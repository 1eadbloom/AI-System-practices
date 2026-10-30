#!/usr/bin/env python3
"""Ablation: separate WHY own hybrid and LangChain hybrid differ.

Variants (same corpus, queries, embedding model; k=5, RRF c=60, alpha=0.5):
  own BM25            memory.bm25.bm25_search
  rank_bm25           rank_bm25.BM25Okapi, own tokenizer, stable tie order
  embedding-only      cached doc embeddings, numpy cosine
  V0 own hybrid       memory.hybrid.hybrid_search AS-IS (re-encodes docs each query)
  V1 own, fixed       own BM25 + cached embeddings + numpy cosine + deterministic RRF ties
  V2 rank_bm25 hybrid V1 but BM25 ranking from rank_bm25      -> effect of BM25 variant
  V3 LangChain        LCHybridIndex (EnsembleRetriever)        -> framework / tie-order differences
  (latency only) V1a  cached embeddings but pure-Python cosine -> caching vs numpy

Also: V0 is run under several PYTHONHASHSEED values, because hybrid.py fuses over a
`set`, so tied RRF scores can be ordered differently between runs.

Usage:
    python benchmark/ablation.py
    python benchmark/ablation.py --corpus corpus_large.jsonl --queries queries_large.jsonl
    python benchmark/ablation.py --seeds 0          # skip the multi-seed V0 runs
    python benchmark/ablation.py --fake-embed       # plumbing test only, numbers are meaningless
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import run_benchmark as rb  # noqa: E402  (reuse load_jsonl / ndcg_at_k)
from memory.bm25 import tokenize, bm25_search  # noqa: E402

K = 5
C = 60
ALPHA = 0.5


class FakeModel:
    """Plumbing test only: hashed bag-of-words vectors. NOT semantic."""
    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False):
        out = []
        for t in texts:
            v = np.zeros(64)
            for w in tokenize(t):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
            out.append(v)
        return np.array(out)


def get_model(fake):
    from memory import hybrid
    if fake:
        hybrid._model = FakeModel()
        return hybrid._model
    m = hybrid._get_model()
    if m is False:
        sys.exit("Embedding model could not be loaded (install sentence-transformers / check network).")
    return m


def evaluate(search_ids, queries, k=K):
    rec, rr, nd = [], [], []
    for q in queries:
        relevant = set(q["relevant_ids"])
        ranked = search_ids(q["query"])[:k]
        rec.append(len(set(ranked) & relevant) / len(relevant) if relevant else 0.0)
        r = 0.0
        for rank, i in enumerate(ranked, start=1):
            if i in relevant:
                r = 1.0 / rank
                break
        rr.append(r)
        nd.append(rb.ndcg_at_k(ranked, relevant, k))
    m = statistics.mean
    return {"recall": m(rec), "mrr": m(rr), "ndcg": m(nd)}


def latency_ms(fn, queries, rounds=3):
    fn(queries[0]["query"])  # warm-up
    vals = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        for q in queries:
            fn(q["query"])
        vals.append((time.perf_counter() - t0) / len(queries) * 1000)
    return statistics.mean(vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="corpus.jsonl")
    ap.add_argument("--queries", default="queries.jsonl")
    ap.add_argument("--seeds", type=int, default=5, help="number of PYTHONHASHSEED runs for V0 (0 = skip)")
    ap.add_argument("--fake-embed", action="store_true")
    ap.add_argument("--v0-json", action="store_true", help="internal: print V0 metrics as JSON and exit")
    args = ap.parse_args()

    corpus = rb.load_jsonl(HERE / args.corpus)
    queries = rb.load_jsonl(HERE / args.queries)
    docs = [{"id": r["id"], "text": " ".join([r["summary"], *r.get("tags", [])])} for r in corpus]
    ids = [d["id"] for d in docs]
    n = len(docs)

    from memory import hybrid
    model = get_model(args.fake_embed)

    # ---- V0 as-is (also used by the multi-seed subprocess mode) ----
    v0 = lambda q: [r["id"] for r in hybrid.hybrid_search(q, docs, K)]
    if args.v0_json:
        print(json.dumps(evaluate(v0, queries)))
        return

    print(f"corpus={args.corpus} ({n} docs), queries={len(queries)}, k={K}, RRF c={C}, alpha={ALPHA}")
    if args.fake_embed:
        print("*** FAKE EMBEDDINGS: plumbing test only, numbers are meaningless ***")
    print()

    # ---- shared pieces ----
    from rank_bm25 import BM25Okapi
    bm = BM25Okapi([tokenize(d["text"]) for d in docs])
    pos = {i: p for p, i in enumerate(ids)}

    def own_bm25_order(q):
        return [pos[r["id"]] for r in bm25_search(q, docs, n)]

    def rb25_order(q):
        s = bm.get_scores(tokenize(q))
        return sorted(range(n), key=lambda i: -s[i])  # stable: ties keep corpus order

    t0 = time.perf_counter()
    D = model.encode([d["text"] for d in docs], convert_to_numpy=True, show_progress_bar=False)
    cache_build = time.perf_counter() - t0
    Dn = D / np.where(np.linalg.norm(D, axis=1, keepdims=True) == 0, 1, np.linalg.norm(D, axis=1, keepdims=True))
    D_list = [row.tolist() for row in D]

    def qvec(q):
        return model.encode([q], convert_to_numpy=True, show_progress_bar=False)[0]

    def emb_order(q):
        v = qvec(q)
        nv = np.linalg.norm(v) or 1.0
        s = Dn @ (v / nv)
        return sorted(range(n), key=lambda i: -float(s[i]))

    def emb_order_pycos(q):  # cached embeddings but pure-Python cosine (as in hybrid.py)
        v = qvec(q).tolist()
        s = [hybrid._cosine(v, d) for d in D_list]
        return sorted(range(n), key=lambda i: -s[i])

    def rrf(rank_lists, weights):
        score = {}
        for rl, w in zip(rank_lists, weights):
            for r, i in enumerate(rl, start=1):
                score[i] = score.get(i, 0.0) + w / (C + r)
        return [i for i in sorted(range(n), key=lambda i: (-score.get(i, 0.0), i))]

    W = [1 - ALPHA, ALPHA]
    to_ids = lambda order: [ids[i] for i in order]
    v1 = lambda q: to_ids(rrf([own_bm25_order(q), emb_order(q)], W))
    v1a = lambda q: to_ids(rrf([own_bm25_order(q), emb_order_pycos(q)], W))
    v2 = lambda q: to_ids(rrf([rb25_order(q), emb_order(q)], W))

    from memory.lc_hybrid import LCHybridIndex
    if args.fake_embed:
        from langchain_core.embeddings import Embeddings

        class FakeLC(Embeddings):
            def embed_documents(self, ts):
                return model.encode(ts).tolist()

            def embed_query(self, t):
                return model.encode([t])[0].tolist()
        lc_emb = FakeLC()
    else:
        from memory.lc_hybrid import default_embeddings
        lc_emb = default_embeddings()
    t0 = time.perf_counter()
    lc = LCHybridIndex(docs, embeddings=lc_emb)
    lc_build = time.perf_counter() - t0
    v3 = lambda q: [r["id"] for r in lc.search(q, K)]

    # ---- quality ----
    rows = [
        ("own BM25", lambda q: to_ids(own_bm25_order(q))),
        ("rank_bm25 (stable ties)", lambda q: to_ids(rb25_order(q))),
        ("embedding-only", lambda q: to_ids(emb_order(q))),
        ("V0 own hybrid (as-is, this run)", v0),
        ("V1 own, cached + deterministic", v1),
        ("V2 rank_bm25 + own fusion", v2),
        ("V3 LangChain ensemble", v3),
    ]
    print(f"{'variant':<34}{'Recall@5':>10}{'MRR':>8}{'nDCG@5':>9}")
    for label, fn in rows:
        m = evaluate(fn, queries)
        print(f"{label:<34}{m['recall']:>10.3f}{m['mrr']:>8.3f}{m['ndcg']:>9.3f}")

    # V1 vs V1a must rank identically (only cosine implementation differs)
    same = sum(1 for q in queries if v1(q["query"])[:K] == v1a(q["query"])[:K])
    print(f"\nCheck: V1 (numpy) vs V1a (pure-Python cosine) identical top-{K} on {same}/{len(queries)} queries")
    same0 = sum(1 for q in queries if v0(q["query"])[:K] == v1(q["query"])[:K])
    print(f"Info : V0 vs V1 identical top-{K} on {same0}/{len(queries)} queries (differences come from RRF tie order)")

    # ---- V0 across hash seeds ----
    if args.seeds > 0:
        print(f"\nV0 own hybrid across PYTHONHASHSEED=0..{args.seeds - 1}:")
        res = []
        for s in range(args.seeds):
            env = dict(os.environ, PYTHONHASHSEED=str(s))
            cmd = [sys.executable, str(Path(__file__).resolve()), "--corpus", args.corpus,
                   "--queries", args.queries, "--v0-json"] + (["--fake-embed"] if args.fake_embed else [])
            out = subprocess.run(cmd, env=env, capture_output=True, text=True)
            line = [l for l in out.stdout.splitlines() if l.startswith("{")]
            if not line:
                print(f"  seed {s}: failed: {out.stderr[-200:]}")
                continue
            m = json.loads(line[-1])
            res.append(m)
            print(f"  seed {s}: Recall {m['recall']:.3f}  MRR {m['mrr']:.3f}  nDCG {m['ndcg']:.3f}")
        if res:
            for key in ("recall", "mrr", "ndcg"):
                vals = [r[key] for r in res]
                print(f"  {key:<7} min {min(vals):.3f}  max {max(vals):.3f}")

    # ---- latency ----
    print("\nLatency (per query, warm; index/cache build reported separately):")
    lat = [
        ("V0 own hybrid (re-encode all docs)", 0.0, v0),
        ("V1a cached embeddings, py cosine", cache_build, v1a),
        ("V1  cached embeddings, numpy", cache_build, v1),
        ("V3  LangChain ensemble", lc_build, v3),
    ]
    print(f"{'variant':<38}{'build (s)':>11}{'per query (ms)':>16}")
    for label, build, fn in lat:
        print(f"{label:<38}{build:>11.3f}{latency_ms(fn, queries):>16.2f}")


if __name__ == "__main__":
    main()
