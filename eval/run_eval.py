"""Compare three systems on the 400-complaint synthetic set (generated with seed 42).

    python eval/run_eval.py --system rule      # rule-only keyword baseline
    python eval/run_eval.py --system tfidf     # TF-IDF + logistic regression (5-fold GroupKFold)
    python eval/run_eval.py --system llm       # TriageAI LLM pipeline (PROVIDER=claude|ollama)
    python eval/run_eval.py --system all --metrics category,urgency

Every system runs through the same pipeline (PII masking, duplicates, urgency, routing)
one complaint at a time, so latency is end to end. Outputs:
    eval/results/<system>.json              metrics
    eval/results/<system>_predictions.csv   one row per complaint (raw outputs)
    docs/confusion_<system>.png             category confusion matrix

If the LLM provider is not reachable the llm system is recorded as "not measured" with the
reason. Nothing is estimated.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from app.baselines import rule_extract  # noqa: E402
from app.config import ANTHROPIC_MODEL, COMPLAINTS_CSV, OLLAMA_MODEL, PROVIDER  # noqa: E402
from app.db import Complaint, make_session_factory  # noqa: E402
from app.duplicates import DUPLICATE_THRESHOLD, DuplicateIndex, resolve_backend  # noqa: E402
from app.extract import FallbackClassifier, Extractor, fallback_extract, llm_available  # noqa: E402
from app.pii import mask_pii  # noqa: E402
from app.pipeline import TriagePipeline  # noqa: E402
from app.taxonomy import URGENCY_LEVELS, load_taxonomy  # noqa: E402
from app.urgency import score_urgency  # noqa: E402
from eval.evaluate import duplicate_scores, plot_confusion, rule_rewrites  # noqa: E402

RESULTS_DIR = ROOT / "eval" / "results"
DOCS_DIR = ROOT / "docs"
ALL_METRICS = ["category", "urgency", "dupes", "routing", "latency", "cost", "bias"]
# USD per million tokens (input, output). Source: Anthropic pricing as of 2026-10.
PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}


# --------------------------------------------------------------------------- extractors per system


def make_extract_fn(system: str, df: pd.DataFrame, masked: list[str]):
    """Returns (extract(i) -> Extraction, info dict). For tfidf each row uses a model that never saw it."""
    if system == "rule":
        return (lambda i: rule_extract(masked[i], df.location.iloc[i])), {"training": "none"}
    if system == "tfidf":
        groups = df.cluster_id.fillna(df.id).tolist()
        fold_model: dict[int, FallbackClassifier] = {}
        t0 = time.perf_counter()
        for train_idx, test_idx in GroupKFold(5).split(df, groups=groups):
            model = FallbackClassifier.train([masked[i] for i in train_idx], df.true_sub_issue.iloc[train_idx].tolist(),
                                             [groups[i] for i in train_idx])
            for i in test_idx:
                fold_model[i] = model
        info = {"training": "5-fold GroupKFold by incident", "train_seconds_total": round(time.perf_counter() - t0, 2)}
        return (lambda i: fallback_extract(fold_model[i], masked[i], df.location.iloc[i])), info
    extractor = Extractor(use_llm=True, provider=PROVIDER)
    return (lambda i: extractor.extract(masked[i], df.location.iloc[i])), {"extractor": extractor}


# --------------------------------------------------------------------------- run


def run_system(system: str, df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    masked = [mask_pii(t)[0] for t in df.text]
    extract, info = make_extract_fn(system, df, masked)
    now = datetime.fromisoformat(df.timestamp.max()) + timedelta(hours=2)
    rows, latencies, extract_lat = [], [], []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        session_factory = make_session_factory(Path(tmp) / "eval.db")
        pipeline = TriagePipeline(DuplicateIndex(), Extractor(use_llm=False))
        pipeline.index.embed("warm up")  # model load is not part of per-complaint latency
        with session_factory() as session:
            ids = []
            for i, row in df.iterrows():
                t0 = time.perf_counter()
                extraction = extract(i)
                t1 = time.perf_counter()
                c = pipeline.process(session, row.text, row.location, datetime.fromisoformat(row.timestamp),
                                     source="eval", external_id=row.id, extraction=extraction, now=now)
                session.flush()
                latencies.append(time.perf_counter() - t0)
                extract_lat.append(t1 - t0)
                ids.append(c.id)
            session.commit()
            by_id = {c.id: c for c in session.query(Complaint).all()}
            for i, cid in zip(df.index, ids):
                c = by_id[cid]
                rows.append({
                    "id": df.id[i], "true_category": df.true_category[i], "pred_category": c.ai_category,
                    "true_sub_issue": df.true_sub_issue[i], "pred_sub_issue": c.ai_sub_issue,
                    "true_urgency": df.true_urgency[i], "pred_urgency": c.urgency,
                    "true_department": df.true_department[i], "pred_department": c.suggested_department,
                    "confidence": c.confidence, "manual_triage": c.needs_manual_triage,
                    "cluster_id": df.cluster_id[i], "incident_id": c.incident_id, "method": c.extraction_method,
                })
        session_factory.kw["bind"].dispose()
    out = pd.DataFrame(rows)
    out["latency_s"] = latencies
    out["extract_latency_s"] = extract_lat
    return out, info


def bias_consistency(system: str, df: pd.DataFrame, n: int = 20, seed: int = 7) -> dict:
    """Same issue rewritten in 8 tones / dialects; share of complaints whose urgency never changes."""
    rng = random.Random(seed)
    picks = []
    for _, g in df.groupby("true_category"):
        picks.extend(g.sample(min(len(g), max(1, n // 8 + 1)), random_state=seed).index.tolist())
    picks = sorted(rng.sample(picks, min(n, len(picks))))
    groups = df.cluster_id.fillna(df.id)
    if system == "tfidf":
        train = df[~groups.isin(groups.loc[picks])]
        model = FallbackClassifier.train([mask_pii(t)[0] for t in train.text], train.true_sub_issue.tolist(),
                                         groups.loc[train.index].tolist())
        extract = lambda text, loc: fallback_extract(model, text, loc)  # noqa: E731
    elif system == "rule":
        extract = rule_extract
    else:
        llm = Extractor(use_llm=True, provider=PROVIDER)
        extract = llm.extract
    consistent, examples = 0, []
    for _, row in df.loc[picks].iterrows():
        levels = {}
        for name, text in rule_rewrites(row, rng).items():
            masked = mask_pii(text)[0]
            levels[name] = score_urgency(extract(masked, row.location), masked).level
        if len(set(levels.values())) == 1:
            consistent += 1
        else:
            examples.append({"id": row.id, "levels": levels})
    return {"n_complaints": len(picks), "n_variants": 8, "consistency": round(consistent / len(picks), 4),
            "rewriter": "rule-based, scenario bank", "inconsistent": examples}


def metrics_for(system: str, out: pd.DataFrame, info: dict, df: pd.DataFrame, wanted: list[str]) -> dict:
    tax = load_taxonomy()
    m: dict = {"system": system, "n": len(out), "dataset": "data/complaints.csv (400 synthetic, seed 42)",
               "embeddings": resolve_backend(), "duplicate_threshold": DUPLICATE_THRESHOLD,
               "measured_at": datetime.now().isoformat(timespec="seconds")}
    if system == "llm":
        m["provider"] = PROVIDER
        m["model"] = OLLAMA_MODEL if PROVIDER == "ollama" else ANTHROPIC_MODEL
        m["llm_fallbacks"] = int((out.method == "fallback").sum())
    if "category" in wanted:
        m["category_accuracy"] = round(float((out.pred_category == out.true_category).mean()), 4)
        m["sub_issue_accuracy"] = round(float((out.pred_sub_issue == out.true_sub_issue).mean()), 4)
        plot_confusion(out.true_category, out.pred_category, tax.categories,
                       f"Category confusion matrix: {system}", DOCS_DIR / f"confusion_{system}.png")
    if "urgency" in wanted:
        m["urgency_macro_f1"] = round(float(f1_score(out.true_urgency, out.pred_urgency, average="macro",
                                                     labels=URGENCY_LEVELS, zero_division=0)), 4)
        m["urgency_accuracy"] = round(float((out.pred_urgency == out.true_urgency).mean()), 4)
    if "dupes" in wanted:
        d = duplicate_scores(out.rename(columns={}))
        m["duplicate_precision"], m["duplicate_recall"], m["duplicate_f1"] = d["precision"], d["recall"], d["f1"]
        m["duplicate_clusters_recovered"] = f"{d['clusters_recovered']}/{d['clusters_total']}"
    if "routing" in wanted:
        m["routing_accuracy"] = round(float((out.pred_department == out.true_department).mean()), 4)
        m["manual_triage_rate"] = round(float(out.manual_triage.mean()), 4)
    if "latency" in wanted:
        lat = out.latency_s.tolist()
        m["latency_mean_s"] = round(statistics.mean(lat), 4)
        m["latency_p50_s"] = round(statistics.median(lat), 4)
        m["latency_p95_s"] = round(sorted(lat)[int(0.95 * (len(lat) - 1))], 4)
        m["extraction_latency_mean_s"] = round(statistics.mean(out.extract_latency_s), 4)
        if "train_seconds_total" in info:
            m["train_seconds_total"] = info["train_seconds_total"]
    if "cost" in wanted:
        if system in ("rule", "tfidf"):
            m["cost_per_1000_usd"] = 0.0
            m["cost_note"] = "No API calls; runs on local CPU."
        elif PROVIDER == "ollama":
            m["cost_per_1000_usd"] = 0.0
            m["cost_note"] = f"Local Ollama model ({OLLAMA_MODEL}); no API cost, hardware not priced."
        else:
            usage = [u for u in info["extractor"]._llm.usage if u["input_tokens"] is not None] if info["extractor"]._llm else []
            price_in, price_out = PRICES.get(ANTHROPIC_MODEL, (None, None))
            if usage and price_in is not None:
                cost = sum(u["input_tokens"] * price_in + u["output_tokens"] * price_out for u in usage) / 1e6
                m["cost_per_1000_usd"] = round(cost / len(out) * 1000, 2)
                m["tokens_in_mean"] = round(statistics.mean(u["input_tokens"] for u in usage), 1)
                m["tokens_out_mean"] = round(statistics.mean(u["output_tokens"] for u in usage), 1)
            else:
                m["cost_per_1000_usd"] = None
                m["cost_note"] = "not measured: no token usage recorded or model price unknown"
    if "bias" in wanted:
        m["bias_check"] = bias_consistency(system, df)
    return m


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--system", choices=["rule", "tfidf", "llm", "all"], default="all")
    parser.add_argument("--metrics", default=",".join(ALL_METRICS), help=f"comma list of {ALL_METRICS}")
    args = parser.parse_args()
    wanted = [w.strip() for w in args.metrics.split(",") if w.strip()]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(COMPLAINTS_CSV).sort_values("timestamp").reset_index(drop=True)
    systems = ["rule", "tfidf", "llm"] if args.system == "all" else [args.system]
    for system in systems:
        path = RESULTS_DIR / f"{system}.json"
        if system == "llm" and not llm_available(PROVIDER):
            reason = ("PROVIDER=ollama but no Ollama server answered at OLLAMA_URL" if PROVIDER == "ollama"
                      else "PROVIDER=claude but ANTHROPIC_API_KEY is not set")
            result = {"system": "llm", "provider": PROVIDER, "status": "not measured", "reason": reason,
                      "measured_at": datetime.now().isoformat(timespec="seconds")}
            path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"[llm] not measured: {reason}")
            continue
        t0 = time.time()
        out, info = run_system(system, df)
        out.to_csv(RESULTS_DIR / f"{system}_predictions.csv", index=False)
        merged = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        merged.pop("status", None)
        merged.pop("reason", None)
        merged.update(metrics_for(system, out, info, df, wanted))
        path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        shown = {k: v for k, v in merged.items() if not isinstance(v, (dict, list))}
        print(f"[{system}] ({time.time() - t0:.0f}s) " + json.dumps(shown))


if __name__ == "__main__":
    main()
