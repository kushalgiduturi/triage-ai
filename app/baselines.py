"""Rule-only baseline: keyword matching, no machine learning, no training data.

Used by eval/run_eval.py to show what TriageAI's learned and LLM paths add over a
hand-written rulebook. Keywords cover English plus common Hinglish and Telugu-English
words. Because the same person wrote these rules and the synthetic data generator,
this baseline is likely optimistic (see docs/RESULTS.md, limitations).
"""

from __future__ import annotations

import re

from app.extract import GROUP_WORDS, LARGE_WORDS, SAFETY_WORDS, SENTIMENT_RULES, Extraction
from app.taxonomy import load_taxonomy

# sub_issue -> keyword regexes (case-insensitive). More specific issues come first so that,
# for example, "electric shock" wins over "power".
RULES: dict[str, list[str]] = {
    "fire_hazard": [r"\bfire\b", r"\bsmoke\b", r"\baag\b", r"gas leak"],
    "electric_shock_hazard": [r"shock", r"current lag", r"live wire"],
    "food_poisoning": [r"food poison", r"vomit", r"ulti\b"],
    "harassment": [r"harass", r"chhed", r"lewd", r"stalk", r"follow(?:s|ing|ed)? me"],
    "ragging": [r"ragg"],
    "theft": [r"stolen", r"theft", r"chori", r"dongat", r"dongil", r"missing"],
    "sparking_wiring": [r"spark", r"chingaari", r"burning smell", r"wiring"],
    "contaminated_water": [r"drinking water", r"yellow", r"muddy", r"brown water", r"ganda", r"peene ka paani"],
    "no_water_supply": [r"no water", r"water supply", r"paani nahi", r"water raavat", r"neellu levu", r"taps? .*dry", r"tank (?:is )?empty", r"khali"],
    "leakage": [r"leak", r"dripping", r"kaaruthunn", r"tap .*(?:not|nahi) (?:close|band)"],
    "blocked_drain": [r"drain", r"naali", r"clog", r"choke"],
    "water_cooler_broken": [r"water cooler", r"dispenser", r"\bcooler\b"],
    "power_outage": [r"power cut", r"no electricity", r"power (?:went|ledu)", r"light nahi", r"bijli", r"current ledu", r"generator"],
    "voltage_fluctuation": [r"voltage", r"flicker"],
    "lights_fans_not_working": [r"tube ?light", r"\bfans?\b", r"pankhe", r"lights? .*(?:off|not working)"],
    "potholes_road_damage": [r"pothole", r"gaddhe", r"road .*(?:broken|damage)", r"sadak"],
    "streetlight_not_working": [r"street ?light", r"andhera", r"cheekati"],
    "building_structural_damage": [r"crack", r"plaster", r"railing", r"daraar", r"collapse"],
    "lift_not_working": [r"\blift\b", r"elevator"],
    "broken_furniture": [r"bench", r"\bcot\b", r"cupboard", r"chair", r"palang", r"almari", r"furniture"],
    "garbage_not_collected": [r"garbage", r"dustbin", r"\bbins?\b", r"kooda", r"kachra", r"chetha", r"trash"],
    "dirty_washrooms": [r"washroom", r"toilet", r"bathroom.*(?:dirty|clean)"],
    "sewage_overflow": [r"sewage", r"manhole", r"septic", r"gutter"],
    "pest_infestation": [r"cockroach", r"\brats?\b", r"bed ?bugs?", r"khatmal", r"chuhe", r"elukalu", r"nallulu"],
    "stray_animals": [r"stray", r"\bdogs?\b", r"kutt", r"kukkalu"],
    "mess_hygiene": [r"insect", r"keeda", r"purugu", r"\bhair\b", r"gloves", r"kitchen .*dirty", r"plates"],
    "food_quality": [r"food", r"rice", r"\bdal\b", r"daal", r"khana", r"undercooked", r"kaccha", r"tasteless"],
    "room_allocation": [r"room (?:allot|allocation|change)", r"allot", r"two-seater", r"reallocate"],
    "hostel_maintenance": [r"window", r"geyser", r"door lock", r"washing machine", r"\btv\b"],
    "wifi_down": [r"wi-?fi .*(?:down|band|not working)", r"no internet", r"internet (?:nahi|raavat)", r"access points?"],
    "slow_internet": [r"slow", r"mbps", r"disconnect"],
    "portal_login_issue": [r"portal", r"\berp\b", r"login", r"password"],
    "lab_computer_fault": [r"computers?", r"\bsystems?\b", r"\bpcs?\b", r"projector", r"keyboard"],
    "email_account_issue": [r"e-?mail", r"mailbox"],
    "unsafe_area": [r"unsafe", r"isolated", r"security guard", r"boundary wall", r"sharaab", r"drink"],
    "exam_schedule_clash": [r"timetable", r"exam .*(?:same|clash)", r"clash"],
    "fee_refund": [r"refund", r"caution deposit", r"fee .*(?:twice|deducted)"],
    "certificate_delay": [r"certificate", r"transcript", r"bonafide"],
    "attendance_error": [r"attendance", r"marked absent"],
    "faculty_conduct": [r"faculty", r"lecturer", r"professor", r"internal marks", r"insult"],
}
_COMPILED = {sub: [re.compile(p, re.IGNORECASE) for p in pats] for sub, pats in RULES.items()}
_PRIORITY = {sub: i for i, sub in enumerate(RULES)}


def rule_extract(masked_text: str, location_hint: str | None = None) -> Extraction:
    """Classify by counting keyword hits per sub_issue; ties go to the more specific (earlier) rule."""
    tax = load_taxonomy()
    hits = {sub: sum(bool(rx.search(masked_text)) for rx in rxs) for sub, rxs in _COMPILED.items()}
    matched = sorted((sub for sub, n in hits.items() if n), key=lambda s: (-hits[s], _PRIORITY[s]))
    if matched:
        sub_issue = matched[0]
        # Confidence: 1.0 for a clear winner, lower when other rules also fired.
        confidence = round(hits[sub_issue] / sum(hits[s] for s in matched), 3)
        reason = f"Rule baseline: matched keywords for {sub_issue} ({hits[sub_issue]} hit(s))."
    else:
        sub_issue, confidence = "hostel_maintenance", 0.0  # no rule fired: left for manual triage
        reason = "Rule baseline: no keyword rule matched; needs manual triage."
    category = tax.category_of(sub_issue)
    if LARGE_WORDS.search(masked_text):
        people = "large"
    elif GROUP_WORDS.search(masked_text):
        people = "group"
    else:
        people = "individual"
    return Extraction(
        category=category,
        sub_issue=sub_issue,
        location=location_hint or "unknown",
        one_line_summary=f"{sub_issue.replace('_', ' ').capitalize()} reported at {location_hint or 'unknown'}.",
        safety_risk=bool(SAFETY_WORDS.search(masked_text)) or category == "Safety and Harassment",
        people_affected=people,
        sentiment=next((name for name, rx in SENTIMENT_RULES if rx.search(masked_text)), "neutral"),
        severity=tax.get(category, sub_issue).base_severity,
        confidence=confidence,
        reasoning=reason,
        method="fallback",
    )
