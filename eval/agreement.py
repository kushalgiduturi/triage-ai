"""Human agreement and override rate from the audit log.

    python eval/agreement.py                 # reads data/triage.db
    python eval/agreement.py --db path.db

Override rate = (edited + rejected + merged) / all human review actions.
Only rows written by a reviewer count; the AI's own "ai_triage" rows are ignored.
The number is only meaningful on a database where real reviewers have worked.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.config import DB_PATH  # noqa: E402
from app.db import AuditLog, make_session_factory  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    if not args.db.exists():
        raise SystemExit(f"No database at {args.db}. Run `make seed` (or python -m app.seed) first.")
    with make_session_factory(args.db)() as session:
        rows = session.scalars(select(AuditLog).where(AuditLog.action != "ai_triage")).all()
    actions = Counter(r.action for r in rows)
    total = sum(actions.values())
    overrides = actions["edit"] + actions["reject"] + actions["merge"]
    result = {
        "database": str(args.db),
        "human_review_actions": total,
        "by_action": dict(actions),
        "reviewers": sorted({r.reviewer for r in rows}),
        "override_rate": round(overrides / total, 4) if total else None,
        "agreement_rate": round(actions["approve"] / total, 4) if total else None,
        "note": "not measured: no human review actions in this database" if not total else
                "computed from the audit log; meaningful only if these were real reviewer decisions",
    }
    out = ROOT / "eval" / "results" / "agreement.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
