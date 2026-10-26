"""The README library example must keep working."""

import os

from triageai import Pipeline


def test_readme_library_example():
    pipe = Pipeline(provider="claude")  # no key in tests: falls back to the offline classifier
    result = pipe.triage("GH-2 mein kal raat se light nahi hai. Mera naam Sneha Reddy hai, 98480 12345",
                         location="Girls Hostel 2")
    from app.taxonomy import load_taxonomy

    assert load_taxonomy().get(result["category"], result["sub_issue"]) is not None
    assert result["status"] == "pending" and result["urgency"] in ("Low", "Medium", "High", "Critical")
    assert "[NAME]" in result["masked_text"] and "98480" not in result["masked_text"]
    assert result["method"] == ("llm" if os.getenv("ANTHROPIC_API_KEY") else "fallback")
