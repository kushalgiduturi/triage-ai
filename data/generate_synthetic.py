"""Generate 400 synthetic complaints -> data/complaints.csv.

The *structure* of the dataset (which incidents exist, cluster sizes, labels,
locations, timestamps, which rows carry fake PII) is fully determined by a fixed
random seed. Only the *wording* can come from two sources:

  --mode llm       Claude writes the complaint text in batches (needs ANTHROPIC_API_KEY)
  --mode template  Text is assembled from data/scenarios.py phrase banks (offline)
  --mode auto      llm if a key is configured, otherwise template (default)

Planted structure:
  * 25 duplicate clusters, 3-8 complaints each, describing the same incident
  * 10 "related but not identical" clusters (same place + category, different issue)
  * the rest are singletons
  * ~12% of rows contain fake names / phones / emails / roll numbers (PII masking test)

Usage:
    python data/generate_synthetic.py [--n 400] [--seed 42] [--mode auto]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import ANTHROPIC_MODEL, COMPLAINTS_CSV, has_anthropic_key  # noqa: E402
from app.taxonomy import URGENCY_LEVELS, URGENCY_RANK, load_taxonomy  # noqa: E402
from data.scenarios import CLOSERS, FAKE_FIRST, FAKE_LAST, LOCATIONS, OPENERS, SCENARIOS  # noqa: E402

N_DUP_CLUSTERS = 25
N_RELATED_CLUSTERS = 10
PII_RATE = 0.12
WINDOW_START = datetime(2026, 10, 11, 6, 0)
WINDOW_DAYS = 14
STYLES = ["formal", "casual", "hi", "te"]
STYLE_WEIGHTS = [0.3, 0.3, 0.2, 0.2]
STYLE_NAMES = {
    "formal": "formal English",
    "casual": "casual English with a few typos and no capitalisation",
    "hi": "Hinglish (Hindi written in Latin script mixed with English)",
    "te": "Telugu-English mix (Telugu written in Latin script mixed with English)",
}
SEVERITY_TO_URGENCY = {1: "Low", 2: "Medium", 3: "Medium", 4: "High", 5: "Critical"}


@dataclass
class Incident:
    """One real-world incident; a duplicate cluster has several reports of it."""

    key: str
    sub_issue: str
    location: str
    n_reports: int
    cluster_id: str = ""
    escalated: bool = False
    start: datetime = field(default_factory=lambda: WINDOW_START)


@dataclass
class Row:
    incident: Incident
    timestamp: datetime
    style: str
    length: str
    mention_escalator: bool
    pii: str = ""
    text: str = ""


# --------------------------------------------------------------------------- structure


def _locations_for(sub_issue: str) -> list[str]:
    types = SCENARIOS[sub_issue]["loc_types"]
    return [name for name, meta in LOCATIONS.items() if meta["type"] in types]


def build_incidents(n_total: int, rng: random.Random) -> list[Incident]:
    """Plan the incidents so that (sub_issue, location) pairs never repeat."""
    used: set[tuple[str, str]] = set()
    incidents: list[Incident] = []
    subs = sorted(SCENARIOS)

    def take(sub_issue: str, location: str | None = None) -> tuple[str, str] | None:
        options = [location] if location else _locations_for(sub_issue)
        options = [loc for loc in options if (sub_issue, loc) not in used]
        if not options:
            return None
        loc = rng.choice(options)
        used.add((sub_issue, loc))
        return sub_issue, loc

    def random_start(margin_days: float = 0) -> datetime:
        return WINDOW_START + timedelta(hours=rng.uniform(0, (WINDOW_DAYS - margin_days) * 24))

    # 1) Duplicate clusters: prefer issues people actually report en masse.
    mass_issues = [
        "no_water_supply", "power_outage", "wifi_down", "food_poisoning", "food_quality",
        "garbage_not_collected", "sewage_overflow", "potholes_road_damage", "streetlight_not_working",
        "electric_shock_hazard", "contaminated_water", "harassment", "stray_animals", "dirty_washrooms",
        "sparking_wiring", "lift_not_working", "slow_internet", "mess_hygiene", "exam_schedule_clash",
        "fire_hazard", "blocked_drain", "pest_infestation", "unsafe_area", "ragging", "voltage_fluctuation",
    ]
    for i, sub in enumerate(mass_issues[:N_DUP_CLUSTERS]):
        picked = take(sub)
        assert picked, f"no location left for {sub}"
        size = rng.randint(3, 8)
        has_esc = "escalator" in SCENARIOS[sub]
        incidents.append(Incident(
            key=f"D{i + 1:02d}", sub_issue=sub, location=picked[1], n_reports=size,
            cluster_id=f"D{i + 1:02d}", escalated=has_esc and rng.random() < 0.4,
            start=random_start(margin_days=2),
        ))

    # 2) Related clusters: same location + category, different sub_issue, close in time.
    for j in range(N_RELATED_CLUSTERS):
        for _ in range(100):
            category = rng.choice(sorted({s["category"] for s in SCENARIOS.values()}))
            cat_subs = [s for s in subs if SCENARIOS[s]["category"] == category]
            location = rng.choice(sorted(LOCATIONS))
            candidates = [s for s in cat_subs if location in _locations_for(s) and (s, location) not in used]
            if len(candidates) >= 2:
                break
        k = min(len(candidates), rng.randint(2, 3))
        start = random_start(margin_days=2)
        for sub in rng.sample(candidates, k):
            take(sub, location)
            incidents.append(Incident(
                key=f"R{j + 1:02d}-{sub}", sub_issue=sub, location=location, n_reports=1,
                cluster_id=f"R{j + 1:02d}", start=start + timedelta(hours=rng.uniform(0, 30)),
            ))

    # 3) Singletons fill the rest.
    n_so_far = sum(inc.n_reports for inc in incidents)
    s_idx = 0
    while n_so_far < n_total:
        sub = rng.choice(subs)
        picked = take(sub)
        if picked is None:
            continue
        s_idx += 1
        has_esc = "escalator" in SCENARIOS[sub]
        incidents.append(Incident(
            key=f"S{s_idx:03d}", sub_issue=sub, location=picked[1], n_reports=1,
            escalated=has_esc and rng.random() < 0.3, start=random_start(),
        ))
        n_so_far += 1
    return incidents


def true_urgency(inc: Incident) -> str:
    """Ground-truth urgency for an incident (shared by all its reports)."""
    tax = load_taxonomy()
    sc = SCENARIOS[inc.sub_issue]
    route = tax.get(sc["category"], inc.sub_issue)
    level = SEVERITY_TO_URGENCY[route.base_severity]
    if inc.escalated:
        level = sc["escalator"][1]
    # Many independent reports of the same incident raise its priority (max: High).
    if inc.n_reports >= 5 and URGENCY_RANK[level] < URGENCY_RANK["High"]:
        level = URGENCY_LEVELS[URGENCY_RANK[level] + 1]
    return level


def plan_rows(incidents: list[Incident], rng: random.Random) -> list[Row]:
    rows: list[Row] = []
    for inc in incidents:
        t = inc.start
        styles = rng.choices(STYLES, weights=STYLE_WEIGHTS, k=inc.n_reports)
        for r in range(inc.n_reports):
            rows.append(Row(
                incident=inc, timestamp=t, style=styles[r],
                length=rng.choice(["short", "medium", "medium", "long"]),
                mention_escalator=inc.escalated and (r == 0 or rng.random() < 0.5),
                pii=fake_pii(rng, styles[r]) if rng.random() < PII_RATE else "",
            ))
            t += timedelta(hours=rng.uniform(0.2, 9))
    rows.sort(key=lambda r: r.timestamp)
    return rows


# --------------------------------------------------------------------------- PII


def fake_phone(rng: random.Random) -> str:
    digits = str(rng.choice([6, 7, 8, 9])) + "".join(str(rng.randint(0, 9)) for _ in range(9))
    fmt = rng.choice(["plain", "spaced", "plus", "dashed"])
    if fmt == "spaced":
        return f"{digits[:5]} {digits[5:]}"
    if fmt == "plus":
        return f"+91 {digits}"
    if fmt == "dashed":
        return f"+91-{digits[:5]}-{digits[5:]}"
    return digits


def fake_pii(rng: random.Random, style: str) -> str:
    first, last = rng.choice(FAKE_FIRST), rng.choice(FAKE_LAST)
    roll = f"{rng.randint(20, 25)}B{rng.randint(10, 99)}A{rng.randint(1, 9):02d}{rng.randint(1, 99):02d}"
    email = f"{first.lower()}.{last.lower()}{rng.randint(1, 99)}@{rng.choice(['example.com', 'example.edu', 'example.org'])}"
    phone = fake_phone(rng)
    if style == "hi":
        options = [f"Mera naam {first} {last} hai, number {phone}.", f"Roll no {roll}, contact {phone}."]
    elif style == "te":
        options = [f"Naa peru {first} {last}, phone {phone}.", f"Roll no {roll}, mail {email}."]
    else:
        options = [
            f"My name is {first} {last}, roll no {roll}.",
            f"You can reach me at {email} or {phone}.",
            f"Regards, {first} {last} ({phone})",
            f"- {first} {last}, Employee ID EMP{rng.randint(1000, 9999)}",
            f"Contact: {phone}",
        ]
    return rng.choice(options)


# --------------------------------------------------------------------------- template text


def _noise(text: str, rng: random.Random, rate: float) -> str:
    """Introduce realistic typos: dropped / swapped letters, txt-speak."""
    swaps = {"please": "pls", "you": "u", "are": "r", "because": "coz", "very": "vry", "the": "teh"}
    out = []
    for w in text.split(" "):
        lw = w.lower()
        if lw in swaps and rng.random() < rate * 2:
            w = swaps[lw]
        elif len(w) > 4 and rng.random() < rate:
            i = rng.randint(1, len(w) - 2)
            w = w[:i] + w[i + 1:] if rng.random() < 0.5 else w[:i] + w[i + 1] + w[i] + w[i + 2:]
        out.append(w)
    return " ".join(out)


def template_text(row: Row, rng: random.Random) -> str:
    inc = row.incident
    sc = SCENARIOS[inc.sub_issue]
    alias = rng.choice(LOCATIONS[inc.location]["aliases"])
    bank = {"formal": sc["en"], "casual": sc["en"], "hi": sc["hi"], "te": sc["te"]}[row.style]
    core = rng.choice(bank).replace("{loc}", alias)
    if core and core[0].islower():
        core = core[0].upper() + core[1:]
    parts: list[str] = []
    opener_style = row.style
    if row.length != "short" and rng.random() < 0.6:
        parts.append(rng.choice(OPENERS[opener_style]))
    parts.append(core)
    if row.length != "short" and sc.get("details") and rng.random() < 0.7:
        parts.append(rng.choice(sc["details"]))
    if row.mention_escalator:
        parts.append(sc["escalator"][0])
    if row.length == "long":
        if len(sc.get("details", [])) > 1 and rng.random() < 0.5:
            parts.append(rng.choice(sc["details"]))
        parts.append(rng.choice(CLOSERS[opener_style]))
    text = " ".join(dict.fromkeys(parts))  # dedupe, keep order
    if row.style == "casual":
        text = _noise(text.lower(), rng, 0.08)
        if rng.random() < 0.4:
            text = text.rstrip(".") + rng.choice(["!!", "!!!", " :(", " ..."])
    elif row.style in ("hi", "te") and rng.random() < 0.5:
        text = _noise(text, rng, 0.04)
    return text


# --------------------------------------------------------------------------- Claude text


def llm_texts(rows: list[Row], client) -> list[str] | None:
    """Ask Claude to write one complaint per row. Returns None on any failure."""
    import anthropic

    items = []
    for i, row in enumerate(rows):
        inc = row.incident
        sc = SCENARIOS[inc.sub_issue]
        facts = sc["en"][0].replace("{loc}", inc.location)
        if row.mention_escalator:
            facts += " " + sc["escalator"][0]
        items.append({
            "item": i,
            "incident_key": inc.key,
            "facts": facts,
            "location_mention": rng_alias(inc.location, i),
            "style": STYLE_NAMES[row.style],
            "length": {"short": "1 sentence", "medium": "2-3 sentences", "long": "4-6 sentences"}[row.length],
        })
    prompt = (
        "You are generating SYNTHETIC complaint messages for testing a campus / public-service complaint "
        "triage system. Write exactly one complaint per item below. Rules:\n"
        "- Each complaint must describe the item's facts, mentioning the location the way given in location_mention.\n"
        "- Items that share an incident_key describe the SAME real incident but are written by different "
        "people independently: vary wording, details and tone so they are not copies.\n"
        "- Follow the requested style and length. Do not add any names, phone numbers, emails or IDs.\n"
        "- Do not invent a more severe situation than the facts describe.\n\n"
        f"Items:\n{json.dumps(items, ensure_ascii=False, indent=1)}"
    )
    schema = {
        "type": "object",
        "properties": {
            "complaints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"item": {"type": "integer"}, "text": {"type": "string"}},
                    "required": ["item", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["complaints"],
        "additionalProperties": False,
    }
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=16000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            return None
        text = next(b.text for b in response.content if b.type == "text")
        by_item = {c["item"]: c["text"].strip() for c in json.loads(text)["complaints"]}
        if len(by_item) != len(rows) or not all(by_item.get(i) for i in range(len(rows))):
            return None
        return [by_item[i] for i in range(len(rows))]
    except (anthropic.APIError, json.JSONDecodeError, KeyError, StopIteration) as exc:
        print(f"  ! Claude batch failed ({type(exc).__name__}), using templates for this batch")
        return None


def rng_alias(location: str, salt: int) -> str:
    aliases = LOCATIONS[location]["aliases"]
    return aliases[salt % len(aliases)]


# --------------------------------------------------------------------------- main


def generate(n_total: int = 400, seed: int = 42, mode: str = "auto", out: Path = COMPLAINTS_CSV) -> Path:
    rng = random.Random(seed)
    incidents = build_incidents(n_total, rng)
    rows = plan_rows(incidents, rng)
    tax = load_taxonomy()

    use_llm = mode == "llm" or (mode == "auto" and has_anthropic_key())
    if mode == "llm" and not has_anthropic_key():
        raise SystemExit("--mode llm needs ANTHROPIC_API_KEY")
    text_rng = random.Random(seed + 1)  # separate stream so wording never shifts the structure

    if use_llm:
        import anthropic

        client = anthropic.Anthropic()
        print(f"Generating text with Claude ({ANTHROPIC_MODEL}) in batches...")
        # Batch duplicate clusters together so Claude can vary wording within an incident.
        batches: list[list[Row]] = []
        by_cluster: dict[str, list[Row]] = {}
        loose: list[Row] = []
        for row in rows:
            (by_cluster.setdefault(row.incident.key, []) if row.incident.cluster_id.startswith("D") else loose).append(row)
        batches.extend(by_cluster.values())
        batches.extend(loose[i:i + 12] for i in range(0, len(loose), 12))
        for b_i, batch in enumerate(batches, 1):
            texts = llm_texts(batch, client)
            print(f"  batch {b_i}/{len(batches)}: {'claude' if texts else 'template'}")
            for row, txt in zip(batch, texts or [template_text(r, text_rng) for r in batch]):
                row.text = txt
    else:
        print("Generating text from templates (no ANTHROPIC_API_KEY or --mode template).")
        for row in rows:
            row.text = template_text(row, text_rng)

    # Fake PII is always injected by code so the masking test set is deterministic.
    for row in rows:
        if row.pii:
            row.text = f"{row.pii} {row.text}" if text_rng.random() < 0.3 else f"{row.text} {row.pii}"
        row.text = re.sub(r"\s+", " ", row.text).strip()

    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["id", "text", "timestamp", "location", "true_category", "true_sub_issue",
              "true_urgency", "true_department", "cluster_id", "has_pii"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            inc = row.incident
            category = SCENARIOS[inc.sub_issue]["category"]
            writer.writerow({
                "id": f"C{i:04d}",
                "text": row.text,
                "timestamp": row.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "location": inc.location,
                "true_category": category,
                "true_sub_issue": inc.sub_issue,
                "true_urgency": true_urgency(inc),
                "true_department": tax.get(category, inc.sub_issue).department,
                "cluster_id": inc.cluster_id,
                "has_pii": int(bool(row.pii)),
            })
    n_dup = sum(1 for inc in incidents if inc.cluster_id.startswith("D"))
    n_rel = len({inc.cluster_id for inc in incidents if inc.cluster_id.startswith("R")})
    print(f"Wrote {len(rows)} complaints to {out} ({n_dup} duplicate clusters, {n_rel} related clusters, "
          f"{sum(1 for r in rows if r.pii)} with fake PII).")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", choices=["auto", "llm", "template"], default="auto")
    parser.add_argument("--out", type=Path, default=COMPLAINTS_CSV)
    args = parser.parse_args()
    generate(args.n, args.seed, args.mode, args.out)


if __name__ == "__main__":
    main()
