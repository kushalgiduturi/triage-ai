"""PII leak test: does any raw personal data reach the LLM prompt?

    python eval/pii_leak_test.py            # 120 complaints, seed 42

Builds Indian-style complaints (Hinglish, Telugu-English, Indian English) with planted PII:
names (deliberately NOT from the masker's built-in first-name list), Indian phone formats,
emails, roll numbers (including JNTU-style codes), employee IDs and Aadhaar-style numbers.
Each complaint also contains hostel or block codes that must NOT be masked.

Every complaint goes through the real pipeline with a fake LLM provider that records the
exact prompt it would have sent. A planted value found in that prompt is a leak.

Outputs:
    eval/pii_misses.json      every leaked value with its complaint and prompt
    eval/results/pii.json     summary counts (leaks by type, over-masked location codes)
"""

from __future__ import annotations

import json
import random
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import make_session_factory  # noqa: E402
from app.duplicates import DuplicateIndex, HashEmbedder  # noqa: E402
from app.extract import Extractor, StructuredLLM  # noqa: E402
from app.pii import COMMON_FIRST_NAMES  # noqa: E402
from app.pipeline import TriagePipeline  # noqa: E402

N = 120
SEED = 42
FIRST = ["Venkatesh", "Lavanya", "Harika", "Gowtham", "Sravani", "Chaitanya", "Bhavana", "Yashwanth", "Keerthi",
         "Nikhil", "Tejaswini", "Pranav", "Ritu", "Imran", "Fatima", "Joseph", "Gurpreet", "Manasa", "Sandeep",
         "Akhila", "Raghav", "Shreya", "Varun", "Swetha", "Abhishek", "Nandini", "Karthik", "Mounika"]
LAST = ["Chowdary", "Yadav", "Khan", "Patil", "Bhat", "Das", "Mishra", "Goud", "Shetty", "Kulkarni", "Pillai",
        "Banerjee", "Jain", "Thomas", "Sinha", "Agarwal"]
assert not {f.lower() for f in FIRST} & COMMON_FIRST_NAMES, "test names must not be in the masker's list"

# Held-out set: different names and phrasings that were NOT used while improving the masker.
HELDOUT_FIRST = ["Anirudh", "Pavani", "Sowmya", "Rajesh", "Deepika", "Aditya", "Haritha", "Mohammed", "Ayesha",
                 "Vamsi", "Snigdha", "Rakesh", "Kalyani", "Tarun", "Ishita", "Prakash", "Anusha", "Vivek"]
HELDOUT_LAST = ["Kamath", "Saxena", "Hegde", "Rathod", "Menon", "Qureshi", "Dutta", "Reddy", "Prasad", "Bose"]
assert not {f.lower() for f in HELDOUT_FIRST} & COMMON_FIRST_NAMES
assert not set(HELDOUT_FIRST) & set(FIRST)

PLACES = [  # (alias used in text, must stay unmasked)
    "BH-A", "BH-C", "GH-1", "GH-2", "Block C", "A-block", "Girls Hostel 2", "PG hostel", "CSE block", "Gate 2",
]
ISSUES = {
    "hi": ["{p} mein subah se paani nahi aa raha hai.", "{p} ke washroom bahut gande hain.",
           "{p} mein kal raat se light nahi hai.", "{p} ke paas street light band hai, andhera rehta hai.",
           "{p} mein WiFi bilkul band hai."],
    "te": ["{p} lo morning nunchi water raavatledu.", "{p} lo washrooms chala dirty ga unnayi.",
           "{p} lo current ledu ninna raatri nunchi.", "{p} daggara street lights work avvatledu.",
           "{p} lo WiFi poorthiga down lo undi."],
    "en": ["No water in {p} since morning.", "The washrooms in {p} are filthy.",
           "Power cut in {p} since last night.", "Streetlights near {p} are not working.",
           "WiFi in {p} has been down all day."],
}


def phone(rng: random.Random) -> str:
    d = str(rng.choice([6, 7, 8, 9])) + "".join(str(rng.randint(0, 9)) for _ in range(9))
    return rng.choice([f"+91 {d[:5]} {d[5:]}", d, f"0{d[:5]} {d[5:]}", f"+91-{d[:5]}-{d[5:]}", f"{d[:5]}-{d[5:]}",
                       f"{d[:3]} {d[3:6]} {d[6:]}", f"+91{d}"])


