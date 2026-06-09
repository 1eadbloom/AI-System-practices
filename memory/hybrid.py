"""Hybrid Retrieval: BM25 + Sentence Embedding cosine similarity (RRF fusion).

Usage:
    from memory.hybrid import hybrid_search
    results = hybrid_search(query, docs, k=8)

- Preserves pure bm25_search() in bm25.py untouched.
- Falls back to BM25-only if sentence-transformers unavailable.
- Enable via MEMORY_HYBRID=1 env var or by calling hybrid_search() directly.
"""
from __future__ import annotations
import os
import math
from .bm25 import bm25_search

_model = None
_MODEL_NAME = os.environ.get("MEMORY_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(_MODEL_NAME)
        except ImportError:
            _model = False  # sentinel: unavailable
    return _model


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def hybrid_search(
    query: str,
    docs: list[dict],
    k: int = 8,
    k1: float = 1.5,
    b: float = 0.75,
    rrf_c: int = 60,
    alpha: float = 0.5,   # weight for embedding score (1-alpha for BM25)
) -> list[dict]:
    """Hybrid BM25 + embedding retrieval using Reciprocal Rank Fusion (RRF).

    Falls back to pure BM25 if sentence-transformers is not available.
    """
    if not docs:
        return []

    model = _get_model()
    if model is False:
        # Fallback: pure BM25
        return bm25_search(query, docs, k, k1, b)

    # --- BM25 ranking ---
    bm25_results = bm25_search(query, docs, len(docs), k1, b)
    bm25_rank = {r["id"]: i + 1 for i, r in enumerate(bm25_results)}

    # --- Embedding ranking ---
    texts = [d["text"] for d in docs]
    doc_embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    query_embedding = model.encode([query], convert_to_numpy=True, show_progress_bar=False)[0]

    embed_scores = []
    for i, doc in enumerate(docs):
        score = float(_cosine(query_embedding.tolist(), doc_embeddings[i].tolist()))
        embed_scores.append((doc["id"], score))
    embed_scores.sort(key=lambda x: x[1], reverse=True)
    embed_rank = {doc_id: i + 1 for i, (doc_id, _) in enumerate(embed_scores)}

    # --- RRF fusion ---
    all_ids = {d["id"] for d in docs}
    fused = []
    for doc_id in all_ids:
        br = bm25_rank.get(doc_id, len(docs) + 1)
        er = embed_rank.get(doc_id, len(docs) + 1)
        rrf_score = (1 - alpha) / (rrf_c + br) + alpha / (rrf_c + er)
        fused.append({"id": doc_id, "score": rrf_score})

    fused.sort(key=lambda x: x["score"], reverse=True)
    return fused[:k]
