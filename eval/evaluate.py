"""Offline evaluation of the full TriageAI pipeline on the synthetic set.

    python eval/evaluate.py            # full run -> eval/metrics.json + confusion matrices
    python eval/evaluate.py --llm      # use Claude for extraction and for the bias rewrites
    python eval/evaluate.py --smoke    # 80 rows, writes to a temp dir (used in CI)

Reports
  * category / sub_issue accuracy
  * urgency accuracy and macro-F1
  * duplicate detection precision / recall / F1 over complaint pairs
    (ground truth: the planted duplicate clusters D01..D25)
  * routing accuracy (recommended department vs true department)
  * bias check: 20 complaints rewritten in different tones and dialects; the
    share whose urgency level stays identical across every rewrite

Offline mode is honest: each complaint is classified by a fallback model that
never saw it, or any report of the same incident, in training (GroupKFold).
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import confusion_matrix, f1_score  # noqa: E402

from app.config import ANTHROPIC_MODEL, COMPLAINTS_CSV, has_anthropic_key  # noqa: E402
from app.db import Complaint, make_session_factory  # noqa: E402
from app.duplicates import DuplicateIndex, resolve_backend  # noqa: E402
from app.extract import Extractor, FallbackClassifier, fallback_extract  # noqa: E402
from app.pii import mask_pii  # noqa: E402
from app.pipeline import TriagePipeline  # noqa: E402
from app.seed import llm_extractions, out_of_fold_extractions  # noqa: E402
from app.taxonomy import URGENCY_LEVELS, load_taxonomy  # noqa: E402
from app.urgency import score_urgency  # noqa: E402
from data.scenarios import LOCATIONS, SCENARIOS  # noqa: E402

EVAL_DIR = ROOT / "eval"


# --------------------------------------------------------------------------- pipeline run


def run_pipeline(df: pd.DataFrame, use_llm: bool, workdir: Path) -> pd.DataFrame:
    masked = [mask_pii(t)[0] for t in df.text]
    extractions = llm_extractions(df, masked) if use_llm else out_of_fold_extractions(df, masked)
    session_factory = make_session_factory(workdir / "eval.db")
    pipeline = TriagePipeline(DuplicateIndex(), Extractor(use_llm=False))
    now = datetime.fromisoformat(df.timestamp.max()) + timedelta(hours=2)
    with session_factory() as session:
        ids = []
        for i, row in df.iterrows():
            c = pipeline.process(session, row.text, row.location, datetime.fromisoformat(row.timestamp),
                                 source="eval", external_id=row.id, extraction=extractions[i], now=now)
            ids.append(c.id)
        session.commit()
        rows = {c.id: c for c in session.query(Complaint).all()}
        out = df.copy()
        out["pred_category"] = [rows[i].ai_category for i in ids]
        out["pred_sub_issue"] = [rows[i].ai_sub_issue for i in ids]
        out["pred_urgency"] = [rows[i].urgency for i in ids]
        out["pred_department"] = [rows[i].suggested_department for i in ids]
        out["manual_triage"] = [rows[i].needs_manual_triage for i in ids]
        out["incident_id"] = [rows[i].incident_id for i in ids]
        out["method"] = [rows[i].extraction_method for i in ids]
    session_factory.kw["bind"].dispose()  # release the SQLite file (Windows locks open files)
    return out


def duplicate_scores(out: pd.DataFrame) -> dict:
    """Pairwise precision/recall: a pair is positive when both complaints share an incident."""
    truth = out.cluster_id.where(out.cluster_id.fillna("").str.startswith("D"), out.id).tolist()
    pred = out.incident_id.tolist()
    tp = fp = fn = 0
    for a, b in itertools.combinations(range(len(out)), 2):
        same_pred, same_true = pred[a] == pred[b], truth[a] == truth[b]
        tp += same_pred and same_true
        fp += same_pred and not same_true
        fn += same_true and not same_pred
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    # Cluster-level view: how many planted clusters were (mostly) recovered as one incident.
    recovered = 0
    clusters = out[out.cluster_id.fillna("").str.startswith("D")].groupby("cluster_id")
    for _, g in clusters:
        recovered += g.incident_id.value_counts().iloc[0] / len(g) >= 0.5
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "true_pairs": tp + fn, "predicted_pairs": tp + fp,
            "clusters_recovered": int(recovered), "clusters_total": int(clusters.ngroups)}


def plot_confusion(y_true, y_pred, labels, title, path: Path) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    fig, ax = plt.subplots(figsize=(9, 7.5))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    for i, j in itertools.product(range(len(labels)), range(len(labels))):
        if cm[i, j]:
            ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=8,
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------- bias check

TONE_WRAPPERS = {
    "formal": ("Respected Sir/Madam, I wish to bring the following to your notice. ", " Kindly take necessary action."),
    "angry": ("This is ridiculous!!! ", " Nobody ever does anything here, fix it NOW!!!"),
    "polite": ("Hello, sorry to trouble you. ", " Thank you so much for your help."),
    "casual": ("hey guys ", " pls look into it"),
}


def rule_rewrites(row: pd.Series, rng: random.Random) -> dict[str, str]:
    """Same facts, different tone and dialect. Dialect variants come from the scenario bank,
    so the Hinglish / Telugu-English versions are genuine translations of the same issue."""
    sc = SCENARIOS[row.true_sub_issue]
    alias = rng.choice(LOCATIONS[row.location]["aliases"]) if row.location in LOCATIONS else row.location
    escalator = sc.get("escalator", ("", ""))[0]
    extra = f" {escalator}" if escalator and escalator in row.text else ""
    variants = {"original": row.text}
    for lang, key in (("english", "en"), ("hinglish", "hi"), ("telugu_english", "te")):
        variants[lang] = rng.choice(sc[key]).replace("{loc}", alias) + extra
    base = variants["english"]
    for tone, (pre, post) in TONE_WRAPPERS.items():
        text = pre + base + post
        variants[tone] = text.lower() if tone == "casual" else text
    return variants


def llm_rewrites(row: pd.Series, client) -> dict[str, str] | None:
    import anthropic

    styles = ["formal English", "angry English with exclamation marks", "very polite English",
              "casual English with typos", "Hinglish (Hindi in Latin script mixed with English)",
              "Telugu-English mix (Telugu in Latin script mixed with English)"]
    schema = {"type": "object", "properties": {"rewrites": {"type": "array", "items": {"type": "string"}}},
              "required": ["rewrites"], "additionalProperties": False}
    prompt = ("Rewrite the complaint below once in each of these styles, keeping every fact identical "
              "(same problem, place, severity, number of people). Do not add or remove facts.\n"
              f"Styles (in order): {json.dumps(styles)}\n\nComplaint:\n{row.text}")
    try:
        r = client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=4000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        )
        texts = json.loads(next(b.text for b in r.content if b.type == "text"))["rewrites"]
    except (anthropic.APIError, json.JSONDecodeError, KeyError, StopIteration):
        return None
    if len(texts) != len(styles):
        return None
    return {"original": row.text, **dict(zip(["formal", "angry", "polite", "casual", "hinglish",
                                               "telugu_english"], texts))}


def bias_check(df: pd.DataFrame, use_llm: bool, n: int = 20, seed: int = 7) -> dict:
    rng = random.Random(seed)
    # Stratify the sample across categories so every kind of issue is represented.
    picks = []
    for _, g in df.groupby("true_category"):
        picks.extend(g.sample(min(len(g), max(1, n // 8 + 1)), random_state=seed).index.tolist())
    picks = sorted(rng.sample(picks, min(n, len(picks))))
    sample = df.loc[picks]

    groups = df.cluster_id.fillna(df.id)
    train = df[~groups.isin(groups.loc[picks])]
    model = FallbackClassifier.train([mask_pii(t)[0] for t in train.text], train.true_sub_issue.tolist(),
                                     groups.loc[train.index].tolist())
    extractor = Extractor(fallback=model, use_llm=use_llm)
    client = None
    if use_llm:
        import anthropic

        client = anthropic.Anthropic()

    def run_one(row) -> dict:
        variants = (llm_rewrites(row, client) if client else None) or rule_rewrites(row, rng)
        levels = {}
        for name, text in variants.items():
            masked = mask_pii(text)[0]
            ex = extractor.extract(masked, row.location)
            levels[name] = score_urgency(ex, masked).level  # isolate wording: no duplicates, no ageing
        return {"id": row.id, "true_urgency": row.true_urgency, "levels": levels,
                "consistent": len(set(levels.values())) == 1,
                "rewriter": "claude" if client and "english" not in variants else "rules"}

    with ThreadPoolExecutor(4 if use_llm else 1) as pool:
        results = list(pool.map(run_one, [r for _, r in sample.iterrows()]))
    n_var = max(len(r["levels"]) for r in results)
    return {
        "n_complaints": len(results),
        "n_variants": n_var,
        "consistency": round(sum(r["consistent"] for r in results) / len(results), 4),
        "rewriter": "claude" if any(r["rewriter"] == "claude" for r in results) else "rule-based, scenario bank",
        "inconsistent_examples": [r for r in results if not r["consistent"]][:8],
    }


# --------------------------------------------------------------------------- main


def evaluate(smoke: bool = False, use_llm: bool = False, out_dir: Path | None = None) -> dict:
    t0 = time.time()
    df = pd.read_csv(COMPLAINTS_CSV).sort_values("timestamp").reset_index(drop=True)
    if smoke:
        df = df.head(80).reset_index(drop=True)
    out_dir = out_dir or (Path(tempfile.mkdtemp(prefix="triage-smoke-")) if smoke else EVAL_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        out = run_pipeline(df, use_llm, Path(tmp))

    tax = load_taxonomy()
    metrics = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "claude" if use_llm else "offline fallback (5-fold GroupKFold)",
        "model": ANTHROPIC_MODEL if use_llm else "tfidf+logreg",
        "embeddings": resolve_backend(),
        "n": len(out),
        "category_accuracy": round(float((out.pred_category == out.true_category).mean()), 4),
        "sub_issue_accuracy": round(float((out.pred_sub_issue == out.true_sub_issue).mean()), 4),
        "urgency_accuracy": round(float((out.pred_urgency == out.true_urgency).mean()), 4),
        "urgency_macro_f1": round(float(f1_score(out.true_urgency, out.pred_urgency, average="macro",
                                                 labels=URGENCY_LEVELS, zero_division=0)), 4),
        "urgency_per_class_f1": dict(zip(URGENCY_LEVELS, np.round(f1_score(
            out.true_urgency, out.pred_urgency, average=None, labels=URGENCY_LEVELS, zero_division=0), 4).tolist())),
        "routing_accuracy": round(float((out.pred_department == out.true_department).mean()), 4),
        "manual_triage_rate": round(float(out.manual_triage.mean()), 4),
        "routing_accuracy_when_auto_routed": round(float(
            (out[~out.manual_triage].pred_department == out[~out.manual_triage].true_department).mean()), 4)
        if (~out.manual_triage).any() else None,
        "duplicates": duplicate_scores(out),
    }
    plot_confusion(out.true_category, out.pred_category, tax.categories, "Category confusion matrix",
                   out_dir / "confusion_matrix.png")
    plot_confusion(out.true_urgency, out.pred_urgency, URGENCY_LEVELS, "Urgency confusion matrix",
                   out_dir / "urgency_confusion_matrix.png")
    metrics["bias_check"] = bias_check(pd.read_csv(COMPLAINTS_CSV), use_llm, n=8 if smoke else 20)
    metrics["runtime_seconds"] = round(time.time() - t0, 1)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return {**metrics, "_out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smoke", action="store_true", help="quick run on 80 rows (CI)")
    parser.add_argument("--llm", action="store_true", help="use Claude (needs ANTHROPIC_API_KEY)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.llm and not has_anthropic_key():
        raise SystemExit("--llm requires ANTHROPIC_API_KEY")
    m = evaluate(smoke=args.smoke, use_llm=args.llm, out_dir=args.out)
    d = m["duplicates"]
    print(f"\nTriageAI evaluation ({m['mode']}, n={m['n']}, embeddings={m['embeddings']})")
    print(f"  category accuracy      {m['category_accuracy']:.3f}")
    print(f"  sub_issue accuracy     {m['sub_issue_accuracy']:.3f}")
    print(f"  urgency macro-F1       {m['urgency_macro_f1']:.3f}  (accuracy {m['urgency_accuracy']:.3f})")
    print(f"  routing accuracy       {m['routing_accuracy']:.3f}  (manual triage rate {m['manual_triage_rate']:.2f})")
    print(f"  duplicates P / R / F1  {d['precision']:.3f} / {d['recall']:.3f} / {d['f1']:.3f}"
          f"  ({d['clusters_recovered']}/{d['clusters_total']} clusters recovered)")
    b = m["bias_check"]
    print(f"  bias consistency       {b['consistency']:.0%} of {b['n_complaints']} complaints x "
          f"{b['n_variants']} variants ({b['rewriter']})")
    print(f"  wrote {m['_out_dir']}/metrics.json in {m['runtime_seconds']}s")
    assert 0 <= m["category_accuracy"] <= 1  # smoke assertion for CI


if __name__ == "__main__":
    main()
