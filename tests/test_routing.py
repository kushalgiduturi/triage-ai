"""Tests for app.routing and the routing table."""

from app.extract import Extraction
from app.routing import route, route_for
from app.taxonomy import load_taxonomy


def make(confidence: float, category="IT and WiFi", sub_issue="wifi_down") -> Extraction:
    return Extraction(
        category=category, sub_issue=sub_issue, location="CSE Block", one_line_summary="WiFi down",
        safety_risk=False, people_affected="group", sentiment="frustrated", severity=3,
        confidence=confidence, reasoning="test",
    )


def test_table_has_expected_shape():
    tax = load_taxonomy()
    assert len(tax.categories) == 8
    assert all(len(tax.sub_issues(c)) >= 5 for c in tax.categories)
    assert tax.manual_triage_department not in tax.departments


def test_confident_route():
    result = route(make(0.9))
    assert result.department == "IT Services"
    assert not result.needs_manual_triage
    assert result.sla_hours == 4


def test_low_confidence_goes_to_manual_triage():
    result = route(make(0.4))
    assert result.needs_manual_triage
    assert result.department == "Needs manual triage"
    assert result.suggested_department == "IT Services"


def test_sub_issue_specific_department():
    assert route(make(0.95, "Hostel and Mess", "food_poisoning")).department == "Campus Health Centre"
    assert route(make(0.95, "Safety and Harassment", "harassment")).department == "Internal Complaints Committee"


def test_route_for_rejects_unknown():
    assert route_for("IT and WiFi", "harassment") is None
    assert route_for("IT and WiFi", "slow_internet").department == "IT Services"
