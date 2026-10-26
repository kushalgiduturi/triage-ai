"""TriageAI FastAPI backend.

Run:  uvicorn app.main:app --port 8000

The API only stores AI *recommendations*. Nothing is ever dispatched
automatically: a complaint leaves "pending" only through POST /complaints/{id}/review,
which requires a named human reviewer and is written to the audit log.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import FRONTEND_DIST, PROVIDER, ROOT_DIR
from app.db import AuditLog, Complaint, Incident, make_session_factory
from app.duplicates import DuplicateIndex
from app.extract import Extractor, llm_available
from app.language import detect_style
from app.pipeline import TriagePipeline, urgency_sort_key
from app.routing import route_for
from app.taxonomy import URGENCY_LEVELS, URGENCY_RANK, load_taxonomy

log = logging.getLogger("triageai")
EVAL_METRICS = ROOT_DIR / "eval" / "metrics.json"


class State:
    """Process-wide singletons, created at startup (or injected by tests)."""

    session_factory: sessionmaker | None = None
    pipeline: TriagePipeline | None = None


state = State()


def init_state(session_factory: sessionmaker | None = None, index: DuplicateIndex | None = None,
               extractor: Extractor | None = None) -> None:
    state.session_factory = session_factory or make_session_factory()
    state.pipeline = TriagePipeline(index or DuplicateIndex.load(), extractor)
    with state.session_factory() as session:
        n_rows = session.scalar(select(func.count(Complaint.id)))
        if n_rows and len(state.pipeline.index) == 0:
            log.info("FAISS index missing; re-embedding %d complaints", n_rows)
            state.pipeline.rebuild_index(session)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if state.pipeline is None:
        init_state()
    yield
    state.pipeline.index.save()


app = FastAPI(
    title="TriageAI",
    description="AI complaint triage. The AI only recommends; every decision is made by a human reviewer.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def get_session():
    with state.session_factory() as session:
        yield session


# --------------------------------------------------------------------------- schemas


class ComplaintIn(BaseModel):
    text: str = Field(min_length=5, max_length=5000)
    location: str | None = Field(default=None, max_length=120)
    contact: str | None = Field(default=None, max_length=200, description="Optional; stored for the reviewer, never sent to the AI")
    reported_at: datetime | None = None


class ReviewIn(BaseModel):
    action: Literal["approve", "edit", "reject", "merge"]
    reviewer: str = Field(min_length=2, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)
    # edit fields (any subset)
    category: str | None = None
    sub_issue: str | None = None
    urgency: Literal["Low", "Medium", "High", "Critical"] | None = None
    department: str | None = None
    # merge target: another complaint id whose incident this one joins
    merge_into: int | None = None


def summary(c: Complaint) -> dict:
    return {
        "id": c.id,
        "external_id": c.external_id,
        "reported_at": c.reported_at.isoformat(),
        "location": c.location,
        "summary": c.ai_summary,
        "category": c.final_category or c.ai_category,
        "sub_issue": c.final_sub_issue or c.ai_sub_issue,
        "urgency": c.final_urgency or c.urgency,
        "urgency_score": c.urgency_score,
        "department": c.final_department or c.department,
        "suggested_department": c.final_department or c.suggested_department,
        "confidence": c.confidence,
        "needs_manual_triage": c.needs_manual_triage,
        "status": c.status,
        "incident_id": c.incident_id,
        "incident_reports": c.incident.report_count if c.incident else 1,
        "extraction_method": c.extraction_method,
    }


def card(c: Complaint) -> dict:
    """Full triage card for the detail view."""
    return {
        **summary(c),
        "text": c.text,
        "masked_text": c.masked_text,
        "contact": c.contact,
        "pii_types": c.pii_types,
        "ai_suggestion": {
            "category": c.ai_category,
            "sub_issue": c.ai_sub_issue,
            "location": c.ai_location,
            "summary": c.ai_summary,
            "safety_risk": c.ai_safety_risk,
            "people_affected": c.ai_people_affected,
            "sentiment": c.ai_sentiment,
            "severity": c.ai_severity,
            "reasoning": c.ai_reasoning,
            "urgency": c.urgency,
            "urgency_score": c.urgency_score,
            "urgency_reason": c.urgency_reason,
            "urgency_rule": c.urgency_rule,
            "department": c.suggested_department,
            "queue": c.department,
            "sla_hours": c.sla_hours,
            "next_action": c.next_action,
            "confidence": c.confidence,
            "routing_reason": c.routing_reason,
            "method": c.extraction_method,
        },
        "human_decision": {
            "category": c.final_category,
            "sub_issue": c.final_sub_issue,
            "urgency": c.final_urgency,
            "department": c.final_department,
            "reviewer": c.reviewer,
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
            "notes": c.review_notes,
        },
        "audit_log": [
            {"action": a.action, "reviewer": a.reviewer, "timestamp": a.timestamp.isoformat(),
             "old_value": a.old_value, "new_value": a.new_value, "notes": a.notes}
            for a in c.audit
        ],
        "disclaimer": "AI suggestion only. Human decision required.",
    }


def get_complaint(session: Session, complaint_id: int) -> Complaint:
    c = session.get(Complaint, complaint_id)
    if c is None:
        raise HTTPException(404, f"Complaint {complaint_id} not found")
    return c


# --------------------------------------------------------------------------- endpoints


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    return {
        "status": "ok",
        "complaints": session.scalar(select(func.count(Complaint.id))),
        "llm_enabled": llm_available(),
        "provider": PROVIDER,
        "embeddings": state.pipeline.index.embedder.name,
        "edition": {"sentence-transformers": "full", "onnx": "lite"}.get(state.pipeline.index.embedder.name, "test"),
        "indexed": len(state.pipeline.index),
    }


@app.get("/taxonomy")
def taxonomy() -> dict:
    tax = load_taxonomy()
    return {
        "categories": {c: tax.sub_issues(c) for c in tax.categories},
        "departments": tax.departments + [tax.manual_triage_department],
        "urgency_levels": URGENCY_LEVELS,
        "statuses": ["pending", "approved", "edited", "rejected", "merged"],
    }


@app.get("/locations")
def locations(session: Session = Depends(get_session)) -> list[str]:
    """Known locations (for the submit form's dropdown)."""
    return sorted({loc for loc in session.scalars(select(Complaint.location)).all() if loc})


@app.post("/complaints", status_code=201)
def submit_complaint(body: ComplaintIn, session: Session = Depends(get_session)) -> dict:
    """Run the full pipeline on a new complaint. The result is a pending suggestion."""
    complaint = state.pipeline.process(session, body.text, body.location, body.reported_at, source="live",
                                       contact=body.contact)
    session.commit()
    state.pipeline.index.save()
    return detail(complaint.id, session)


@app.get("/complaints")
def list_complaints(
    session: Session = Depends(get_session),
    category: str | None = None,
    urgency: str | None = None,
    status: str | None = None,
    department: str | None = None,
    search: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict:
    """Review queue sorted by urgency (Critical first), then oldest first."""
    rows = session.scalars(select(Complaint)).all()

    def keep(c: Complaint) -> bool:
        s = summary(c)
        return ((not category or s["category"] == category) and (not urgency or s["urgency"] == urgency)
                and (not status or s["status"] == status) and (not department or s["department"] == department)
                and (not search or search.lower() in c.masked_text.lower()))

    rows = sorted(filter(keep, rows), key=urgency_sort_key)
    return {"total": len(rows), "items": [summary(c) for c in rows[offset:offset + limit]]}


@app.get("/complaints/{complaint_id}")
def detail(complaint_id: int, session: Session = Depends(get_session)) -> dict:
    """Full triage card plus similar / duplicate complaints."""
    c = get_complaint(session, complaint_id)
    index = state.pipeline.index
    similar = []
    if complaint_id in index.meta:
        vector = index.index.reconstruct(complaint_id)
        for m in index.search(vector, c.final_category or c.ai_category, c.location, c.reported_at,
                              exclude_id=complaint_id, sub_issue=c.final_sub_issue or c.ai_sub_issue):
            other = session.get(Complaint, m.complaint_id)
            if other is None:
                continue
            similar.append({
                **summary(other), "similarity": m.similarity, "score": m.score, "label": m.label,
                "same_incident": other.incident_id == c.incident_id, "masked_text": other.masked_text,
            })
    incident = None
    if c.incident:
        incident = {
            "id": c.incident.id, "title": c.incident.title, "report_count": c.incident.report_count,
            "urgency": c.incident.urgency, "location": c.incident.location,
            "first_reported": c.incident.first_reported.isoformat(),
            "last_reported": c.incident.last_reported.isoformat(),
            "member_ids": [m.id for m in c.incident.complaints],
        }
    return {**card(c), "similar": similar, "incident": incident}


@app.post("/complaints/{complaint_id}/review")
def review(complaint_id: int, body: ReviewIn, session: Session = Depends(get_session)) -> dict:
    """Record a human decision. This is the only way a complaint leaves 'pending'."""
    c = get_complaint(session, complaint_id)
    tax = load_taxonomy()
    old = {
        "status": c.status, "category": c.final_category or c.ai_category,
        "sub_issue": c.final_sub_issue or c.ai_sub_issue, "urgency": c.final_urgency or c.urgency,
        "department": c.final_department or c.suggested_department, "incident_id": c.incident_id,
    }

    if body.action == "approve":
        c.final_category, c.final_sub_issue = old["category"], old["sub_issue"]
        c.final_urgency, c.final_department = old["urgency"], old["department"]
        c.status = "approved"

    elif body.action == "edit":
        category = body.category or old["category"]
        sub_issue = body.sub_issue or (old["sub_issue"] if category == old["category"] else None)
        if sub_issue is None or tax.get(category, sub_issue) is None:
            raise HTTPException(422, f"sub_issue {sub_issue!r} is not valid for category {category!r}")
        changed_route = (category, sub_issue) != (old["category"], old["sub_issue"])
        default_dept = route_for(category, sub_issue).department if changed_route else old["department"]
        department = body.department or default_dept
        if department not in tax.departments:
            raise HTTPException(422, f"Unknown department {department!r}; choose one from /taxonomy")
        c.final_category, c.final_sub_issue = category, sub_issue
        c.final_urgency = body.urgency or old["urgency"]
        c.final_department = department
        c.status = "edited"

    elif body.action == "reject":
        c.status = "rejected"

    elif body.action == "merge":
        target_id = body.merge_into
        if target_id is None:
            raise HTTPException(422, "merge requires merge_into (the complaint to merge with)")
        target = get_complaint(session, target_id)
        if target.id == c.id:
            raise HTTPException(422, "Cannot merge a complaint into itself")
        if target.incident is None:
            raise HTTPException(422, "Target complaint has no incident")
        old_incident = c.incident
        c.incident = target.incident
        session.flush()
        now = datetime.now()
        state.pipeline.rescore_incident(session, target.incident, now)
        if old_incident is not None and old_incident.id != target.incident.id:
            session.refresh(old_incident)
            if not old_incident.complaints:
                session.delete(old_incident)
            else:
                state.pipeline.rescore_incident(session, old_incident, now)
        c.final_category, c.final_sub_issue = target.final_category or target.ai_category, \
            target.final_sub_issue or target.ai_sub_issue
        c.final_urgency = target.incident.urgency
        c.final_department = target.final_department or target.suggested_department
        c.status = "merged"

    c.reviewer = body.reviewer
    c.reviewed_at = datetime.now()
    c.review_notes = body.notes
    new = {
        "status": c.status, "category": c.final_category or c.ai_category,
        "sub_issue": c.final_sub_issue or c.ai_sub_issue, "urgency": c.final_urgency or c.urgency,
        "department": c.final_department or c.suggested_department, "incident_id": c.incident_id,
    }
    session.add(AuditLog(complaint_id=c.id, action=body.action, reviewer=body.reviewer,
                         timestamp=c.reviewed_at, old_value=old, new_value=new, notes=body.notes))
    session.commit()
    return detail(c.id, session)


@app.get("/audit")
def audit_log(session: Session = Depends(get_session), include_ai: bool = False,
              limit: int = Query(500, ge=1, le=5000)) -> dict:
    """Global audit log, newest first. By default only human actions (not the AI's initial suggestions)."""
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if not include_ai:
        query = query.where(AuditLog.action != "ai_triage")
    return {"items": [
        {"id": a.id, "complaint_id": a.complaint_id, "timestamp": a.timestamp.isoformat(), "reviewer": a.reviewer,
         "action": a.action, "old_value": a.old_value, "new_value": a.new_value, "notes": a.notes}
        for a in session.scalars(query).all()
    ]}


@app.get("/export.csv")
def export_csv(session: Session = Depends(get_session), status: str | None = None):
    """Download triage records as CSV (AI suggestion and human decision side by side)."""
    import csv
    import io

    from fastapi.responses import Response

    rows = session.scalars(select(Complaint).order_by(Complaint.id)).all()
    if status:
        rows = [c for c in rows if c.status == status]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "reported_at", "location", "masked_text", "ai_category", "ai_sub_issue", "ai_urgency",
                     "ai_department", "confidence", "status", "final_category", "final_urgency",
                     "final_department", "reviewer", "reviewed_at", "incident_id"])
    for c in rows:
        writer.writerow([c.id, c.reported_at.isoformat(), c.location, c.masked_text, c.ai_category, c.ai_sub_issue,
                         c.urgency, c.suggested_department, c.confidence, c.status, c.final_category,
                         c.final_urgency, c.final_department, c.reviewer,
                         c.reviewed_at.isoformat() if c.reviewed_at else "", c.incident_id])
    # Masked text only: the export is meant to be shared, so raw complaint text stays in the database.
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=triageai_export.csv"})


