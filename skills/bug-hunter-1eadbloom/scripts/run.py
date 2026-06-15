#!/usr/bin/env python3
"""
bug-hunter / scripts/run.py — file-based output contract entry point (atomic write).

Self-contained resolve_result_path; does NOT import aiase_contract (unavailable
once installed under ~/.hermes/skills/).

--bugs takes a JSON array string. Each bug object is sanitized (severity/type
whitelist, line_start/line_end coerced to int). If verdict=clean, bugs is
forced to [].

Usage:
    python3 run.py --task_id "<id>" --verdict buggy \
        --bugs '[{"line_start":3,"line_end":3,"severity":"medium","type":"edge_case","description":"...","suggested_fix":"..."}]' \
        --confidence 0.9
"""
import os
import sys
import json
import argparse


ALLOWED_VERDICTS = {"buggy", "clean"}
ALLOWED_TYPES = {
    "off_by_one", "null_deref", "type_error", "logic_error",
    "edge_case", "api_misuse", "inefficient", "unhandled_input",
}
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}


def resolve_result_path() -> str:
    return os.environ.get("AIASE_RESULT_PATH") or os.path.join(os.getcwd(), "aiase_result.json")


def _clamp_confidence(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def _sanitize_bug(b):
    if not isinstance(b, dict):
        return None
    try:
        ls = int(b.get("line_start"))
        le = int(b.get("line_end", ls))
    except (TypeError, ValueError):
        return None
    if ls < 1 or le < ls:
        return None
    sev = str(b.get("severity", "")).strip().lower()
    typ = str(b.get("type", "")).strip().lower()
    if sev not in ALLOWED_SEVERITIES or typ not in ALLOWED_TYPES:
        return None
    return {
        "line_start": ls,
        "line_end": le,
        "severity": sev,
        "type": typ,
        "description": str(b.get("description", "")),
        "suggested_fix": str(b.get("suggested_fix", "")),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task_id", required=True)
    ap.add_argument("--verdict", required=True, choices=sorted(ALLOWED_VERDICTS))
    ap.add_argument("--bugs", default="[]", help="JSON array string of bug objects")
    ap.add_argument("--confidence", type=float, default=0.5)
    a = ap.parse_args()

    try:
        raw_bugs = json.loads(a.bugs)
        if not isinstance(raw_bugs, list):
            raise ValueError("bugs must be a JSON array")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"ERROR: --bugs is not a valid JSON array: {e}", file=sys.stderr)
        return 2

    bugs = [b for b in (_sanitize_bug(x) for x in raw_bugs) if b is not None]

    verdict = a.verdict
    if verdict == "clean":
        bugs = []

    result = {
        "task_id": a.task_id,
        "verdict": verdict,
        "bugs": bugs,
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
