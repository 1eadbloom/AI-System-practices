#!/usr/bin/env python3
"""
open-jsonvalidate / scripts/run.py — file-based output contract entry point (atomic write).

Self-contained resolve_result_path; does NOT import aiase_contract (unavailable
once installed under ~/.hermes/skills/).

--errors takes a JSON array string of {path, rule, message} objects.
Consistency rule: valid=true requires errors=[]; if valid=true but errors
is non-empty, valid is overridden to false (evidence overrides claim).

Usage:
    python3 run.py --task_id "<id>" --valid false \
        --errors '[{"path":"/age","rule":"minimum","message":"Value -1 is less than minimum 0"}]' \
        --confidence 1.0
"""
import os
import sys
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


def _sanitize_error(e):
    if not isinstance(e, dict):
        return None
    return {
        "path": str(e.get("path", "/")),
        "rule": str(e.get("rule", "")),
        "message": str(e.get("message", "")),
    }


def _str2bool(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task_id", required=True)
    ap.add_argument("--valid", required=True)
    ap.add_argument("--errors", default="[]", help="JSON array string of error objects")
    ap.add_argument("--confidence", type=float, default=1.0)
    a = ap.parse_args()

    try:
        raw_errors = json.loads(a.errors)
        if not isinstance(raw_errors, list):
            raise ValueError("errors must be a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"ERROR: --errors is not a valid JSON array: {e}", file=sys.stderr)
        return 2

    errors = [x for x in (_sanitize_error(e) for e in raw_errors) if x is not None]
    valid = _str2bool(a.valid)

    # Enforce consistency: valid=true requires errors=[]
    if valid and errors:
        valid = False  # evidence overrides claim

    result = {
        "task_id": a.task_id,
        "valid": valid,
        "errors": errors,
        "error_count": len(errors),
        "confidence": _clamp_confidence(a.confidence),
    }

    path = resolve_result_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    os.replace(tmp, path)  # atomic write
    print(f"written ok -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
