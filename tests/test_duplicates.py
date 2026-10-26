"""Tests for app.duplicates (hash embeddings so no model download is needed)."""

from datetime import datetime, timedelta

from app.duplicates import DuplicateIndex, HashEmbedder, normalize_location

T0 = datetime(2026, 10, 20, 9, 0)


def build():
    idx = DuplicateIndex(HashEmbedder())
    texts = {
        1: ("There is no water supply in Block A hostel since this morning.", "Water and Plumbing", "Block A Boys Hostel"),
        2: ("WiFi has been completely down in the CSE block since yesterday.", "IT and WiFi", "CSE Block"),
    }
    for cid, (text, cat, loc) in texts.items():
        idx.add(cid, idx.embed(text), cat, loc, T0)
    return idx


def test_near_identical_is_likely_duplicate():
    idx = build()
    v = idx.embed("There is no water supply in Block A hostel since this morning!!")
    matches = idx.search(v, "Water and Plumbing", "Block A Boys Hostel", T0 + timedelta(hours=2))
    assert matches[0].complaint_id == 1
    assert matches[0].label == "likely_duplicate"
    assert matches[0].same_location and matches[0].same_category


def test_different_location_is_at_most_related():
    idx = build()
    v = idx.embed("There is no water supply in Block A hostel since this morning.")
    matches = idx.search(v, "Water and Plumbing", "Block C Boys Hostel", T0)
    assert matches and matches[0].label == "related"


def test_old_reports_are_not_duplicates():
    idx = build()
    v = idx.embed("There is no water supply in Block A hostel since this morning.")
    matches = idx.search(v, "Water and Plumbing", "Block A Boys Hostel", T0 + timedelta(days=10))
    assert matches[0].label == "related"


def test_exclude_self_and_persistence(tmp_path):
    idx = build()
    v = idx.index.reconstruct(1)
    assert all(m.complaint_id != 1 for m in idx.search(v, "Water and Plumbing", "Block A Boys Hostel", T0, exclude_id=1))
    path = tmp_path / "x.index"
    idx.save(path)
    loaded = DuplicateIndex.load(path, HashEmbedder())
    assert len(loaded) == 2 and loaded.meta[2].category == "IT and WiFi"


def test_normalize_location():
    assert normalize_location("Block-A  Boys Hostel") == "blockaboyshostel"
    assert normalize_location("unknown") == ""


def test_different_sub_issue_is_at_most_related():
    idx = DuplicateIndex(HashEmbedder())
    text = "Problem in the main mess kitchen, very dirty and students are sick."
    idx.add(1, idx.embed_complaint(text, "Hostel and Mess", "mess_hygiene"), "Hostel and Mess", "Main Mess", T0,
            "mess_hygiene")
    v = idx.embed_complaint(text, "Hostel and Mess", "food_poisoning")
    matches = idx.search(v, "Hostel and Mess", "Main Mess", T0, sub_issue="food_poisoning")
    assert matches and matches[0].label == "related"


def test_resolve_backend_explicit_and_auto():
    from app.duplicates import resolve_backend

    assert resolve_backend("onnx") == "onnx"
    assert resolve_backend("hash") == "hash"
    assert resolve_backend("auto") in ("sentence-transformers", "onnx")


def test_index_from_another_backend_is_not_reused(tmp_path):
    idx = build()
    path = tmp_path / "x.index"
    idx.save(path)

    class OtherBackend(HashEmbedder):
        name = "onnx"

    assert len(DuplicateIndex.load(path, OtherBackend())) == 0  # rebuilt from the DB instead of mixing vectors
    assert len(DuplicateIndex.load(path, HashEmbedder())) == 2
