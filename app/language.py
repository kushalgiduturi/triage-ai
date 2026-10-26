"""Very small heuristic language-style detector used by the bias check.

It only needs to separate the four styles present in the data well enough to
compare urgency outcomes across them; it is not a general language identifier.
"""

from __future__ import annotations

import re

HINGLISH = {"hai", "nahi", "mein", "ka", "ki", "ke", "se", "ho", "raha", "rahi", "gaya", "kal", "bahut", "paani",
            "aur", "bhi", "kuch", "log", "karte", "kar", "mera", "mujhe", "abhi", "tak", "jaldi", "kripya", "bijli"}
TENGLISH = {"lo", "ledu", "undi", "unnayi", "chala", "avtundi", "avvatledu", "cheyyatledu", "raavatledu", "kuda",
            "nunchi", "naa", "ivala", "ninna", "vastundi", "ayyindi", "sir", "andi", "cheyyandi", "levu", "ga"}
CASUAL_MARKERS = re.compile(r"\b(pls|plz|u|r|asap|coz|guys|ok so)\b|!!|:\(")


def detect_style(text: str) -> str:
    """Return one of: hinglish, telugu_english, casual_english, formal_english."""
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return "formal_english"
    hi = sum(w in HINGLISH for w in words)
    te = sum(w in TENGLISH for w in words)
    if max(hi, te) >= 2:
        return "telugu_english" if te > hi else "hinglish"
    if CASUAL_MARKERS.search(text.lower()) or text == text.lower():
        return "casual_english"
    return "formal_english"
