#!/usr/bin/env python3
"""
code-author / scripts/run.py — file-based output contract entry point (atomic write).

Self-contained resolve_result_path; does NOT import aiase_contract (unavailable
once installed under ~/.hermes/skills/).

Usage:
    python3 run.py --task_id "<id>" --code "<source>" --loc 12 \
        --self_test_passed 5 --self_test_failed 0 \
        --rationale "<text>" --confidence 0.9
"""
import os
import json
import argparse


def resolve_result_path() -> str:
    return os.environ.get("AIASE_RESULT_PATH") or os.path.join(os.getcwd(), "aiase_result.json")


def _clamp_confidence(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task_id", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--loc", type=int, default=0)
    ap.add_argument("--self_test_passed", type=int, default=0)
    ap.add_argument("--self_test_failed", type=int, default=0)
    ap.add_argument("--rationale", default="")
    ap.add_argument("--confidence", type=float, default=0.5)
    a = ap.parse_args()

    result = {
        "task_id": a.task_id,
        "code": a.code,
        "loc": a.loc,
        "self_test_results": {"passed": a.self_test_passed, "failed": a.self_test_failed},
        "rationale": a.rationale,
        "confidence": _clamp_confidence(a.confidence),
    }

    path = resolve_result_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, path)  # atomic write
    print(f"written ok -> {path}")


if __name__ == "__main__":
    main()
