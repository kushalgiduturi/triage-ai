"""End-to-end triage pipeline: mask -> extract -> duplicates -> urgency -> routing -> store.

Nothing here dispatches work to a department. The pipeline only writes an AI
*suggestion* with status "pending"; a human reviewer decides (see app.main).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import AuditLog, Complaint, Incident
from app.duplicates import DuplicateIndex, Match
from app.extract import Extraction, Extractor
from app.pii import mask_pii
from app.routing import route
from app.taxonomy import URGENCY_LEVELS, URGENCY_RANK
from app.urgency import score_urgency

SYSTEM_ACTOR = "TriageAI"


def extraction_from_row(c: Complaint) -> Extraction:
    """Rebuild the stored AI extraction (used when an incident grows and urgency is rescored)."""
    return Extraction.model_construct(
        category=c.ai_category, sub_issue=c.ai_sub_issue, location=c.ai_location,
        one_line_summary=c.ai_summary, safety_risk=c.ai_safety_risk, people_affected=c.ai_people_affected,
        sentiment=c.ai_sentiment, severity=c.ai_severity, confidence=c.confidence,
        reasoning=c.ai_reasoning, method=c.extraction_method,
    )


def hours_between(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds() / 3600)


class TriagePipeline:
    def __init__(self, index: DuplicateIndex, extractor: Extractor | None = None) -> None:
        self.index = index
        self.extractor = extractor or Extractor()

    # ------------------------------------------------------------------ main entry point

    def process(
        self,
        session: Session,
        text: str,
        location: str | None = None,
        reported_at: datetime | None = None,
        *,
        source: str = "live",
        external_id: str | None = None,
        truth: dict | None = None,
        extraction: Extraction | None = None,
        contact: str | None = None,
        now: datetime | None = None,
    ) -> Complaint:
        """Run the whole pipeline for one complaint and persist the result (status = pending)."""
        reported_at = reported_at or datetime.now()
        now = now or datetime.now()
        masked, pii = mask_pii(text)
        if extraction is None:
            extraction = self.extractor.extract(masked, location)
        place = location or extraction.location

        # Duplicates: search before adding this complaint to the index.
        vector = self.index.embed_complaint(masked, extraction.category, extraction.sub_issue)
        matches = self.index.search(vector, extraction.category, place, reported_at, sub_issue=extraction.sub_issue)
        incident = self._incident_for(session, matches, extraction, place, reported_at)

        routing = route(extraction)
        complaint = Complaint(
            external_id=external_id, source=source, text=text, masked_text=masked,
            pii_types=sorted({p["type"] for p in pii}), location=place, reported_at=reported_at, contact=contact,
            ai_category=extraction.category, ai_sub_issue=extraction.sub_issue, ai_location=extraction.location,
            ai_summary=extraction.one_line_summary, ai_safety_risk=extraction.safety_risk,
            ai_people_affected=extraction.people_affected, ai_sentiment=extraction.sentiment,
            ai_severity=extraction.severity, ai_reasoning=extraction.reasoning,
            extraction_method=extraction.method,
            urgency="Low", urgency_score=0, urgency_reason="", urgency_rule=None,
            department=routing.department, suggested_department=routing.suggested_department,
            sla_hours=routing.sla_hours, next_action=routing.next_action, confidence=routing.confidence,
            needs_manual_triage=routing.needs_manual_triage, routing_reason=routing.reason,
            incident=incident, status="pending",
            **{f"true_{k}": v for k, v in (truth or {}).items()},
        )
        session.add(complaint)
        incident.report_count += 1
        incident.last_reported = max(incident.last_reported, reported_at)
        session.flush()  # assigns complaint.id

        self.index.add(complaint.id, vector, extraction.category, place, reported_at, extraction.sub_issue)
        self.rescore_incident(session, incident, now)
        session.add(AuditLog(
            complaint_id=complaint.id, action="ai_triage", reviewer=SYSTEM_ACTOR, timestamp=now,
            new_value=self.suggestion(complaint),
            notes=f"Pipeline suggestion ({extraction.method}); {len(matches)} similar complaint(s) found.",
        ))
        return complaint

    # ------------------------------------------------------------------ incidents

    def _incident_for(self, session: Session, matches: list[Match], extraction: Extraction,
                      place: str, reported_at: datetime) -> Incident:
        for m in matches:
            if m.label != "likely_duplicate":
                continue
            other = session.get(Complaint, m.complaint_id)
            if other is not None and other.incident is not None and other.status != "rejected":
                return other.incident
        incident = Incident(
            title=extraction.one_line_summary, category=extraction.category, sub_issue=extraction.sub_issue,
            location=place or "unknown", report_count=0, urgency="Low",
            first_reported=reported_at, last_reported=reported_at,
        )
        session.add(incident)
        return incident

    def rescore_incident(self, session: Session, incident: Incident, now: datetime) -> None:
        """Recompute urgency for every pending report in the incident.

        Each report is scored with the incident's report count; then all reports
        inherit the highest level in the incident (one incident, one priority).
        """
        members = [c for c in incident.complaints if c.status not in ("rejected",)]
        count = len(members)
        incident.report_count = count
        best_level, best_score = "Low", 0
        for c in members:
            if c.status != "pending":
                continue
            result = score_urgency(extraction_from_row(c), c.masked_text, count, hours_between(c.reported_at, now))
            c.urgency, c.urgency_score, c.urgency_reason, c.urgency_rule = (
                result.level, result.score, result.reason, result.rule)
        for c in members:
            level = c.final_urgency or c.urgency
            if URGENCY_RANK[level] > URGENCY_RANK[best_level] or (level == best_level and c.urgency_score > best_score):
                best_level, best_score = level, c.urgency_score
        incident.urgency = best_level
        for c in members:
            if c.status == "pending" and URGENCY_RANK[c.urgency] < URGENCY_RANK[best_level]:
                c.urgency_reason += f" Raised to {best_level}: a linked report in the same incident is {best_level}."
                c.urgency = best_level
                c.urgency_score = max(c.urgency_score, best_score)

    @staticmethod
    def suggestion(c: Complaint) -> dict:
        return {
            "category": c.ai_category, "sub_issue": c.ai_sub_issue, "urgency": c.urgency,
            "urgency_score": c.urgency_score, "department": c.suggested_department,
            "queue": c.department, "confidence": c.confidence, "incident_id": c.incident_id,
        }

    # ------------------------------------------------------------------ helpers

    def rebuild_index(self, session: Session) -> int:
        """Re-embed all stored complaints (used when the FAISS file is missing)."""
        rows = session.scalars(select(Complaint).order_by(Complaint.id)).all()
        if not rows:
            return 0
        for c in rows:
            category, sub_issue = c.final_category or c.ai_category, c.final_sub_issue or c.ai_sub_issue
            vector = self.index.embed_complaint(c.masked_text, category, sub_issue)
            self.index.add(c.id, vector, category, c.location, c.reported_at, sub_issue)
        return len(rows)


def urgency_sort_key(c: Complaint) -> tuple:
    """Queue order: highest urgency first, then oldest first (waiting longest)."""
    level = c.final_urgency or c.urgency
    return (-URGENCY_RANK.get(level, 0), c.reported_at)


__all__ = ["TriagePipeline", "urgency_sort_key", "URGENCY_LEVELS"]
