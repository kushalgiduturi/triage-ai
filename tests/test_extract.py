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


def test_ollama_provider_uses_schema_and_validates():
    """PROVIDER=ollama: same masked prompt and JSON schema, answer validated like Claude's."""
    import httpx

    seen = {}

    def handler(request):
        body = json.loads(request.content)
        seen.update(body)
        return httpx.Response(200, json={"message": {"content": json.dumps(VALID)},
                                         "prompt_eval_count": 900, "eval_count": 120})

    llm = ex.OllamaExtractor(model="test-model", url="http://ollama.test")
    llm.client = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    result = llm.extract("no water in [NAME]'s room in Block A", "Block A Boys Hostel")
    assert result.sub_issue == "no_water_supply" and result.method == "llm"
    assert seen["model"] == "test-model" and seen["format"]["properties"]["category"]["enum"]
    assert 0 <= seen["options"]["temperature"] <= 0.2 and seen["stream"] is False
    assert "[NAME]" in seen["messages"][1]["content"]
    assert llm.usage == [{"input_tokens": 900, "output_tokens": 120}]


def _mock_ollama(monkeypatch, handler):
    import httpx

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "get", lambda url, **kw: httpx.Client(transport=transport).get(url))


def test_ollama_available_requires_installed_model(monkeypatch):
    import httpx

    _mock_ollama(monkeypatch, lambda r: httpx.Response(200, json={"models": [{"name": "qwen2.5:3b"}]}))
    assert ex.ollama_available("http://ollama.test", "qwen2.5:3b")
    assert not ex.ollama_available("http://ollama.test", "llama3.1:8b")
    _mock_ollama(monkeypatch, lambda r: httpx.Response(200, json={"models": [{"name": "mistral:latest"}]}))
    assert ex.ollama_available("http://ollama.test", "mistral")


def test_ollama_unreachable_is_unavailable(monkeypatch):
    import httpx

    def down(request):
        raise httpx.ConnectError("refused")

    _mock_ollama(monkeypatch, down)
    assert not ex.ollama_available("http://ollama.test", "qwen2.5:3b")


def test_ollama_two_invalid_answers_fall_back(fallback_model):
    """Two schema-invalid Ollama answers: the offline classifier decides, method='fallback'."""
    import httpx

    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"message": {"content": json.dumps({**VALID, "category": "Weather"})}})

    llm = ex.OllamaExtractor(model="test-model", url="http://ollama.test")
    llm.client = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    extractor = ex.Extractor(fallback=fallback_model, use_llm=True, provider="ollama")
    extractor._llm = llm
    result = extractor.extract("There is no water supply in Block C hostel since this morning.", "Block C Boys Hostel")
    assert len(calls) == 2
    assert result.method == "fallback" and result.category == "Water and Plumbing"


def test_provider_selection():
    assert isinstance(ex.make_llm("ollama"), ex.OllamaExtractor)
    assert ex.llm_available("ollama") is False  # the test suite sets TRIAGE_DISABLE_LLM=1
    assert ex.llm_model_name("ollama") == ex.OLLAMA_MODEL