@app.get("/incidents")
def incidents(session: Session = Depends(get_session), min_reports: int = 2) -> dict:
    rows = session.scalars(select(Incident).where(Incident.report_count >= min_reports)).all()
    rows = sorted(rows, key=lambda i: (-URGENCY_RANK[i.urgency], -i.report_count))
    return {"items": [
        {"id": i.id, "title": i.title, "category": i.category, "location": i.location,
         "report_count": i.report_count, "urgency": i.urgency,
         "first_reported": i.first_reported.isoformat(), "last_reported": i.last_reported.isoformat(),
         "member_ids": [c.id for c in i.complaints]}
        for i in rows
    ]}


@app.get("/metrics")
def metrics(session: Session = Depends(get_session)) -> dict:
    """Accuracy vs synthetic ground truth, human-agreement stats, distributions and bias check."""
    rows = session.scalars(select(Complaint)).all()
    labelled = [c for c in rows if c.true_category]

    def rate(items, pred) -> float | None:
        items = list(items)
        return round(sum(1 for c in items if pred(c)) / len(items), 4) if items else None

    accuracy = {
        "n_labelled": len(labelled),
        "category_accuracy": rate(labelled, lambda c: c.ai_category == c.true_category),
        "sub_issue_accuracy": rate(labelled, lambda c: c.ai_sub_issue == c.true_sub_issue),
        "urgency_accuracy": rate(labelled, lambda c: c.urgency == c.true_urgency),
        "routing_accuracy": rate(labelled, lambda c: c.suggested_department == c.true_department),
        "manual_triage_rate": rate(rows, lambda c: c.needs_manual_triage),
    }

    reviewed = [c for c in rows if c.status in ("approved", "edited")]
    human = {
        "n_reviewed": len([c for c in rows if c.status != "pending"]),
        "n_approved": sum(c.status == "approved" for c in rows),
        "n_edited": sum(c.status == "edited" for c in rows),
        "n_rejected": sum(c.status == "rejected" for c in rows),
        "n_merged": sum(c.status == "merged" for c in rows),
        "agreement_rate": rate(reviewed, lambda c: c.status == "approved"),
        "category_agreement": rate(reviewed, lambda c: c.final_category == c.ai_category),
        "urgency_agreement": rate(reviewed, lambda c: c.final_urgency == c.urgency),
        "department_agreement": rate(reviewed, lambda c: c.final_department == c.suggested_department),
    }

    by_style: dict[str, list[Complaint]] = {}
    for c in rows:
        by_style.setdefault(detect_style(c.text), []).append(c)
    bias = {
        style: {
            "n": len(items),
            "mean_urgency_score": round(sum(c.urgency_score for c in items) / len(items), 1),
            "critical_rate": rate(items, lambda c: c.urgency == "Critical"),
            "manual_triage_rate": rate(items, lambda c: c.needs_manual_triage),
            "category_accuracy": rate([c for c in items if c.true_category],
                                      lambda c: c.ai_category == c.true_category),
            "urgency_accuracy": rate([c for c in items if c.true_urgency], lambda c: c.urgency == c.true_urgency),
        }
        for style, items in sorted(by_style.items())
    }

    incident_rows = session.scalars(select(Incident).where(Incident.report_count >= 2)).all()
    evaluation = json.loads(EVAL_METRICS.read_text(encoding="utf-8")) if EVAL_METRICS.exists() else None
    return {
        "accuracy_vs_ground_truth": accuracy,
        "human_agreement": human,
        "distributions": {
            "category": dict(Counter(c.final_category or c.ai_category for c in rows)),
            "urgency": dict(Counter(c.final_urgency or c.urgency for c in rows)),
            "status": dict(Counter(c.status for c in rows)),
            "department": dict(Counter(c.final_department or c.department for c in rows)),
            "extraction_method": dict(Counter(c.extraction_method for c in rows)),
        },
        "incidents": {
            "multi_report_incidents": len(incident_rows),
            "complaints_in_multi_report_incidents": sum(i.report_count for i in incident_rows),
            "largest": sorted(({"id": i.id, "title": i.title, "location": i.location, "reports": i.report_count,
                                "urgency": i.urgency} for i in incident_rows),
                              key=lambda x: -x["reports"])[:10],
        },
        "bias_by_language_style": bias,
        "offline_evaluation": evaluation,
    }


# --------------------------------------------------------------------------- frontend

# The built React app (frontend/dist) is served from "/" so the whole product runs on one port.
# Mounted last: every API route above takes precedence. The UI uses hash routes (#/complaints/12),
# so browser routes never collide with API paths.
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
