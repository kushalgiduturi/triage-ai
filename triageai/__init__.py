"""TriageAI as a library.

    from triageai import Pipeline
    pipe = Pipeline(provider="claude")
    result = pipe.triage("GH-2 mein kal raat se light nahi hai", location="Girls Hostel 2")
    print(result["category"], result["urgency"], result["department"])

The AI recommends. A human always decides: `triage()` returns a suggestion and never
dispatches anything.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from app.db import make_session_factory
from app.duplicates import DuplicateIndex
from app.extract import Extractor

__all__ = ["Pipeline"]


class Pipeline:
    """Self-contained triage pipeline with its own temporary database and duplicate index.

    provider: "claude" (default) or "ollama". Without a reachable provider the offline
    TF-IDF classifier is used and each result says so in `method`.
    """

    def __init__(self, provider: str = "claude", db_path: str | Path | None = None) -> None:
        from app.pipeline import TriagePipeline

        self._tmp = None if db_path else tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(db_path) if db_path else Path(self._tmp.name) / "triageai.db"
        self._sessions = make_session_factory(path)
        self._pipeline = TriagePipeline(DuplicateIndex(), Extractor(provider=provider))

    def triage(self, text: str, location: str | None = None, reported_at: datetime | None = None) -> dict:
        """Run masking, extraction, duplicate search, urgency and routing on one complaint."""
        with self._sessions() as session:
            c = self._pipeline.process(session, text, location, reported_at)
            session.commit()
            return {
                "id": c.id,
                "masked_text": c.masked_text,
                "category": c.ai_category,
                "sub_issue": c.ai_sub_issue,
                "summary": c.ai_summary,
                "urgency": c.urgency,
                "urgency_reason": c.urgency_reason,
                "department": c.suggested_department,
                "sla_hours": c.sla_hours,
                "next_action": c.next_action,
                "confidence": c.confidence,
                "needs_manual_triage": c.needs_manual_triage,
                "incident_id": c.incident_id,
                "incident_reports": c.incident.report_count if c.incident else 1,
                "method": c.extraction_method,
                "status": c.status,
            }
