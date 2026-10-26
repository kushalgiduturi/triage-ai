"""Tests for the rule-only baseline."""

from app.baselines import rule_extract


def test_rule_baseline_matches_keywords():
    e = rule_extract("A student got an electric shock from the switchboard in Block A hostel.", "Block A Boys Hostel")
    assert (e.category, e.sub_issue) == ("Electricity", "electric_shock_hazard")
    assert e.safety_risk and e.confidence == 1.0


def test_rule_baseline_code_mixed():
    assert rule_extract("GH-1 lo morning nunchi water raavatledu").sub_issue == "no_water_supply"
    assert rule_extract("mess ke khana mein keeda mila").sub_issue == "mess_hygiene"


def test_rule_baseline_no_match_goes_to_manual_triage():
    e = rule_extract("Something is wrong, please help.")
    assert e.confidence == 0.0 and "no keyword rule matched" in e.reasoning
