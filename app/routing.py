"""Routing: (category, sub_issue) -> department, SLA and standard next action.

The table lives in config/departments.yaml. The LLM can only output taxonomy
values (schema enums + Pydantic validation), and this module only ever returns
departments that exist in that table. Low-confidence results go to the
"Needs manual triage" queue, keeping the best guess visible to the reviewer.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.extract import Extraction
from app.taxonomy import load_taxonomy


@dataclass(frozen=True)
class RoutingResult:
    department: str  # queue the complaint lands in (may be the manual-triage queue)
    suggested_department: str  # best table match, always shown to the reviewer
    sla_hours: int
    next_action: str
    confidence: float
    needs_manual_triage: bool
    reason: str


def route(extraction: Extraction) -> RoutingResult:
    tax = load_taxonomy()
    row = tax.get(extraction.category, extraction.sub_issue)
    if row is None:  # cannot happen after validation, but never invent a department
        return RoutingResult(
            department=tax.manual_triage_department, suggested_department=tax.manual_triage_department,
            sla_hours=24, next_action="Reviewer to classify manually.", confidence=0.0,
            needs_manual_triage=True, reason="Category/sub_issue not found in the routing table.",
        )
    confidence = round(float(extraction.confidence), 3)
    manual = confidence < tax.confidence_threshold
    reason = (f"Routing table: {extraction.category} / {extraction.sub_issue} -> {row.department} "
              f"(SLA {row.sla_hours}h).")
    if manual:
        reason += (f" Confidence {confidence:.2f} is below {tax.confidence_threshold:.2f}, "
                   f"so it is queued for manual triage.")
    return RoutingResult(
        department=tax.manual_triage_department if manual else row.department,
        suggested_department=row.department,
        sla_hours=row.sla_hours,
        next_action=row.next_action,
        confidence=confidence,
        needs_manual_triage=manual,
        reason=reason,
    )


def route_for(category: str, sub_issue: str) -> RoutingResult | None:
    """Lookup used when a reviewer edits category/sub_issue (confidence = 1, human decided)."""
    row = load_taxonomy().get(category, sub_issue)
    if row is None:
        return None
    return RoutingResult(row.department, row.department, row.sla_hours, row.next_action, 1.0, False,
                         "Set by human reviewer.")
