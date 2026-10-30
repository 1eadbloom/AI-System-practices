#!/usr/bin/env python3
"""Timing comparison: own hybrid (memory/hybrid.py) vs LangChain (memory/lc_hybrid.py).

Measures, on the same corpus and queries:
  1. model load time        (embedding model into memory)
  2. index build time       (LangChain only; own hybrid has no index)
  3. avg per-query latency  (warm-up query excluded, repeated ROUNDS times)

Usage:
    python benchmark/time_benchmark.py
    python benchmark/time_benchmark.py --corpus corpus_large.jsonl --queries queries_large.jsonl
    python benchmark/time_benchmark.py --no-embed     # BM25-only dry run, no model download
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def per_query_ms(fn, queries, rounds):
    fn(queries[0])  # warm-up, discarded
    per_round = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for q in queries:
            fn(q)
        per_round.append((time.perf_counter() - t0) / len(queries) * 1000)
    return statistics.mean(per_round), (statistics.stdev(per_round) if len(per_round) > 1 else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="corpus.jsonl")
    ap.add_argument("--queries", default="queries.jsonl")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--no-embed", action="store_true", help="BM25-only dry run")
    args = ap.parse_args()

    corpus = load_jsonl(HERE / args.corpus)
    queries = [q["query"] for q in load_jsonl(HERE / args.queries)]
    docs = [{"id": r["id"], "text": " ".join([r["summary"], *r.get("tags", [])])} for r in corpus]
    k = args.k
    print(f"corpus={args.corpus} ({len(docs)} docs), queries={len(queries)}, k={k}, rounds={args.rounds}\n")

    from memory.bm25 import bm25_search
    from memory.lc_hybrid import LCHybridIndex

    results = []  # (label, load_s, build_s, mean_ms, std_ms)

    # --- own pure BM25 ---
    m, s = per_query_ms(lambda q: bm25_search(q, docs, k), queries, args.rounds)
    results.append(("own BM25", 0.0, 0.0, m, s))

    # --- LangChain BM25 only ---
    t0 = time.perf_counter()
    lc_bm25 = LCHybridIndex(docs, embeddings=None)
    build = time.perf_counter() - t0
    m, s = per_query_ms(lambda q: lc_bm25.search(q, k), queries, args.rounds)
    results.append(("LangChain BM25", 0.0, build, m, s))

    if not args.no_embed:
        from memory import hybrid
        from memory.lc_hybrid import default_embeddings

        # --- own hybrid ---
        t0 = time.perf_counter()
        model = hybrid._get_model()
        load = time.perf_counter() - t0
        if model is False:
            print("WARNING: own hybrid could not load the embedding model; skipped.")
        else:
            m, s = per_query_ms(lambda q: hybrid.hybrid_search(q, docs, k), queries, args.rounds)
            results.append(("own hybrid", load, 0.0, m, s))

        # --- LangChain hybrid ---
        t0 = time.perf_counter()
        emb = default_embeddings()
        load = time.perf_counter() - t0
        t0 = time.perf_counter()
        lc = LCHybridIndex(docs, embeddings=emb)
        build = time.perf_counter() - t0
        m, s = per_query_ms(lambda q: lc.search(q, k), queries, args.rounds)
        results.append(("LangChain hybrid", load, build, m, s))

    print(f"{'mode':<18}{'model load (s)':>16}{'index build (s)':>17}{'per query (ms)':>18}")
    for label, load, build, m, s in results:
        print(f"{label:<18}{load:>16.2f}{build:>17.3f}{m:>12.2f} +/- {s:.2f}")
    print("\nNotes: own hybrid re-encodes ALL docs on every query (no index), so its per-query cost")
    print("grows with corpus size. LangChain builds the index once; per-query only encodes the query.")


if __name__ == "__main__":
    main()
