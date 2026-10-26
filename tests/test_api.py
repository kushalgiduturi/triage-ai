"""End-to-end API tests with an isolated SQLite DB and hash embeddings."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.db import make_session_factory
from app.duplicates import DuplicateIndex, HashEmbedder
from app.extract import Extractor


@pytest.fixture()
def client(tmp_path: Path):
    main.init_state(
        session_factory=make_session_factory(tmp_path / "test.db"),
        index=DuplicateIndex(HashEmbedder()),
        extractor=Extractor(use_llm=False),
    )
    with TestClient(main.app) as c:
        yield c


def submit(client, text, location="Block A Boys Hostel"):
    r = client.post("/complaints", json={"text": text, "location": location})
    assert r.status_code == 201, r.text
    return r.json()


def test_submit_runs_full_pipeline(client):
    card = submit(client, "My name is Priya Sharma, 9876543210. A student got an electric shock from the "
                          "switchboard in Block A hostel.")
    assert card["status"] == "pending"
    assert "[NAME]" in card["masked_text"] and "[PHONE]" in card["masked_text"]
    assert "9876543210" not in card["masked_text"]
    assert card["urgency"] == "Critical"
    assert card["ai_suggestion"]["reasoning"]
    assert card["disclaimer"] == "AI suggestion only. Human decision required."
    assert [a["action"] for a in card["audit_log"]] == ["ai_triage"]


def test_duplicates_form_incident_and_escalate(client):
    text = "Garbage has not been collected from Block A hostel for four days and bins are overflowing."
    first = submit(client, text)
    for _ in range(5):
        last = submit(client, text)
    assert last["incident_id"] == first["incident_id"]
    assert last["incident"]["report_count"] == 6
    assert any(s["label"] == "likely_duplicate" for s in last["similar"])
    refreshed = client.get(f"/complaints/{first['id']}").json()
    assert refreshed["urgency"] in ("High", "Critical")


def test_queue_sorted_by_urgency(client):
    submit(client, "Two tube lights and the ceiling fan in my room are not working.")
    submit(client, "There is a fire in the kitchen area of the main mess, smoke is coming out.", "Main Mess")
    items = client.get("/complaints").json()["items"]
    ranks = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
    assert [ranks[i["urgency"]] for i in items] == sorted((ranks[i["urgency"]] for i in items), reverse=True)
    assert client.get("/complaints", params={"urgency": "Critical"}).json()["total"] >= 1


def test_review_actions_and_audit(client):
    c = submit(client, "WiFi has been completely down in Block A hostel since yesterday evening.")
    r = client.post(f"/complaints/{c['id']}/review", json={
        "action": "edit", "reviewer": "Asha (warden)", "category": "IT and WiFi", "sub_issue": "wifi_down",
        "department": "IT Services", "urgency": "High", "notes": "Confirmed with students."})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "edited"
    assert body["human_decision"]["department"] == "IT Services"
    edit = body["audit_log"][-1]
    assert edit["action"] == "edit" and edit["reviewer"] == "Asha (warden)"
    assert edit["new_value"]["urgency"] == "High"

    bad = client.post(f"/complaints/{c['id']}/review", json={
        "action": "edit", "reviewer": "Asha", "category": "IT and WiFi", "sub_issue": "harassment"})
    assert bad.status_code == 422
    invented = client.post(f"/complaints/{c['id']}/review", json={
        "action": "edit", "reviewer": "Asha", "department": "Ministry of Magic"})
    assert invented.status_code == 422

    other = submit(client, "Internet speed in Block A hostel is extremely slow in the evenings.")
    merged = client.post(f"/complaints/{other['id']}/review", json={
        "action": "merge", "reviewer": "Asha", "merge_into": c["id"]}).json()
    assert merged["status"] == "merged" and merged["incident_id"] == c["incident_id"]

    rejected = client.post(f"/complaints/{other['id']}/review", json={"action": "reject", "reviewer": "Asha"})
    assert rejected.json()["status"] == "rejected"


def test_metrics_and_taxonomy(client):
    submit(client, "Rice served at the main mess today was half cooked.", "Main Mess")
    m = client.get("/metrics").json()
    assert {"accuracy_vs_ground_truth", "human_agreement", "distributions", "bias_by_language_style"} <= set(m)
    tax = client.get("/taxonomy").json()
    assert len(tax["categories"]) == 8
    assert client.get("/health").json()["status"] == "ok"
