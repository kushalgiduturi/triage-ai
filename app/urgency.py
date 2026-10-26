"""Hybrid urgency scoring: hard safety rules + an additive, explainable score.

Rule layer
    Keywords / flags for life-safety situations force "Critical" no matter what
    the model says (fire, injury, electric shock, harassment, assault, gas leak,
    ragging, food poisoning, no water for 24h+).

Model layer
    score (0-100) = severity points            (LLM severity, or routing-table default offline)
                  + people affected             (individual / group / large)
                  + duplicate reports           (size of the incident cluster)
                  + hours since reported        (ageing of an unresolved complaint)
                  + safety-risk flag
                  + time-critical wording       ("deadline tonight", "visa interview next week")
    Without a rule hit, "Critical" is reserved for severity-5 extractions, so a pile of
    duplicate reports about a broken streetlight can reach "High" but never "Critical".

Every result carries a plain-English reason listing the components that contributed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.extract import Extraction

SEVERITY_POINTS = {1: 15, 2: 40, 3: 46, 4: 62, 5: 88}
SEVERITY_WORDS = {1: "trivial", 2: "routine", 3: "disruptive", 4: "serious / health risk", 5: "danger to life or safety"}
PEOPLE_POINTS = {"individual": 0, "group": 4, "large": 8}
THRESHOLDS = [(85, "Critical"), (58, "High"), (35, "Medium"), (0, "Low")]
NON_CRITICAL_CAP = 84

# (label shown in the reason, pattern). Patterns run on PII-masked text, case-insensitive.
CRITICAL_RULES: list[tuple[str, re.Pattern]] = [
    ("fire / smoke", re.compile(r"\bfire\b(?! extinguisher| safety)|\bsmoke\b|aag lagi|dhuaan", re.I)),
    ("gas leak", re.compile(r"gas\s*leak|gas smell", re.I)),
    ("electric shock", re.compile(r"electric\s*shock|current lag|shock tagil|\bshock\b", re.I)),
    ("injury", re.compile(r"injur|bleed|fractur|\bbit (?:a|me|him|her)\b|unconscious", re.I)),
    ("harassment", re.compile(r"harass|chhed|lewd|molest|stalk", re.I)),
    ("assault", re.compile(r"assault|\bgrab|beaten|\battack", re.I)),
    ("ragging", re.compile(r"\bragg", re.I)),
    ("food poisoning", re.compile(r"food\s*poison", re.I)),
    ("no water for 24h+", re.compile(
        r"(?:no|without) water.{0,40}?(?:\b[2-9]\s*(?:days|din|rojulu)|\b(?:24|36|48|72)\s*(?:h|hours)|more than (?:a|one|1|2) day)",
        re.I)),
]
TIME_CRITICAL = re.compile(r"deadline|tonight|visa|joining date|next week|in \d+ hours", re.I)


@dataclass(frozen=True)
class UrgencyResult:
    level: str
    score: int
    reason: str
    rule: str | None = None


def _level(score: float) -> str:
    return next(level for cutoff, level in THRESHOLDS if score >= cutoff)


def check_rules(text: str) -> str | None:
    """Return the label of the first critical rule that matches, else None."""
    for label, pattern in CRITICAL_RULES:
        if pattern.search(text):
            return label
    return None


def score_urgency(
    extraction: Extraction,
    text: str,
    duplicate_count: int = 1,
    hours_since_reported: float = 0.0,
) -> UrgencyResult:
    """Compute urgency for one complaint.

    duplicate_count: number of reports in this complaint's incident (1 = only this one).
    hours_since_reported: age of the complaint while still unresolved.
    """
    parts: list[tuple[str, float]] = []
    sev = extraction.severity
    parts.append((f"severity {sev}/5 ({SEVERITY_WORDS[sev]})", SEVERITY_POINTS[sev]))
    if PEOPLE_POINTS[extraction.people_affected]:
        parts.append((f"{extraction.people_affected} group affected", PEOPLE_POINTS[extraction.people_affected]))
    if duplicate_count >= 5:
        parts.append((f"{duplicate_count} reports of the same incident", 20))
    elif duplicate_count >= 3:
        parts.append((f"{duplicate_count} reports of the same incident", 8))
    elif duplicate_count == 2:
        parts.append(("2 reports of the same incident", 4))
    if hours_since_reported >= 1:
        parts.append((f"open for {hours_since_reported:.0f}h", round(min(hours_since_reported / 72, 1.0) * 5, 1)))
    if extraction.safety_risk:
        parts.append(("safety risk flagged", 5))
    if TIME_CRITICAL.search(text):
        parts.append(("time-critical wording", 20))

    raw = sum(points for _, points in parts)
    breakdown = ", ".join(f"{name} (+{points:g})" for name, points in parts)

    rule = check_rules(text)
    if rule:
        score = max(90, min(100, round(raw)))
        return UrgencyResult("Critical", score, f"Critical by safety rule: mentions {rule}. Model factors: {breakdown}.", rule)

    if sev < 5:
        raw = min(raw, NON_CRITICAL_CAP)
    score = int(round(min(raw, 100)))
    level = _level(score)
    return UrgencyResult(level, score, f"{level} (score {score}/100): {breakdown}.")
