"""Central configuration: paths, model names and environment switches."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = Path(os.getenv("TRIAGE_DATA_DIR", ROOT_DIR / "data"))
MODELS_DIR = Path(os.getenv("TRIAGE_MODELS_DIR", ROOT_DIR / "models"))
DEPARTMENTS_YAML = ROOT_DIR / "config" / "departments.yaml"
COMPLAINTS_CSV = ROOT_DIR / "data" / "complaints.csv"
FRONTEND_DIST = Path(os.getenv("TRIAGE_FRONTEND_DIST", ROOT_DIR / "frontend" / "dist"))

DB_PATH = Path(os.getenv("TRIAGE_DB_PATH", DATA_DIR / "triage.db"))
FAISS_INDEX_PATH = Path(os.getenv("TRIAGE_FAISS_PATH", DATA_DIR / "faiss.index"))

# Claude settings. The key is only ever read from the environment.
ANTHROPIC_MODEL = os.getenv("TRIAGE_CLAUDE_MODEL", "claude-opus-5-5")
LLM_ENABLED = os.getenv("TRIAGE_DISABLE_LLM", "0") != "1"

# Embeddings. "hash" is a dependency-light fallback used by unit tests / CI.
EMBEDDING_MODEL = os.getenv("TRIAGE_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
EMBEDDING_BACKEND = os.getenv("TRIAGE_EMBEDDINGS", "sentence-transformers")  # or "hash"


def has_anthropic_key() -> bool:
    """True when a Claude API key is configured and LLM use is not disabled."""
    return LLM_ENABLED and bool(os.getenv("ANTHROPIC_API_KEY"))
