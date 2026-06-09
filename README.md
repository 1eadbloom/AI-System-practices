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

## Running the Benchmark

```bash
# Standard corpus (30 obs / 21 queries)
python benchmark/run_benchmark.py --k 5 --per-query

# Large corpus (100 obs / 40 queries)
python benchmark/run_benchmark.py --corpus benchmark/corpus_large.jsonl \
    --queries benchmark/queries_large.jsonl --k 5 --per-query
```

### BM25 Results (baseline corpus, k=5)

| Metric | Score |
|---|---|
| Recall@5 | 0.810 |
| MRR | 0.810 |
| nDCG@5 | 0.802 |

Matches the reference baseline exactly.

## Connecting to Pi

```bash
cd AIASE2026-HW4
PYTHONPATH=. pi -e ./pi-bridge/extension.ts
```

> The `PYTHONPATH=.` ensures Python can locate the `memory/` package when the bridge calls `python -m memory.cli`.

## Task 2: Hybrid Retrieval

`memory/hybrid.py` implements BM25 + sentence-embedding cosine similarity fused via Reciprocal Rank Fusion (RRF). The pure `bm25_search()` in `bm25.py` is preserved unchanged.

To use hybrid retrieval:
```python
from memory.hybrid import hybrid_search
results = hybrid_search(query, docs, k=8)
```

Or set `MEMORY_HYBRID=1` when running the benchmark (see `benchmark/run_benchmark.py`).

The embedding model is downloaded from Hugging Face on first use (~90MB). For fully offline use, pre-cache it:
```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

## Demo

See `demo/README.md` for demo video link and screenshots.
