"""SQLite persistence with SQLAlchemy 2.0.

Tables
  complaints  - original + masked text, the AI suggestion (category, urgency, routing,
                reasoning, confidence), the human decision, status, and (synthetic rows
                only) ground-truth labels used for evaluation
  incidents   - groups of duplicate complaints; report_count feeds urgency
  audit_log   - every human action (and the initial AI suggestion) with old / new values
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import DB_PATH

STATUSES = ("pending", "approved", "edited", "rejected", "merged")


class Base(DeclarativeBase):
    pass


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(80))
    sub_issue: Mapped[str] = mapped_column(String(80))
    location: Mapped[str] = mapped_column(String(120))
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    urgency: Mapped[str] = mapped_column(String(20), default="Low")
    first_reported: Mapped[datetime] = mapped_column(DateTime)
    last_reported: Mapped[datetime] = mapped_column(DateTime)

    complaints: Mapped[list["Complaint"]] = relationship(back_populates="incident")


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="live")
    text: Mapped[str] = mapped_column(Text)
    masked_text: Mapped[str] = mapped_column(Text)
    pii_types: Mapped[list] = mapped_column(JSON, default=list)  # types only; raw values are never stored twice
    location: Mapped[str] = mapped_column(String(120), default="")
    reported_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # ---- AI suggestion
    ai_category: Mapped[str] = mapped_column(String(80))
    ai_sub_issue: Mapped[str] = mapped_column(String(80))
    ai_location: Mapped[str] = mapped_column(String(120))
    ai_summary: Mapped[str] = mapped_column(Text)
    ai_safety_risk: Mapped[bool] = mapped_column(Boolean)
    ai_people_affected: Mapped[str] = mapped_column(String(20))
    ai_sentiment: Mapped[str] = mapped_column(String(20))
    ai_severity: Mapped[int] = mapped_column(Integer)
    ai_reasoning: Mapped[str] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String(20))
    urgency: Mapped[str] = mapped_column(String(20))
    urgency_score: Mapped[int] = mapped_column(Integer)
    urgency_reason: Mapped[str] = mapped_column(Text)
    urgency_rule: Mapped[str | None] = mapped_column(String(60), nullable=True)
    department: Mapped[str] = mapped_column(String(80))  # queue (may be "Needs manual triage")
    suggested_department: Mapped[str] = mapped_column(String(80))
    sla_hours: Mapped[int] = mapped_column(Integer)
    next_action: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    needs_manual_triage: Mapped[bool] = mapped_column(Boolean, default=False)
    routing_reason: Mapped[str] = mapped_column(Text, default="")
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"), nullable=True)

    # ---- human decision
    status: Mapped[str] = mapped_column(String(20), default="pending")
    final_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    final_sub_issue: Mapped[str | None] = mapped_column(String(80), nullable=True)
    final_urgency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    final_department: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ---- ground truth (synthetic data only, used for metrics; never shown to the model)
    true_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    true_sub_issue: Mapped[str | None] = mapped_column(String(80), nullable=True)
    true_urgency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    true_department: Mapped[str | None] = mapped_column(String(80), nullable=True)
    true_cluster_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    incident: Mapped[Incident | None] = relationship(back_populates="complaints")
    audit: Mapped[list["AuditLog"]] = relationship(back_populates="complaint", order_by="AuditLog.id")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"))
    action: Mapped[str] = mapped_column(String(30))  # ai_triage | approve | edit | reject | merge
    reviewer: Mapped[str] = mapped_column(String(80))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    complaint: Mapped[Complaint] = relationship(back_populates="audit")


def make_engine(path: Path = DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def make_session_factory(path: Path = DB_PATH) -> sessionmaker:
    engine = make_engine(path)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