def roll(rng: random.Random) -> str:
    return rng.choice([
        f"{rng.randint(20, 25)}B{rng.randint(10, 99)}A{rng.randint(1000, 9999)}",   # 21B81A0512 style
        f"{rng.randint(20, 25)}{rng.randint(100, 999)}A{rng.randint(0, 9)}{rng.choice('0123456789')}{rng.choice('ABCDEFGH')}{rng.randint(0, 9)}",  # JNTU 22341A05C3
    ])


def snippets(rng: random.Random, lang: str, p: str) -> list[tuple[str, list[dict]]]:
    f, l = rng.choice(FIRST), rng.choice(LAST)
    ph, r, em = phone(rng), roll(rng), f"{f.lower()}.{l.lower()}{rng.randint(1, 99)}@gmail.com"
    aad = f"{rng.randint(2000, 9999)} {rng.randint(1000, 9999)} {rng.randint(1000, 9999)}"
    name = [{"type": "NAME", "value": f}, {"type": "NAME", "value": l}]
    options = {
        "hi": [(f"Mera naam {f} {l} hai, number {ph}.", name + [{"type": "PHONE", "value": ph}]),
               (f"{f} {l} bol raha hoon, {p} se. Call karo {ph}.", name + [{"type": "PHONE", "value": ph}]),
               (f"pls call {f.lower()} bhaiya {ph}", [{"type": "NAME", "value": f}, {"type": "PHONE", "value": ph}]),
               (f"Roll no {r}, mail {em}", [{"type": "ID", "value": r}, {"type": "EMAIL", "value": em}])],
        "te": [(f"Naa peru {f} {l}, phone {ph}.", name + [{"type": "PHONE", "value": ph}]),
               (f"{f} garu ki cheppandi, {ph}.", [{"type": "NAME", "value": f}, {"type": "PHONE", "value": ph}]),
               (f"Roll number {r}. Aadhaar {aad} kuda ichanu.", [{"type": "ID", "value": r}, {"type": "ID", "value": aad}]),
               (f"- {f} ({r})", [{"type": "NAME", "value": f}, {"type": "ID", "value": r}])],
        "en": [(f"Regards, {f} {l}, Roll No: {r}", name + [{"type": "ID", "value": r}]),
               (f"I am {f} {l}, you can reach me at {em}.", name + [{"type": "EMAIL", "value": em}]),
               (f"{f} {l} here from {p}, ph {ph}", name + [{"type": "PHONE", "value": ph}]),
               (f"Contact warden Mr. {l} or me on {ph}.", [{"type": "NAME", "value": l}, {"type": "PHONE", "value": ph}])],
    }[lang]
    return rng.sample(options, 2)


def heldout_snippets(rng: random.Random, lang: str, p: str) -> list[tuple[str, list[dict]]]:
    f, l = rng.choice(HELDOUT_FIRST), rng.choice(HELDOUT_LAST)
    ph, r = phone(rng), roll(rng)
    em = f"{f.lower()}{rng.randint(10, 99)}@yahoo.co.in"
    name = [{"type": "NAME", "value": f}, {"type": "NAME", "value": l}]
    options = {
        "hi": [(f"Main {f} {l}, {p} mein rehta hoon. Mobile {ph}.", name + [{"type": "PHONE", "value": ph}]),
               (f"{f.lower()} ko bolo mujhe {ph} pe call kare", [{"type": "NAME", "value": f}, {"type": "PHONE", "value": ph}]),
               (f"Shikayat karta: {f} {l} (roll {r})", name + [{"type": "ID", "value": r}])],
        "te": [(f"Nenu {f} {l}, {p} lo untanu. Number {ph}.", name + [{"type": "PHONE", "value": ph}]),
               (f"{f} madam ki inform cheyyandi, mail {em}", [{"type": "NAME", "value": f}, {"type": "EMAIL", "value": em}]),
               (f"Complaint by {f} {l}, hall ticket {r}", name + [{"type": "ID", "value": r}])],
        "en": [(f"Submitted by {f} {l} ({ph})", name + [{"type": "PHONE", "value": ph}]),
               (f"Please ask {f} at the front desk, or email {em}.", [{"type": "NAME", "value": f}, {"type": "EMAIL", "value": em}]),
               (f"Thanks, {f.lower()} {l.lower()}", name)],
    }[lang]
    return rng.sample(options, 2)


