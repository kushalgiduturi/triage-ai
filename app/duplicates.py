"""Duplicate / related complaint detection with sentence embeddings + FAISS.

Each complaint is embedded with paraphrase-multilingual-MiniLM-L12-v2 and stored
in a FAISS inner-product index. The model runs through ONNX Runtime using the
8-bit quantized export published in the model's own repository, so the app needs
no torch and fits a 512 MB host (sentence-transformers is still supported as an
optional backend; the vectors agree to ~0.99 cosine).

Two editions share this code (see README "Two editions"):
  Full (local)     sentence-transformers + torch, uses more than 512 MB
  Lite (deployed)  ONNX Runtime + SentencePiece, fits in 512 MB Vectors are stored L2-normalised, so inner product = cosine similarity.
The vector is the sum of two embeddings:

    embed(masked complaint text) + embed("<category>: <sub issue>")

Raw text alone is not enough: the same incident written in English, Hinglish and
Telugu-English has a median cosine of only ~0.6, so the 0.85 threshold almost
never fires (recall 0.20 on the synthetic set). Anchoring the vector with the
normalised English issue label lifts recall to ~0.75 while the guards below keep
precision ~0.9 (see eval/metrics.json).

For a new complaint we retrieve the top-5 neighbours and score them:

    score = cosine + 0.05 if same category + 0.05 if same location

    score > 0.85        -> "likely_duplicate"
    0.65 <= score <= .85 -> "related"

Extra guards (documented choice): if both complaints name *different* known
locations, have *different* sub-issues, or were filed more than 7 days apart,
they can be "related" at most.
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

from app.config import (
    EMBEDDING_BACKEND, EMBEDDING_MODEL, EMBEDDING_ONNX_FILE, EMBEDDING_REVISION, FAISS_INDEX_PATH,
)

DUPLICATE_THRESHOLD = 0.85
RELATED_THRESHOLD = 0.65
CATEGORY_BOOST = 0.05
LOCATION_BOOST = 0.05
DUPLICATE_WINDOW_DAYS = 7
TOP_K = 5


# --------------------------------------------------------------------------- embedders


class Embedder:
    name: str  # recorded with the FAISS index so vectors from different backends are never mixed
    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class OnnxEmbedder(Embedder):
    """paraphrase-multilingual-MiniLM-L12-v2 on ONNX Runtime (no torch), sized for a 512 MB host.

    Reproduces the sentence-transformers pipeline: tokenize (max 128 tokens),
    run the transformer, mean-pool over the attention mask, L2-normalise.

    Memory choices (measured on Linux): the `tokenizers` library needs ~290 MB to load
    XLM-R's 250k-token vocabulary, so we tokenize with SentencePiece from the same repo
    (identical token ids, ~10 MB); and ONNX graph optimisation is off because it
    de-quantizes weights at load time (+200 MB) without changing the output.
    """

    name = "onnx"
    MAX_TOKENS = 128  # the model's max_seq_length in sentence-transformers
    BOS, PAD, EOS, UNK = 0, 1, 2, 3  # XLM-R special ids; SentencePiece ids are shifted by +1

    def __init__(self, model_name: str = EMBEDDING_MODEL, onnx_file: str = EMBEDDING_ONNX_FILE,
                 revision: str = EMBEDDING_REVISION) -> None:
        import onnxruntime as ort
        import sentencepiece as spm
        from huggingface_hub import hf_hub_download

        repo = model_name if "/" in model_name else f"sentence-transformers/{model_name}"
        model_path = hf_hub_download(repo, onnx_file, revision=revision)
        self.sp = spm.SentencePieceProcessor(
            model_file=hf_hub_download(repo, "sentencepiece.bpe.model", revision=revision))

        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.enable_cpu_mem_arena = False
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        self.session = ort.InferenceSession(model_path, options, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.dim = self.session.get_outputs()[0].shape[-1] or 384

    def _token_ids(self, text: str) -> list[int]:
        """XLM-R ids: <s> + SentencePiece pieces shifted by the fairseq offset + </s>."""
        body = [p + 1 if p != 0 else self.UNK for p in self.sp.encode(text)]
        return [self.BOS] + body[: self.MAX_TOKENS - 2] + [self.EOS]

    def encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        out = []
        for start in range(0, len(texts), batch_size):
            seqs = [self._token_ids(t) for t in texts[start:start + batch_size]]
            width = max(len(seq) for seq in seqs)
            ids = np.full((len(seqs), width), self.PAD, dtype="int64")
            mask = np.zeros((len(seqs), width), dtype="int64")
            for row, seq in enumerate(seqs):
                ids[row, : len(seq)] = seq
                mask[row, : len(seq)] = 1
            feeds = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.input_names:
                feeds["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(None, feeds)[0]  # (batch, tokens, dim)
            weights = mask[..., None].astype("float32")
            pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
            out.append(pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None))
        return np.vstack(out).astype("float32") if out else np.zeros((0, self.dim), dtype="float32")


class SentenceTransformerEmbedder(Embedder):
    """Full edition backend (requirements.txt): needs sentence-transformers, which pulls in torch."""

    name = "sentence-transformers"

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name, device="cpu")
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=32)
        return vecs.astype("float32")


class HashEmbedder(Embedder):
    """Character n-gram hashing vectors. Fast, no download; used in unit tests / CI."""

    name = "hash"

    def __init__(self, dim: int = 2048) -> None:
        from sklearn.feature_extraction.text import HashingVectorizer

        self.dim = dim
        self.vec = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=dim,
                                     alternate_sign=False, norm="l2")

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.vec.transform([t.lower() for t in texts]).toarray().astype("float32")


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def resolve_backend(backend: str = EMBEDDING_BACKEND) -> str:
    """'auto' means the Full edition's sentence-transformers when installed, else the Lite ONNX backend."""
    if backend != "auto":
        return backend
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return "onnx"
    return "sentence-transformers"


