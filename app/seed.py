"""Seed the database with the synthetic complaints and pre-run the pipeline.

    python -m app.seed            # rebuild data/triage.db + FAISS index
    python -m app.seed --llm      # use Claude for extraction (needs ANTHROPIC_API_KEY)
    python -m app.seed --if-empty # no-op when a seeded DB already exists (used by start.sh)

Offline (default when no API key): the fallback classifier is evaluated
honestly with 5-fold GroupKFold, so each seeded complaint is classified by a
model that never saw it or any duplicate of it during training.
"""

from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pandas as pd
from sklearn.model_selection import GroupKFold
from sqlalchemy import func, select

from app.config import COMPLAINTS_CSV, DB_PATH, FAISS_INDEX_PATH, has_anthropic_key
from app.db import Complaint, make_session_factory
from app.duplicates import DuplicateIndex
from app.extract import Extraction, Extractor, FallbackClassifier, fallback_extract
from app.pii import mask_pii
from app.pipeline import TriagePipeline

log = logging.getLogger("seed")


def out_of_fold_extractions(df: pd.DataFrame, masked: list[str], n_splits: int = 5) -> list[Extraction]:
    """Fallback extractions where each row is predicted by a model trained without its incident."""
    groups = df.cluster_id.fillna(df.id).tolist()
    result: list[Extraction | None] = [None] * len(df)
    for train_idx, test_idx in GroupKFold(n_splits).split(df, groups=groups):
        model = FallbackClassifier.train([masked[i] for i in train_idx],
                                         df.true_sub_issue.iloc[train_idx].tolist(),
                                         [groups[i] for i in train_idx])
        for i in test_idx:
            result[i] = fallback_extract(model, masked[i], df.location.iloc[i])
    return result  # type: ignore[return-value]


def llm_extractions(df: pd.DataFrame, masked: list[str], workers: int = 8) -> list[Extraction]:
    extractor = Extractor(use_llm=True)
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(lambda i: extractor.extract(masked[i], df.location.iloc[i]), range(len(df))))


def seed(use_llm: bool = False, csv_path=COMPLAINTS_CSV) -> int:
    for path in (DB_PATH, FAISS_INDEX_PATH, FAISS_INDEX_PATH.with_suffix(".meta.json")):
        path.unlink(missing_ok=True)
    df = pd.read_csv(csv_path).sort_values("timestamp").reset_index(drop=True)
    masked = [mask_pii(t)[0] for t in df.text]

    t0 = time.time()
    extractions = llm_extractions(df, masked) if use_llm else out_of_fold_extractions(df, masked)
    print(f"Extraction done in {time.time() - t0:.1f}s ({'Claude' if use_llm else 'offline classifier'})")

    # Seeded data is "as of" shortly after the last complaint, so ageing looks realistic.
    now = datetime.fromisoformat(df.timestamp.max()) + timedelta(hours=2)
    session_factory = make_session_factory()
    pipeline = TriagePipeline(DuplicateIndex(), Extractor(use_llm=False))
    t0 = time.time()
    with session_factory() as session:
        for i, row in df.iterrows():
            pipeline.process(
                session, row.text, row.location, datetime.fromisoformat(row.timestamp),
                source="seed", external_id=row.id, extraction=extractions[i], now=now,
                truth={"category": row.true_category, "sub_issue": row.true_sub_issue,
                       "urgency": row.true_urgency, "department": row.true_department,
                       "cluster_id": row.cluster_id if isinstance(row.cluster_id, str) else None},
            )
        session.commit()
        n = session.scalar(select(func.count(Complaint.id)))
    pipeline.index.save()
    # Also persist a fallback model trained on all data for live complaints.
    groups = df.cluster_id.fillna(df.id).tolist()
    FallbackClassifier.train(masked, df.true_sub_issue.tolist(), groups).save()
    print(f"Seeded {n} complaints into {DB_PATH} in {time.time() - t0:.1f}s")
    return n


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="use Claude for extraction")
    parser.add_argument("--if-empty", action="store_true", help="skip if the DB already has rows")
    args = parser.parse_args()
    if args.if_empty and DB_PATH.exists() and FAISS_INDEX_PATH.exists():
        with make_session_factory()() as session:
            if session.scalar(select(func.count(Complaint.id))):
                print("Database already seeded; skipping.")
                return
    if args.llm and not has_anthropic_key():
        raise SystemExit("--llm requires ANTHROPIC_API_KEY")
    seed(use_llm=args.llm)


if __name__ == "__main__":
    main()
