"""Unit tests for app.pii."""

import pandas as pd
import pytest

from app.config import COMPLAINTS_CSV
from app.pii import mask_pii


@pytest.mark.parametrize(
    "text, expected_types, leaked",
    [
        ("You can reach me at priya.sharma12@example.com or 9876543210.", {"EMAIL", "PHONE"}, ["priya", "9876543210"]),
        ("Regards, Suresh Naidu (+91-97980-79359)", {"NAME", "PHONE"}, ["Suresh", "97980"]),
        ("My name is Kavya Reddy, roll no 21B81A0512.", {"NAME", "ID"}, ["Kavya", "21B81A0512"]),
        ("Mera naam Rahul Verma hai, number 98765 43210.", {"NAME", "PHONE"}, ["Rahul", "43210"]),
        ("Naa peru Divya Rao, phone +91 7012345678.", {"NAME", "PHONE"}, ["Divya", "7012345678"]),
        ("- Arjun Gupta, Employee ID EMP4821", {"NAME", "ID"}, ["Arjun", "EMP4821"]),
        ("Please contact Dr. Meena Iyer about this.", {"NAME"}, ["Meena"]),
        ("Generator band hai. Contact Priya 9876501234", {"NAME", "PHONE"}, ["Priya", "9876501234"]),
        ("Please call me at 98765 43210, ask Ravi at the gate.", {"NAME", "PHONE"}, ["Ravi", "43210"]),
    ],
)
def test_masks_expected_pii(text, expected_types, leaked):
    masked, found = mask_pii(text)
    assert {f["type"] for f in found} == expected_types
    for value in leaked:
        assert value not in masked


@pytest.mark.parametrize(
    "text",
    [
        "There is no water supply in Block A Boys Hostel since this morning.",
        "Girls Hostel 2 lo WiFi down lo undi.",
        "Two of my exams are scheduled at the same time in the new timetable.",
        "Room 204 on floor 3 of the PG Hostel has a broken fan.",
    ],
)
def test_no_false_positives_on_locations(text):
    masked, found = mask_pii(text)
    assert found == []
    assert masked == text


def test_dataset_pii_rows_are_masked():
    """Every synthetic row with planted PII must have at least one mask."""
    df = pd.read_csv(COMPLAINTS_CSV)
    pii_rows = df[df.has_pii == 1]
    missed = [t for t in pii_rows.text if not mask_pii(t)[1]]
    assert not missed, missed[:3]
    # And clean rows should rarely trigger masks (allow a tiny false-positive budget).
    clean = df[df.has_pii == 0]
    false_pos = sum(1 for t in clean.text if mask_pii(t)[1])
    assert false_pos <= 0.02 * len(clean)
