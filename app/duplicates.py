"""Duplicate / related complaint detection with sentence embeddings + FAISS.

Each complaint's masked text is embedded (paraphrase-multilingual-MiniLM-L12-v2,
L2-normalised so inner product = cosine similarity) and stored in a FAISS index.
For a new complaint we retrieve the top-5 neighbours and score them:

    score = cosine + 0.05 if same category + 0.05 if same location

    score > 0.85        -> "likely_duplicate"
    0.65 <= score <= .85 -> "related"

Two extra guards (documented choice): if both complaints name *different* known
locations, or were filed more than 7 days apart, they can be "related" at most.
"No water in Block A" and "No water in Block C" read almost identically but are
different incidents.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import faiss
import numpy as np

from app.config import EMBEDDING_BACKEND, EMBEDDING_MODEL, FAISS_INDEX_PATH

DUPLICATE_THRESHOLD = 0.85
RELATED_THRESHOLD = 0.65
CATEGORY_BOOST = 0.05
LOCATION_BOOST = 0.05
DUPLICATE_WINDOW_DAYS = 7
TOP_K = 5


# --------------------------------------------------------------------------- embedders


class Embedder:
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device="cpu")
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
        return vecs.astype("float32")


class HashEmbedder(Embedder):
    """Character n-gram hashing vectors. Fast, no download; used in unit tests / CI."""

    def __init__(self, dim: int = 2048) -> None:
        from sklearn.feature_extraction.text import HashingVectorizer

        self.dim = dim
        self.vec = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=dim,
                                     alternate_sign=False, norm="l2")

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.vec.transform([t.lower() for t in texts]).toarray().astype("float32")


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    """Process-wide embedder (the transformer model is loaded once)."""
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            _embedder = HashEmbedder() if EMBEDDING_BACKEND == "hash" else SentenceTransformerEmbedder()
        return _embedder


# --------------------------------------------------------------------------- index


def normalize_location(location: str | None) -> str:
    if not location or location.strip().lower() in {"unknown", "none", "n/a", ""}:
        return ""
    return re.sub(r"[^a-z0-9]", "", location.lower())


@dataclass
class Match:
    complaint_id: int
    similarity: float  # raw cosine
    score: float  # after boosts
    label: str  # "likely_duplicate" | "related"
    same_category: bool
    same_location: bool


@dataclass
class _Meta:
    category: str
    location: str
    timestamp: str


class DuplicateIndex:
    """FAISS inner-product index keyed by complaint id, plus the metadata used for boosts."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or get_embedder()
        self.index = faiss.IndexIDMap2(faiss.IndexFlatIP(self.embedder.dim))
        self.meta: dict[int, _Meta] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return self.index.ntotal

    def embed(self, text: str) -> np.ndarray:
        return self.embedder.encode([text])[0]

    def add(self, complaint_id: int, vector: np.ndarray, category: str, location: str, timestamp: datetime) -> None:
        with self._lock:
            if complaint_id in self.meta:
                self.index.remove_ids(np.array([complaint_id], dtype="int64"))
            self.index.add_with_ids(vector.reshape(1, -1).astype("float32"), np.array([complaint_id], dtype="int64"))
            self.meta[complaint_id] = _Meta(category, normalize_location(location), timestamp.isoformat())

    def search(
        self,
        vector: np.ndarray,
        category: str,
        location: str,
        timestamp: datetime,
        k: int = TOP_K,
        exclude_id: int | None = None,
    ) -> list[Match]:
        """Top-k neighbours scored and labelled; neighbours below RELATED_THRESHOLD are dropped."""
        if self.index.ntotal == 0:
            return []
        with self._lock:
            sims, ids = self.index.search(vector.reshape(1, -1).astype("float32"), min(k + 1, self.index.ntotal))
        loc = normalize_location(location)
        matches: list[Match] = []
        for sim, cid in zip(sims[0], ids[0]):
            cid = int(cid)
            if cid == -1 or cid == exclude_id or cid not in self.meta:
                continue
            meta = self.meta[cid]
            same_cat = meta.category == category
            same_loc = bool(loc) and meta.location == loc
            score = float(sim) + CATEGORY_BOOST * same_cat + LOCATION_BOOST * same_loc
            days_apart = abs((timestamp - datetime.fromisoformat(meta.timestamp)).total_seconds()) / 86400
            different_place = bool(loc) and bool(meta.location) and not same_loc
            if score > DUPLICATE_THRESHOLD and not different_place and days_apart <= DUPLICATE_WINDOW_DAYS:
                label = "likely_duplicate"
            elif score >= RELATED_THRESHOLD:
                label = "related"
            else:
                continue
            matches.append(Match(cid, round(float(sim), 4), round(min(score, 1.0), 4), label, same_cat, same_loc))
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:k]

    # ----------------------------------------------------------------------- persistence

    def save(self, path: Path = FAISS_INDEX_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            faiss.write_index(self.index, str(path))
            meta = {str(k): vars(v) for k, v in self.meta.items()}
        path.with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = FAISS_INDEX_PATH, embedder: Embedder | None = None) -> "DuplicateIndex":
        obj = cls(embedder)
        meta_path = path.with_suffix(".meta.json")
        if path.exists() and meta_path.exists():
            loaded = faiss.read_index(str(path))
            if loaded.d == obj.embedder.dim:
                obj.index = loaded
                obj.meta = {int(k): _Meta(**v) for k, v in json.loads(meta_path.read_text(encoding="utf-8")).items()}
        return obj
