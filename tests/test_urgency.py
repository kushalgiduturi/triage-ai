"""Tests for app.urgency."""

import pytest

from app.extract import Extraction
from app.urgency import check_rules, score_urgency


def make(category="Electricity", sub_issue="lights_fans_not_working", severity=1, people="individual", safety=False):
    return Extraction(
        category=category, sub_issue=sub_issue, location="Block A Boys Hostel",
        one_line_summary="test", safety_risk=safety, people_affected=people,
        sentiment="neutral", severity=severity, confidence=0.9, reasoning="test",
    )


@pytest.mark.parametrize(
    "text, rule",
    [
        ("A student got an electric shock from the switchboard.", "electric shock"),
        ("There is a fire in the kitchen, smoke everywhere", "fire / smoke"),
        ("Gas leak smell in the mess kitchen", "gas leak"),
        ("Some men are harassing girls near the gate", "harassment"),
        ("A dog bit a student and he is injured", "injury"),
        ("We have had no water for more than 2 days now.", "no water for 24h+"),
        ("Seniors are ragging first years", "ragging"),
    ],
)
def test_rules_force_critical(text, rule):
    assert check_rules(text) == rule
    result = score_urgency(make(severity=2), text)
    assert result.level == "Critical" and result.score >= 90
    assert rule in result.reason


def test_no_rule_for_routine_text():
    assert check_rules("No water since this morning in Block A.") is None
    assert check_rules("Please send the fire safety team") is None


def test_duplicates_escalate_but_not_to_critical():
    single = score_urgency(make(severity=2), "garbage not collected")
    many = score_urgency(make(severity=2), "garbage not collected", duplicate_count=6)
    assert single.level == "Medium"
    assert many.level == "High"
    assert "6 reports" in many.reason
    huge = score_urgency(make(severity=4, people="large", safety=True), "sewage overflow", duplicate_count=8,
                         hours_since_reported=100)
    assert huge.level == "High"


def test_severity_mapping():
    assert score_urgency(make(severity=1), "fan broken").level == "Low"
    assert score_urgency(make(severity=4), "contaminated water").level == "High"
    assert score_urgency(make(severity=5), "something terrible").level == "Critical"


def test_time_critical_wording_raises_level():
    assert score_urgency(make(severity=3), "wifi down").level == "Medium"
    assert score_urgency(make(severity=3), "wifi down, assignment deadline tonight").level == "High"
