"""Tests for app.extract: schema validation, retry-once, and offline fallback."""

import json

import pytest
from pydantic import ValidationError

from app import extract as ex

VALID = {
    "category": "Water and Plumbing",
    "sub_issue": "no_water_supply",
    "location": "Block A Boys Hostel",
    "one_line_summary": "No water supply in Block A hostel since morning.",
    "safety_risk": False,
    "people_affected": "large",
    "sentiment": "frustrated",
    "severity": 4,
    "confidence": 0.93,
    "reasoning": "Mentions taps dry and no water since morning.",
}


@pytest.fixture(scope="module")
def fallback_model():
    return ex.FallbackClassifier.load_or_train()


def test_schema_rejects_sub_issue_from_wrong_category():
    with pytest.raises(ValidationError):
        ex.Extraction(**{**VALID, "sub_issue": "wifi_down"})


def test_schema_rejects_unknown_category():
    with pytest.raises(ValidationError):
        ex.Extraction(**{**VALID, "category": "Weather"})


class FakeLLM(ex.LLMExtractor):
    """LLMExtractor with the network call replaced by canned answers."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    def _call(self, user_content):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_llm_retries_once_on_invalid_json():
    llm = FakeLLM(["{not json", json.dumps(VALID)])
    result = llm.extract("no water in block a")
    assert llm.calls == 2
    assert result.sub_issue == "no_water_supply" and result.method == "llm"


def test_extractor_falls_back_when_llm_fails(fallback_model):
    extractor = ex.Extractor(fallback=fallback_model, use_llm=True)
    extractor._llm = FakeLLM([RuntimeError("API down")])
    result = extractor.extract("There is no water supply in Block C hostel since this morning.", "Block C Boys Hostel")
    assert result.method == "fallback"
    assert result.category == "Water and Plumbing"


def test_extractor_falls_back_after_two_invalid_answers(fallback_model):
    extractor = ex.Extractor(fallback=fallback_model, use_llm=True)
    extractor._llm = FakeLLM(["{}", json.dumps({**VALID, "sub_issue": "harassment"})])
    result = extractor.extract("No internet in the library, the WiFi shows connected but no internet.")
    assert result.method == "fallback"
    assert result.category == "IT and WiFi"


def test_fallback_fields(fallback_model):
    result = ex.fallback_extract(
        fallback_model, "A student got an electric shock from the switchboard in Block A hostel. We are scared."
    )
    assert result.category == "Electricity"
    assert result.safety_risk is True
    assert result.sentiment == "worried"
    assert 0 <= result.confidence <= 1
