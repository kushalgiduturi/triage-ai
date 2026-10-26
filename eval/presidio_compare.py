"""Run Microsoft Presidio (default AnalyzerEngine) on TriageAI's PII leak-test cases.

Needs presidio-analyzer and the spaCy model it uses by default, in any environment:
    pip install presidio-analyzer && python -m spacy download en_core_web_lg
    python eval/pii_leak_test.py --dump-cases eval/results/pii_cases.json   # in the TriageAI env
    python eval/presidio_compare.py eval/results/pii_cases.json             # in the Presidio env

A planted value counts as leaked if any occurrence of it is not fully covered by a Presidio
detection of any entity type (the same rule as eval/pii_leak_test.py). Writes
eval/results/presidio_compare.json.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

from presidio_analyzer import AnalyzerEngine


def occurrences(text: str, item: dict) -> list[tuple[int, int]]:
    value = item["value"]
    if item["type"] == "NAME":
        return [m.span() for m in re.finditer(rf"\b{re.escape(value)}\b", text, re.IGNORECASE)]
    return [m.span() for m in re.finditer(re.escape(value), text)]


def phone_format(value: str) -> str:
    """Describe a phone number's layout, e.g. '+91 dddddddddd' or 'ddddd ddddd'."""
    return re.sub(r"\d", "d", value)


def main() -> None:
    cases_path = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/results/pii_cases.json")
    sets = json.loads(cases_path.read_text(encoding="utf-8"))
    analyzer = AnalyzerEngine()
    report = {"presidio_analyzer_version": version("presidio-analyzer"), "spacy_version": version("spacy"),
              "nlp_model": "en_core_web_lg (default)", "sets": {}}
    for set_name, cases in sets.items():
        planted, leaked = Counter(), Counter()
        phone_miss, phone_total = Counter(), Counter()
        place_hits, misses = [], []
        entity_types = Counter()
        for case in cases:
            text = case["text"]
            results = analyzer.analyze(text=text, language="en")
            spans = [(r.start, r.end, r.entity_type) for r in results]
            entity_types.update(r.entity_type for r in results)
            covered = lambda s, e: any(a <= s and e <= b for a, b, _ in spans)  # noqa: E731
            unique = {(i["type"], i["value"].lower()): i for i in case["pii"]}.values()
            for item in unique:
                occ = occurrences(text, item)
                planted[item["type"]] += 1
                is_leak = not occ or any(not covered(s, e) for s, e in occ)
                leaked[item["type"]] += is_leak
                if item["type"] == "PHONE":
                    phone_total[phone_format(item["value"])] += 1
                    phone_miss[phone_format(item["value"])] += is_leak
                if is_leak:
                    misses.append({"id": case["id"], "type": item["type"], "value": item["value"], "text": text,
                                   "presidio": [(text[a:b], t) for a, b, t in spans]})
            for m in re.finditer(re.escape(case["place"]), text):
                hit = [t for a, b, t in spans if a < m.end() and m.start() < b]
                if hit:
                    place_hits.append({"id": case["id"], "place": case["place"], "detected_as": hit})
        report["sets"][set_name] = {
            "n_complaints": len(cases),
            "by_type": {t: {"planted": planted[t], "leaked": leaked[t]} for t in sorted(planted)},
            "leaked_total": sum(leaked.values()), "planted_total": sum(planted.values()),
            "phone_formats": {f: {"planted": phone_total[f], "missed": phone_miss[f]} for f in sorted(phone_total)},
            "location_codes_flagged": len(place_hits),
            "location_flag_examples": place_hits[:10],
            "entity_types_returned": dict(entity_types.most_common()),
            "misses_sample": misses[:15],
        }
    out = Path("eval/results/presidio_compare.json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, r in report["sets"].items():
        print(name, "| leaked", r["leaked_total"], "of", r["planted_total"], "|", {t: v["leaked"] for t, v in r["by_type"].items()},
              "| locations flagged", r["location_codes_flagged"])
        print("   phone formats (missed/planted):", {f: f"{v['missed']}/{v['planted']}" for f, v in r["phone_formats"].items()})
    print("versions:", report["presidio_analyzer_version"], "spaCy", report["spacy_version"])


if __name__ == "__main__":
    main()
