"""PII masking with regular expressions plus simple rules.

Runs before any text is sent to the LLM or embedded. Masks:
  EMAIL  - anything that looks like an email address
  PHONE  - Indian mobile numbers (+91 / 0 prefixes, spaces or dashes) and long digit runs
  ID     - roll numbers (e.g. 21B81A0512), employee IDs (EMP1234), labelled IDs ("roll no: ...")
  NAME   - names introduced by cues ("my name is", "regards,", "naa peru", ...), honorifics
           (Mr./Ms./Dr./Prof.), and known first names followed by a capitalised surname

Rules are intentionally conservative: we would rather miss an unusual name than
mask location words such as "Block A" or "Girls Hostel".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A small list of common first names (synthetic data uses these; real deployments would
# plug in a NER model here). Lower-case for matching.
COMMON_FIRST_NAMES = {
    "aarav", "priya", "rahul", "sneha", "kiran", "divya", "arjun", "meena", "vikram", "lakshmi",
    "rohan", "anjali", "suresh", "kavya", "naveen", "pooja", "ravi", "ramesh", "sita", "amit",
    "neha", "sanjay", "deepa", "arun", "manoj", "swathi", "srinivas", "harish", "sai", "teja",
}

# Words that are never part of a person's name in this domain (protects locations etc.).
NOT_NAME_WORDS = {
    "block", "hostel", "girls", "boys", "mess", "road", "gate", "lab", "library", "building",
    "sir", "madam", "team", "the", "and", "from", "room", "floor", "ward", "sector", "a", "an",
    "please", "kindly", "thanks", "thank", "student", "students", "hai", "hoon", "here",
}

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# +91 98765 43210, +91-98765-43210, 09876543210, 9876543210, 98765 43210, 984 801 2345
PHONE_RE = re.compile(r"(?<![\w+])(?:\+?91[\s-]?|0)?(?:[6-9]\d{4}[\s-]?\d{5}|[6-9]\d{2}[\s-]\d{3}[\s-]\d{4})(?!\d)")
# University roll numbers: 21B81A0512, and JNTU-style 10-character codes such as 22341A05C3.
ROLL_RE = re.compile(r"\b(?:\d{2}[A-Z]\d{2}[A-Z]\d{4}|\d{2}[0-9A-Z]{3}A[0-9A-Z]{4})\b")
EMP_RE = re.compile(r"\b(?:EMP|STU|EID|ID)[-/]?\d{3,}\b", re.IGNORECASE)
LABELLED_ID_RE = re.compile(
    r"\b(?:roll|reg(?:istration)?|enrol(?:l?ment)?|employee|emp|student|aadhaar|aadhar|hall\s*ticket)"
    r"\s*(?:no\.?|number|num|id|#)?\s*[:.\-]?\s*([A-Z0-9][A-Z0-9/-]{4,})",
    re.IGNORECASE,
)
AADHAAR_RE = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")

_NAME_TOKEN = r"[A-Z][a-z]+"
NAME_CUE_RE = re.compile(
    r"(?:(?i:my name is|i am|i'm|this is|name\s*[:\-]|regards,?|thanks,?|sincerely,?|"
    r"contact(?:\s+me)?(?:\s+at)?\s*[:\-]?|call(?:\s+me)?|mera naam|naa peru|naa paeru|from)\s+|^-\s*|\s-\s)"
    rf"({_NAME_TOKEN}(?:\s{_NAME_TOKEN}){{0,2}})"
)
HONORIFIC_RE = re.compile(rf"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+({_NAME_TOKEN}(?:\s{_NAME_TOKEN})?)")
# Names followed by an Indian-language honorific or kinship suffix ("Abhishek garu", "varun bhaiya").
# Case-insensitive, because code-mixed messages are often typed in lowercase.
SUFFIX_HONORIFIC_RE = re.compile(
    r"\b(?:([A-Z][a-z]+)\s+)?([A-Za-z]{3,})\s+(?i:garu|gaaru|bhaiya|bhaiyya|bhai|didi|anna|akka|ji|saab|sahab)\b"
)
# A speaker introducing themselves: "Ritu Shetty bol raha hoon", "Fatima Banerjee here from ...".
SPEAKER_RE = re.compile(
    rf"\b({_NAME_TOKEN}(?:\s{_NAME_TOKEN})?)\s+(?:bol\s+raha|bol\s+rahi|here\s+from|here,|speaking|maatladutunna)",
)
# Lowercase words that the suffix rule must never treat as a name.
NOT_NAME_LOWER = {"call", "contact", "please", "pls", "plz", "the", "and", "aap", "meru", "mee", "sir", "madam",
                  "you", "your", "thank", "thanks", "him", "her", "them", "hai", "haan", "nahi", "ok", "okay"}
FIRST_LAST_RE = re.compile(rf"\b({_NAME_TOKEN})\s+({_NAME_TOKEN})\b")
KNOWN_FIRST_NAME_RE = re.compile(r"\b(?:" + "|".join(n.capitalize() for n in sorted(COMMON_FIRST_NAMES)) + r")\b")


@dataclass(frozen=True)
class PIIMatch:
    """One masked span. `value` is kept only in memory for the caller; never persisted."""

    type: str
    value: str
    start: int
    end: int


def _is_name(candidate: str) -> bool:
    words = candidate.split()
    return bool(words) and all(w.lower() not in NOT_NAME_WORDS for w in words)


def find_pii(text: str) -> list[PIIMatch]:
    """Return non-overlapping PII spans, earliest first."""
    found: list[PIIMatch] = []

    def add(kind: str, start: int, end: int) -> None:
        found.append(PIIMatch(kind, text[start:end], start, end))

    for m in EMAIL_RE.finditer(text):
        add("EMAIL", m.start(), m.end())
    for m in PHONE_RE.finditer(text):
        add("PHONE", m.start(), m.end())
    for regex in (ROLL_RE, EMP_RE, AADHAAR_RE):
        for m in regex.finditer(text):
            add("ID", m.start(), m.end())
    for m in LABELLED_ID_RE.finditer(text):
        if any(ch.isdigit() for ch in m.group(1)):
            add("ID", m.start(1), m.end(1))
    for regex in (NAME_CUE_RE, HONORIFIC_RE):
        for m in regex.finditer(text):
            if _is_name(m.group(1)):
                add("NAME", m.start(1), m.end(1))
    for m in FIRST_LAST_RE.finditer(text):
        if m.group(1).lower() in COMMON_FIRST_NAMES and _is_name(m.group(2)):
            add("NAME", m.start(), m.end())
    # A known first name on its own ("Contact Priya", "ask Ravi") is masked too.
    for m in KNOWN_FIRST_NAME_RE.finditer(text):
        add("NAME", m.start(), m.end())
    for m in SUFFIX_HONORIFIC_RE.finditer(text):
        # The word right before the honorific is the name; an optional capitalised word before
        # it is the first name ("Abhishek Rao garu"), unless it is an ordinary word ("Call").
        if m.group(2).lower() in NOT_NAME_LOWER or not _is_name(m.group(2)):
            continue
        first = m.group(1)
        start = m.start(1) if first and first.lower() not in NOT_NAME_LOWER and _is_name(first) else m.start(2)
        add("NAME", start, m.end(2))
    for m in SPEAKER_RE.finditer(text):
        if _is_name(m.group(1)):
            add("NAME", m.start(1), m.end(1))

    # Once a word is known to be part of a name, mask its other occurrences in the same text
    # ("Yashwanth Goud bol raha hoon ... pls call yashwanth bhaiya").
    name_words = {w for p in found if p.type == "NAME" for w in p.value.split() if len(w) >= 3}
    for word in name_words:
        for m in re.finditer(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            add("NAME", m.start(), m.end())

    # Resolve overlaps: prefer the longest span, then the earliest.
    found.sort(key=lambda p: (p.start, -(p.end - p.start)))
    result: list[PIIMatch] = []
    for p in found:
        if result and p.start < result[-1].end:
            if (p.end - p.start) > (result[-1].end - result[-1].start):
                result[-1] = p
            continue
        result.append(p)
    return result


def mask_pii(text: str) -> tuple[str, list[dict[str, str]]]:
    """Mask PII in `text`.

    Returns the masked text (e.g. "call [PHONE]") and a list of
    {"type": ..., "value": ...} dicts describing what was masked.
    """
    matches = find_pii(text)
    out, cursor = [], 0
    for m in matches:
        out.append(text[cursor:m.start])
        out.append(f"[{m.type}]")
        cursor = m.end
    out.append(text[cursor:])
    return "".join(out), [{"type": m.type, "value": m.value} for m in matches]
