# HW4: Pi Memory — Capture / Store / Retrieve / Inject

A persistent memory layer for the [Pi coding agent](https://github.com/earendil-works/pi), implemented entirely in Python. Pi extension bridge (TypeScript) is provided and requires no modification.

## Design Overview

```
Pi (local LLM) → pi-bridge/extension.ts → python -m memory.cli → memory.json
```

Four-stage pipeline:
- **Capture**: intercept `remember` tool calls → `core.capture()`
- **Store**: SHA-256 deduplicated JSON persistence → `JsonStore`
- **Retrieve**: BM25 lexical ranking → `bm25_search()`
- **Inject**: token-budget-aware context prepend → `build_injection()`

Optional **Hybrid Retrieval** (Task 2): BM25 + sentence-embedding RRF fusion via `memory/hybrid.py`. Enable with `MEMORY_HYBRID=1`.

An optional **LangChain comparison experiment** (not part of the assignment) is described at the end of this README.

## Environment

| Item | Value |
|---|---|
| Python | 3.12 (3.10+ required) |
| Local LLM | Any OpenAI-compatible endpoint (Gemma 4, Qwen3, Llama) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (auto-downloaded on first hybrid run) |
| Backend | LM Studio or Ollama |
| GPU | Not required for core tests/benchmark |

## Installation & Tests

```bash
pip install -r requirements.txt
pytest -q
```

All 13 tests should pass (green ✅).

The LangChain comparison needs extra packages and is optional; the core system does not depend on them:

```bash
pip install -r requirements-langchain.txt
```

## Running the Benchmark

Corpus and query file names are resolved relative to the `benchmark/` folder.

```bash
# Standard corpus (30 obs / 21 queries)
python benchmark/run_benchmark.py --k 5 --per-query

# Large corpus (100 obs / 40 queries)
python benchmark/run_benchmark.py --corpus corpus_large.jsonl \
    --queries queries_large.jsonl --k 5 --per-query
```

### BM25 Results (baseline corpus, k=5)

| Metric | Score |
|---|---|
| Recall@5 | 0.810 |
| MRR | 0.810 |
| nDCG@5 | 0.802 |

Matches the reference baseline exactly.

### Hybrid Results (baseline corpus, k=5)

| Metric | Pure BM25 | Hybrid | Δ |
|---|---|---|---|
| Recall@5 | 0.810 | 0.810 | = |
| MRR | 0.810 | 0.786 | ↓ −0.024 |
| nDCG@5 | 0.802 | 0.792 | ↓ −0.010 |

Recall is identical (the correct answers are still found). On this small corpus the MRR/nDCG dip is fragile: it depends on how tied RRF scores are ordered and on the BM25 variant (using `rank_bm25` scores with the same fusion gives MRR 0.810). On the larger corpus hybrid clearly helps (MRR 0.826 → 0.910); see "Extension: LangChain Comparison and Ablation" below.

### Optional: LangChain comparison

```bash
python benchmark/run_benchmark.py --k 5 --langchain
python benchmark/time_benchmark.py
python benchmark/ablation.py
# large corpus:
python benchmark/ablation.py --corpus corpus_large.jsonl --queries queries_large.jsonl
```

## Connecting to Pi

```bash
cd AIASE2026-HW4
PYTHONPATH=. pi -e ./pi-bridge/extension.ts
```

> The `PYTHONPATH=.` ensures Python can locate the `memory/` package when the bridge calls `python -m memory.cli`.

## Task 2: Hybrid Retrieval

`memory/hybrid.py` implements BM25 + sentence-embedding cosine similarity fused via Reciprocal Rank Fusion (RRF). The pure `bm25_search()` in `bm25.py` is preserved unchanged.

RRF ties are broken by corpus order, so results are deterministic across runs (an earlier version fused over a `set`, which made tied scores vary with `PYTHONHASHSEED`).

`memory/lc_hybrid.py` is an optional LangChain re-implementation used only for comparison; `bm25.py` and `hybrid.py` do not depend on it.

To use hybrid retrieval:
```python
from memory.hybrid import hybrid_search
results = hybrid_search(query, docs, k=8)
```

Or set `MEMORY_HYBRID=1` when running the benchmark (see `benchmark/run_benchmark.py`).

The embedding model is downloaded from Hugging Face on first use (~90MB).

### Offline / No-Internet Setup

If your machine cannot reach HuggingFace (e.g. `getaddrinfo failed`), use **one** of:

**Option A — use the HF local cache (model was downloaded before)**
```bash
# Windows
set HF_HUB_OFFLINE=1
python benchmark/run_benchmark.py --hybrid --k 5

# macOS / Linux
HF_HUB_OFFLINE=1 python benchmark/run_benchmark.py --hybrid --k 5
```

**Option B — point directly to a local model folder**
```bash
# Windows
set MEMORY_EMBED_MODEL=C:\path\to\all-MiniLM-L6-v2
python benchmark/run_benchmark.py --hybrid --k 5

# macOS / Linux
MEMORY_EMBED_MODEL=/path/to/all-MiniLM-L6-v2 python benchmark/run_benchmark.py --hybrid --k 5
```

**Option C — pre-cache on a machine with internet, then copy**
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
# Then copy ~/.cache/huggingface/hub/ to the offline machine.
```

If the model cannot be loaded for any reason, hybrid search **automatically falls back to pure BM25** — it will not crash.

## Demo

See `demo/README.md` for demo video link and screenshots.

## Extension: LangChain Comparison and Ablation

Not part of the assignment: an extra experiment comparing my implementation with a LangChain version (`BM25Retriever` + FAISS + `EnsembleRetriever`, in `memory/lc_hybrid.py`). Same corpus, queries, and embedding model (all-MiniLM-L6-v2); k=5, RRF c=60, alpha=0.5. Small = 21 queries / 30 docs, Large = 40 queries / 100 docs.

### Retrieval quality

| Variant | Small (R@5 / MRR / nDCG) | Large (R@5 / MRR / nDCG) |
|---|---|---|
| Own BM25 | 0.810 / 0.810 / 0.802 | 0.838 / 0.826 / 0.795 |
| rank_bm25 (stable ties) | 0.810 / 0.810 / 0.802 | 0.838 / 0.838 / 0.799 |
| Embedding-only | 0.857 / 0.810 / 0.822 | 0.912 / 0.844 / 0.843 |
| Own hybrid | 0.810 / 0.786 / 0.792 | 0.875 / 0.910 / 0.854 |
| rank_bm25 + own fusion | 0.810 / 0.810 / 0.810 | 0.875 / 0.910 / 0.854 |
| LangChain ensemble | 0.857 / 0.857 / 0.853 | 0.850 / 0.892 / 0.834 |

Findings:
- Hybrid improves ranking quality on the large corpus (MRR 0.826 → 0.910 vs BM25).
- Embedding-only has the highest Recall@5 on both corpora, so hybrid at alpha=0.5 does not dominate; alpha was not tuned.
- LangChain shows no consistent advantage over own hybrid (better on small, worse on large); with 21/40 queries these differences are within noise.
- Before the tie-order fix, own hybrid fused over a `set`: MRR ranged 0.786–0.810 (small) and 0.898–0.910 (large) across 5 `PYTHONHASHSEED` values. It is now deterministic.

### Latency (per query, same run)

| Variant | Small | Large |
|---|---|---|
| Own hybrid, re-encode all docs per query | 35.9 ms | 103.0 ms |
| Cached embeddings, pure-Python cosine | 5.5 ms | 8.4 ms |
| Cached embeddings, numpy cosine | 4.7 ms | 5.3 ms |
| LangChain ensemble | 4.5 ms | 5.5 ms |

The original slowness came from re-encoding every document on each query, not from the absence of a framework. With cached embeddings and numpy, own and LangChain versions are about equally fast. Absolute timings vary between runs, so compare only within one run.

### Trade-offs

- Accuracy and speed: no consistent advantage from LangChain in this benchmark.
- Engineering: less fusion logic to maintain; easy to swap vector store or embedding model.
- Cost: more dependencies, package moves (`EnsembleRetriever` is in `langchain-classic` in v1.x; `langchain-community` is being sunset), one more abstraction layer to debug.

Limitations: small benchmarks, one embedding model, alpha not tuned, single machine.

Raw outputs: `benchmark/results/` (`ablation_small.txt`, `ablation_large.txt`, `timing_small.txt`, `timing_large.txt`).
