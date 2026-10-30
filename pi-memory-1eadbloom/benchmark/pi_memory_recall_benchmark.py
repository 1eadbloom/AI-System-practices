"""
Pi Memory Recall@K Benchmark
==============================
比較 pure BM25 vs Hybrid（BM25 + embedding RRF）的召回率。

使用方式：
    # 純 BM25
    python pi_memory_recall_benchmark.py --mode bm25

    # Hybrid（需先 pip install sentence-transformers）
    python pi_memory_recall_benchmark.py --mode hybrid

    # 兩者都跑，直接比較
    python pi_memory_recall_benchmark.py --mode both

    # 指定 K 值
    python pi_memory_recall_benchmark.py --mode both --k 5 --k 10

資料來源：
    benchmark/corpus.jsonl   — 記憶庫（30 筆 observation）
    benchmark/queries.jsonl  — 21 個 query + 人工標記的 relevant_ids
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# 資料載入
# ---------------------------------------------------------------------------

def load_corpus(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_queries(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# BM25 實作（與 memory/bm25.py 邏輯一致）
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    import re
    text = text.lower()
    text = re.sub(r"([\u4e00-\u9fff\u3400-\u4dbf])", r" \1 ", text)
    return [t for t in text.split() if t]


def bm25_search(query: str, docs: list[dict], k: int,
                k1: float = 1.5, b: float = 0.75) -> list[dict]:
    if not docs:
        return []
    tokenized = [tokenize(d["text"]) for d in docs]
    df: dict[str, int] = {}
    for tokens in tokenized:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    N = len(docs)
    avgdl = sum(len(t) for t in tokenized) / N if N else 1
    q_tokens = tokenize(query)
    scores = []
    for i, (doc, tokens) in enumerate(zip(docs, tokenized)):
        tf = Counter(tokens)
        dl = len(tokens)
        score = 0.0
        for qt in q_tokens:
            if qt not in tf:
                continue
            idf = math.log((N - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5) + 1)
            tf_norm = tf[qt] * (k1 + 1) / (tf[qt] + k1 * (1 - b + b * dl / avgdl))
            score += idf * tf_norm
        scores.append((i, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    top = [docs[i] for i, s in scores[:k] if s > 0]
    # 如果有效結果不足 k 筆，補上分數為 0 的（讓 Recall 計算更公平）
    if len(top) < k:
        used_ids = {d["id"] for d in top}
        for i, s in scores[len(top):]:
            if docs[i]["id"] not in used_ids:
                top.append(docs[i])
            if len(top) >= k:
                break
    return top[:k]


def corpus_to_docs(corpus: list[dict]) -> list[dict]:
    """把 corpus（含 summary + tags）轉成 {id, text} 供 BM25 使用。"""
    return [
        {"id": o["id"], "text": " ".join([o["summary"], *o.get("tags", [])])}
        for o in corpus
    ]


# ---------------------------------------------------------------------------
# Hybrid：BM25 + Embedding RRF
# ---------------------------------------------------------------------------

_embed_model = None

def get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            print("✅ sentence-transformers 載入成功，啟用真正的 hybrid 模式", file=sys.stderr)
        except ImportError:
            print(
                "⚠️  找不到 sentence-transformers，hybrid 模式退回純 BM25。\n"
                "   安裝方式：pip install sentence-transformers",
                file=sys.stderr,
            )
    return _embed_model


def embedding_search(query: str, docs: list[dict], corpus: list[dict], k: int) -> list[dict]:
    """用 cosine similarity 排序，回傳 top-k corpus entries。"""
    model = get_embed_model()
    if model is None:
        return bm25_search(query, docs, k)

    import numpy as np
    texts = [d["text"] for d in docs]
    doc_embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    q_emb = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
    sims = doc_embs @ q_emb
    ranked_idx = sims.argsort()[::-1][:k]
    by_id = {o["id"]: o for o in corpus}
    return [by_id[docs[i]["id"]] for i in ranked_idx if docs[i]["id"] in by_id]


def rrf_fuse(bm25_hits: list[dict], emb_hits: list[dict],
             k_rrf: int = 60, top_k: int = 5) -> list[dict]:
    """Reciprocal Rank Fusion。"""
    scores: dict[str, float] = {}
    for rank, doc in enumerate(bm25_hits):
        scores[doc["id"]] = scores.get(doc["id"], 0) + 1 / (k_rrf + rank + 1)
    for rank, doc in enumerate(emb_hits):
        scores[doc["id"]] = scores.get(doc["id"], 0) + 1 / (k_rrf + rank + 1)
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    by_id = {d["id"]: d for d in bm25_hits + emb_hits}
    return [by_id[i] for i in sorted_ids[:top_k] if i in by_id]


def hybrid_search(query: str, docs: list[dict], corpus: list[dict], k: int) -> list[dict]:
    bm25_hits_raw = bm25_search(query, docs, k * 2)
    emb_hits_raw = embedding_search(query, docs, corpus, k * 2)
    # 轉回 corpus 格式
    by_id = {o["id"]: o for o in corpus}
    bm25_corpus = [by_id[d["id"]] for d in bm25_hits_raw if d["id"] in by_id]
    emb_corpus = [by_id[d["id"]] for d in emb_hits_raw if d["id"] in by_id]
    return rrf_fuse(bm25_corpus, emb_corpus, top_k=k)


# ---------------------------------------------------------------------------
# 評測指標
# ---------------------------------------------------------------------------

def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    retrieved_k = set(retrieved_ids[:k])
    return len(retrieved_k & set(relevant_ids)) / len(relevant_ids)


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    rel_set = set(relevant_ids)
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in rel_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    rel_set = set(relevant_ids)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, rid in enumerate(retrieved_ids[:k], start=1)
        if rid in rel_set
    )
    ideal = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, min(len(relevant_ids), k) + 1)
    )
    return dcg / ideal if ideal > 0 else 0.0


# ---------------------------------------------------------------------------
# 執行評測
# ---------------------------------------------------------------------------

def run_eval(mode: str, corpus: list[dict], queries: list[dict],
             k: int, per_query: bool = False) -> dict:
    docs = corpus_to_docs(corpus)
    by_id = {o["id"]: o for o in corpus}

    recalls, mrrs, ndcgs = [], [], []

    if per_query:
        print(f"\n{'Query':<45} {'Recall@'+str(k):<12} {'MRR':<8} {'nDCG@'+str(k):<8} Hits")
        print("-" * 95)

    for q in queries:
        query_text = q["query"]
        relevant_ids = q["relevant_ids"]

        if mode == "bm25":
            hits = bm25_search(query_text, docs, k)
            retrieved_ids = [h["id"] for h in hits]
        else:  # hybrid
            hits = hybrid_search(query_text, docs, corpus, k)
            retrieved_ids = [h["id"] for h in hits]

        r = recall_at_k(retrieved_ids, relevant_ids, k)
        m = mrr(retrieved_ids, relevant_ids)
        n = ndcg_at_k(retrieved_ids, relevant_ids, k)
        recalls.append(r)
        mrrs.append(m)
        ndcgs.append(n)

        if per_query:
            hit_ids = [rid for rid in retrieved_ids[:k] if rid in set(relevant_ids)]
            miss_ids = [rid for rid in relevant_ids if rid not in set(retrieved_ids[:k])]
            status = "✅" if r == 1.0 else ("⚠️ " if r > 0 else "❌")
            q_short = query_text[:43] + ".." if len(query_text) > 45 else query_text
            print(f"{status} {q_short:<45} {r:<12.3f} {m:<8.3f} {n:<8.3f} hit={hit_ids} miss={miss_ids}")

    return {
        "recall": sum(recalls) / len(recalls),
        "mrr": sum(mrrs) / len(mrrs),
        "ndcg": sum(ndcgs) / len(ndcgs),
        "per_query": list(zip([q["query"] for q in queries], recalls, mrrs, ndcgs)),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Pi Memory Recall@K Benchmark")
    ap.add_argument("--mode", choices=["bm25", "hybrid", "both"], default="both",
                    help="評測模式（預設 both）")
    ap.add_argument("--k", type=int, action="append", dest="ks",
                    help="K 值，可重複指定多個（預設 5）")
    ap.add_argument("--per-query", action="store_true", help="顯示每題細節")
    ap.add_argument("--corpus", default=None, help="corpus.jsonl 路徑")
    ap.add_argument("--queries", default=None, help="queries.jsonl 路徑")
    args = ap.parse_args()

    ks = args.ks or [5]

    # 自動尋找資料檔
    search_dirs = [HERE, HERE / "benchmark", HERE.parent / "benchmark"]
    def find_file(name: str, override: str | None) -> Path:
        if override:
            return Path(override)
        for d in search_dirs:
            p = d / name
            if p.exists():
                return p
        print(f"❌ 找不到 {name}，請用 --corpus / --queries 指定路徑", file=sys.stderr)
        sys.exit(1)

    corpus_path = find_file("corpus.jsonl", args.corpus)
    queries_path = find_file("queries.jsonl", args.queries)

    corpus = load_corpus(corpus_path)
    queries = load_queries(queries_path)

    print(f"\n📊 Pi Memory Recall@K Benchmark")
    print(f"   corpus : {corpus_path} ({len(corpus)} 筆)")
    print(f"   queries: {queries_path} ({len(queries)} 筆)")

    modes = ["bm25", "hybrid"] if args.mode == "both" else [args.mode]

    all_results: dict[str, dict[int, dict]] = {}

    for mode in modes:
        all_results[mode] = {}
        for k in ks:
            print(f"\n{'='*60}")
            print(f"  模式：{mode.upper()}   K={k}")
            print(f"{'='*60}")
            result = run_eval(mode, corpus, queries, k, per_query=args.per_query)
            all_results[mode][k] = result
            print(f"\n  Recall@{k}  : {result['recall']:.3f}")
            print(f"  MRR       : {result['mrr']:.3f}")
            print(f"  nDCG@{k}   : {result['ndcg']:.3f}")

    # 比較表（--mode both 時）
    if args.mode == "both" and len(ks) >= 1:
        print(f"\n{'='*60}")
        print("  📈 BM25 vs Hybrid 比較")
        print(f"{'='*60}")
        print(f"{'指標':<20}", end="")
        for k in ks:
            print(f"  BM25@{k}   Hybrid@{k}   Delta", end="")
        print()
        print("-" * (20 + len(ks) * 30))

        for metric_key, metric_name in [("recall", "Recall@K"), ("mrr", "MRR"), ("ndcg", "nDCG@K")]:
            print(f"{metric_name:<20}", end="")
            for k in ks:
                b = all_results["bm25"][k][metric_key]
                h = all_results["hybrid"][k][metric_key]
                delta = h - b
                sign = "+" if delta >= 0 else ""
                print(f"  {b:.3f}     {h:.3f}     {sign}{delta:.3f}", end="")
            print()

        print(f"\n{'='*60}")
        print("  面試可引用的數字：")
        for k in ks:
            b_r = all_results["bm25"][k]["recall"]
            h_r = all_results["hybrid"][k]["recall"]
            delta_pct = (h_r - b_r) * 100
            sign = "+" if delta_pct >= 0 else ""
            print(f"  Recall@{k}：BM25={b_r:.1%}，Hybrid={h_r:.1%}，提升 {sign}{delta_pct:.1f} 個百分點")


if __name__ == "__main__":
    main()
