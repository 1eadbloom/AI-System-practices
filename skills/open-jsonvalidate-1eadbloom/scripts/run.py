#!/usr/bin/env python3
"""
open-jsonvalidate skill ??final output wrapper.

Reads JSON from argv[1] with {task_id, valid, errors, error_count, confidence};
enforces contract shape and consistency rules; emits a single fenced JSON block.
"""

from __future__ import annotations

import json
import sys


def _clamp_confidence(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, f))


def _sanitize_error(e: dict) -> dict | None:
    if not isinstance(e, dict):
        return None
    return {
        "path": str(e.get("path", "/")),
        "rule": str(e.get("rule", "")),
        "message": str(e.get("message", "")),
    }


def emit_contract(obj: dict) -> int:
    valid = bool(obj.get("valid", False))
    raw_errors = obj.get("errors") or []
    if not isinstance(raw_errors, list):
        raw_errors = []
    errors = [e for e in (_sanitize_error(x) for x in raw_errors) if e is not None]

    # Enforce consistency: valid=true requires errors=[]
    if valid and errors:
        valid = False  # evidence overrides claim

    out = {
        "task_id": str(obj.get("task_id", "")),
        "valid": valid,
        "errors": errors,
        "error_count": len(errors),
        "confidence": _clamp_confidence(obj.get("confidence", 1.0)),
    }
    sys.stdout.write("```json\n")
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2))
    sys.stdout.write("\n```\n")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return emit_contract({
            "task_id": "", "valid": False,
            "errors": [{"path": "/", "rule": "invocation", "message": "run.py invoked without payload"}],
            "error_count": 1, "confidence": 0.0,
        })
    try:
        payload = json.loads(argv[1])
        if not isinstance(payload, dict):
            raise ValueError("payload not an object")
    except (json.JSONDecodeError, ValueError) as e:
        return emit_contract({
            "task_id": "", "valid": False,
            "errors": [{"path": "/", "rule": "parse", "message": f"invalid argv JSON: {e}"}],
            "error_count": 1, "confidence": 0.0,
        })
    return emit_contract(payload)


if __name__ == "__main__":
    sys.exit(main(sys.argv))