def build_cases(heldout: bool = False) -> list[dict]:
    rng = random.Random(SEED + 1 if heldout else SEED)
    make_snippets = heldout_snippets if heldout else snippets
    cases = []
    for i in range(N):
        lang = ["hi", "te", "en"][i % 3] if i % 5 else rng.choice(["hi", "te"])  # mostly code-mixed
        p = rng.choice(PLACES)
        parts, pii = [rng.choice(ISSUES[lang]).format(p=p)], []
        for text, items in make_snippets(rng, lang, p):
            parts.append(text)
            pii.extend(items)
        cases.append({"id": f"{'H' if heldout else 'P'}{i + 1:03d}", "lang": lang, "text": " ".join(parts), "pii": pii, "place": p})
    return cases


def leaked(item: dict, prompt: str) -> bool:
    value = item["value"]
    if item["type"] == "NAME":
        return re.search(rf"\b{re.escape(value)}\b", prompt, re.IGNORECASE) is not None
    if item["type"] == "PHONE" or (item["type"] == "ID" and re.fullmatch(r"[\d ]+", value)):
        digits = re.sub(r"\D", "", value)[-10:]
        runs = [re.sub(r"\D", "", m) for m in re.findall(r"\+?\d[\d \-]{6,}\d", prompt)]
        return any(digits in r for r in runs)
    return value.lower() in prompt.lower()


class PromptRecorder(StructuredLLM):
    """Fake provider: records the prompt and returns a fixed valid extraction."""

    name = "recorder"

    def __init__(self) -> None:
        super().__init__()
        self.prompts: list[str] = []

    def _call(self, user_content: str) -> str:
        self.prompts.append(user_content)
        return json.dumps({
            "category": "Water and Plumbing", "sub_issue": "no_water_supply", "location": "unknown",
            "one_line_summary": "test", "safety_risk": False, "people_affected": "group",
            "sentiment": "neutral", "severity": 3, "confidence": 0.9, "reasoning": "test",
        })


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--heldout", action="store_true",
                        help="use the held-out names and phrasings that were not used to tune the masker")
    args = parser.parse_args()
    suffix = "_heldout" if args.heldout else ""
    cases = build_cases(args.heldout)
    recorder = PromptRecorder()
    extractor = Extractor(use_llm=True)
    extractor._llm = recorder
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        session_factory = make_session_factory(Path(tmp) / "pii.db")
        pipeline = TriagePipeline(DuplicateIndex(HashEmbedder()), extractor)
        with session_factory() as session:
            for case in cases:
                pipeline.process(session, case["text"], None, datetime(2026, 10, 20, 9, 0))
            session.commit()
        session_factory.kw["bind"].dispose()

    misses, over_masked = [], []
    by_type: dict[str, list[int]] = {}
    for case, prompt in zip(cases, recorder.prompts):
        # Count each distinct value once per complaint, even if the text mentions it twice.
        unique = list({(item["type"], item["value"].lower()): item for item in case["pii"]}.values())
        leaks = [item for item in unique if leaked(item, prompt)]
        for item in unique:
            by_type.setdefault(item["type"], [0, 0])
            by_type[item["type"]][0] += 1
            by_type[item["type"]][1] += item in leaks
        if leaks:
            misses.append({"id": case["id"], "lang": case["lang"], "text": case["text"],
                           "prompt_sent_to_llm": prompt, "leaked": leaks})
        if case["place"] not in prompt:
            over_masked.append({"id": case["id"], "place": case["place"], "prompt_sent_to_llm": prompt})

    total = sum(v[0] for v in by_type.values())
    leak_total = sum(v[1] for v in by_type.values())
    summary = {
        "set": "held-out (not used for tuning)" if args.heldout else "tuning set",
        "n_complaints": len(cases), "seed": SEED + 1 if args.heldout else SEED, "n_pii_items": total, "counting": "distinct values per complaint", "leaked_items": leak_total,
        "complaints_with_any_leak": len(misses),
        "by_type": {t: {"planted": v[0], "leaked": v[1]} for t, v in sorted(by_type.items())},
        "location_codes_over_masked": len(over_masked),
        "languages": {lang: sum(c["lang"] == lang for c in cases) for lang in ("hi", "te", "en")},
        "prompts_checked": len(recorder.prompts),
    }
    (ROOT / "eval" / "results").mkdir(parents=True, exist_ok=True)
    (ROOT / "eval" / f"pii_misses{suffix}.json").write_text(json.dumps({"misses": misses, "over_masked_locations": over_masked},
                                                              indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "eval" / "results" / f"pii{suffix}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