def get_embedder() -> Embedder:
    """Process-wide embedder (the transformer model is loaded once)."""
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            backends = {"onnx": OnnxEmbedder, "hash": HashEmbedder,
                        "sentence-transformers": SentenceTransformerEmbedder}
            _embedder = backends[resolve_backend()]()
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
    sub_issue: str = ""


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

    def embed_complaint(self, masked_text: str, category: str, sub_issue: str) -> np.ndarray:
        """Issue-anchored complaint vector: text embedding + issue-label embedding, re-normalised."""
        text_vec, issue_vec = self.embedder.encode([masked_text, f"{category}: {sub_issue.replace('_', ' ')}"])
        vec = text_vec + issue_vec
        return (vec / (np.linalg.norm(vec) or 1.0)).astype("float32")

    def add(self, complaint_id: int, vector: np.ndarray, category: str, location: str, timestamp: datetime,
            sub_issue: str = "") -> None:
        with self._lock:
            if complaint_id in self.meta:
                self.index.remove_ids(np.array([complaint_id], dtype="int64"))
            self.index.add_with_ids(vector.reshape(1, -1).astype("float32"), np.array([complaint_id], dtype="int64"))
            self.meta[complaint_id] = _Meta(category, normalize_location(location), timestamp.isoformat(), sub_issue)

    def search(
        self,
        vector: np.ndarray,
        category: str,
        location: str,
        timestamp: datetime,
        k: int = TOP_K,
        exclude_id: int | None = None,
        sub_issue: str = "",
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
            different_issue = bool(sub_issue) and bool(meta.sub_issue) and meta.sub_issue != sub_issue
            if (score > DUPLICATE_THRESHOLD and not different_place and not different_issue
                    and days_apart <= DUPLICATE_WINDOW_DAYS):
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
            meta = {"backend": self.embedder.name, "items": {str(k): vars(v) for k, v in self.meta.items()}}
        path.with_suffix(".meta.json").write_text(json.dumps(meta), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = FAISS_INDEX_PATH, embedder: Embedder | None = None) -> "DuplicateIndex":
        obj = cls(embedder)
        meta_path = path.with_suffix(".meta.json")
        if path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            loaded = faiss.read_index(str(path))
            # Only reuse vectors made by the same backend (e.g. after switching Full <-> Lite the
            # API re-embeds everything from the database instead of mixing vector spaces).
            if meta.get("backend") == obj.embedder.name and loaded.d == obj.embedder.dim:
                obj.index = loaded
                obj.meta = {int(k): _Meta(**v) for k, v in meta["items"].items()}
        return obj
