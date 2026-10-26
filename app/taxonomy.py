"""Loads the fixed taxonomy / routing table from config/departments.yaml.

Every other module reads categories, sub_issues and departments from here so
there is exactly one place where the taxonomy is defined.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import DEPARTMENTS_YAML

URGENCY_LEVELS: list[str] = ["Low", "Medium", "High", "Critical"]
URGENCY_RANK: dict[str, int] = {u: i for i, u in enumerate(URGENCY_LEVELS)}


@dataclass(frozen=True)
class Route:
    """One row of the routing table."""

    category: str
    sub_issue: str
    department: str
    sla_hours: int
    next_action: str
    base_severity: int


@dataclass(frozen=True)
class Taxonomy:
    routes: dict[tuple[str, str], Route]
    manual_triage_department: str
    confidence_threshold: float

    @property
    def categories(self) -> list[str]:
        return sorted({c for c, _ in self.routes})

    def sub_issues(self, category: str | None = None) -> list[str]:
        if category is None:
            return sorted({s for _, s in self.routes})
        return [s for c, s in self.routes if c == category]

    @property
    def departments(self) -> list[str]:
        return sorted({r.department for r in self.routes.values()})

    def category_of(self, sub_issue: str) -> str | None:
        for c, s in self.routes:
            if s == sub_issue:
                return c
        return None

    def get(self, category: str, sub_issue: str) -> Route | None:
        return self.routes.get((category, sub_issue))


@lru_cache(maxsize=4)
def load_taxonomy(path: str | Path = DEPARTMENTS_YAML) -> Taxonomy:
    """Parse departments.yaml into a Taxonomy (cached)."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    routes: dict[tuple[str, str], Route] = {}
    for category, subs in raw["categories"].items():
        for sub_issue, row in subs.items():
            routes[(category, sub_issue)] = Route(
                category=category,
                sub_issue=sub_issue,
                department=row["department"],
                sla_hours=int(row["sla_hours"]),
                next_action=row["next_action"],
                base_severity=int(row["base_severity"]),
            )
    return Taxonomy(
        routes=routes,
        manual_triage_department=raw.get("manual_triage_department", "Needs manual triage"),
        confidence_threshold=float(raw.get("confidence_threshold", 0.6)),
    )
