#!/usr/bin/env python3
"""
bug-hunter analyzer -- deterministic edge-input probing with optional oracle comparison.

Usage:
    python analyze.py '{
        "code": "...",
        "entry_function": "<entry_name>",
        "edge_inputs": [          # optional; if omitted, a generic battery is used
            {"input": [[]],          "label": "empty container"},
            {"input": [0],           "label": "zero"},
            {"input": [[1,2,3], 1],  "label": "first element", "expected": 1}
        ]
    }'

Prints a single fenced JSON block:
    {"entry_found": bool,
     "ast_lines": {"entry_def": int, "return_lines": [int], "loop_lines": [int]},
     "probes": [{"label": str, "outcome": "ok"|"crash"|"timeout"|"mismatch", "error": str,
                  "actual": <any, present when outcome in {ok, mismatch}>,
                  "expected": <any, present if the probe supplied "expected">}],
     "suspicious_lines": [int],
     "summary": str}

This is the deterministic side of the bug-hunter; the LLM uses it as evidence,
but still makes the final bug-vs-not-bug judgment.

Oracle-based probing: if a probe in `edge_inputs` includes an "expected" key,
the probe's return value is compared against it with `==`. A mismatch produces
outcome="mismatch" -- this is how *silent* logic errors (wrong answer, no crash)
get surfaced, which "crash vs ok vs timeout" alone cannot detect.
"""

from __future__ import annotations

import ast
import json
import signal
import sys
import traceback
from contextlib import contextmanager


def _emit(obj: dict) -> int:
    sys.stdout.write("```json\n")
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.stdout.write("\n```\n")
    return 0


def _ast_features(code: str, entry: str) -> dict:
    out = {"entry_def": -1, "return_lines": [], "loop_lines": []}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entry:
            out["entry_def"] = node.lineno
        if isinstance(node, ast.Return) and node.lineno:
            out["return_lines"].append(node.lineno)
        if isinstance(node, (ast.For, ast.While)) and node.lineno:
            out["loop_lines"].append(node.lineno)
    out["return_lines"].sort()
    out["loop_lines"].sort()
    return out


class _Timeout(Exception):
    pass


@contextmanager
def _time_limit(seconds: float):
    """SIGALRM-based timeout. POSIX only; Windows users will get no timeout."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return
    def _handler(signum, frame):
        raise _Timeout("probe timed out")
    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def _default_battery() -> list[dict]:
    """
    Task-agnostic shape probes. Each item passes a single positional argument
    of a common "shape category" (empty container, singleton, two-element,
    extremes, None). The probe layer only judges "crash vs ok vs timeout" and
    pins a line if the traceback points inside <candidate>; whether a crash
    is a *real* bug is your skill's call.

    Probes that fail with TypeError because the entry function has a different
    arity will not contribute a `bad_line` (their traceback is outside
    <candidate>), so wrong-arity noise does not pollute suspicious_lines.

    For more targeted probing, callers should pass `edge_inputs` in the
    payload instead of relying on this generic battery. Include an "expected"
    key on any probe to enable oracle-based mismatch detection (catches
    silent wrong-answer bugs that don't crash).
    """
    return [
        {"input": [[]],                "label": "empty list"},
        {"input": [[0]],               "label": "singleton list"},
        {"input": [[0, 0]],            "label": "two-element list (repeats)"},
        {"input": [[0, 1]],            "label": "two-element list (distinct)"},
        {"input": [""],                "label": "empty string"},
        {"input": ["a"],               "label": "single-char string"},
        {"input": [0],                 "label": "zero"},
        {"input": [-1],                "label": "negative integer"},
        {"input": [10**6],             "label": "large integer"},
        {"input": [None],              "label": "None"},
    ]


def _probe(code: str, entry: str, sample: dict, timeout_sec: float) -> dict:
    label = sample.get("label", "?")
    has_expected = "expected" in sample
    expected = sample.get("expected")

    ns: dict = {}
    try:
        exec(compile(code, "<candidate>", "exec"), ns)
    except Exception as e:
        r = {"label": label, "outcome": "crash",
             "error": f"compile/exec error: {e!r}"}
        if has_expected:
            r["expected"] = expected
        return r
    fn = ns.get(entry)
    if not callable(fn):
        r = {"label": label, "outcome": "crash",
             "error": f"entry function {entry!r} not defined"}
        if has_expected:
            r["expected"] = expected
        return r
    args = sample.get("input", [])
    try:
        with _time_limit(timeout_sec):
            actual = fn(*args) if isinstance(args, list) else fn(args)
        if has_expected:
            if actual == expected:
                return {"label": label, "outcome": "ok", "error": "",
                        "actual": actual, "expected": expected}
            else:
                return {"label": label, "outcome": "mismatch",
                        "error": f"expected {expected!r}, got {actual!r}",
                        "actual": actual, "expected": expected}
        return {"label": label, "outcome": "ok", "error": "", "actual": actual}
    except _Timeout as e:
        r = {"label": label, "outcome": "timeout", "error": str(e)}
        if has_expected:
            r["expected"] = expected
        return r
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        # Walk the traceback to find the deepest frame inside <candidate>
        # to pinpoint the suspicious line.
        bad_line = -1
        for f in tb:
            if f.filename == "<candidate>" and f.lineno:
                bad_line = f.lineno
        r = {
            "label": label,
            "outcome": "crash",
            "error": f"{type(e).__name__}: {e}",
            "bad_line": bad_line,
        }
        if has_expected:
            r["expected"] = expected
        return r


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _emit({"entry_found": False, "ast_lines": {}, "probes": [],
                      "suspicious_lines": [], "summary": "usage: analyze.py '<json>'"})
    try:
        payload = json.loads(argv[1])
    except json.JSONDecodeError as e:
        return _emit({"entry_found": False, "ast_lines": {}, "probes": [],
                      "suspicious_lines": [], "summary": f"argv JSON invalid: {e}"})

    code = str(payload.get("code", ""))
    entry = str(payload.get("entry_function", ""))
    samples = payload.get("edge_inputs") or _default_battery()
    timeout_sec = float(payload.get("timeout_sec", 1.0))

    ast_lines = _ast_features(code, entry)
    entry_found = ast_lines.get("entry_def", -1) > 0

    probes = []
    suspicious: set[int] = set()
    for s in samples:
        r = _probe(code, entry, s, timeout_sec)
        probes.append(r)
        if r["outcome"] != "ok" and r.get("bad_line", -1) > 0:
            suspicious.add(r["bad_line"])
        # A mismatch (wrong-but-non-crashing output) is also evidence of a bug,
        # even though it has no traceback to pin a line. Surface it via the
        # AST's return_lines so the LLM has somewhere concrete to look.
        if r["outcome"] == "mismatch":
            for rl in ast_lines.get("return_lines", []):
                suspicious.add(rl)

    crashes = sum(1 for r in probes if r["outcome"] == "crash")
    timeouts = sum(1 for r in probes if r["outcome"] == "timeout")
    mismatches = sum(1 for r in probes if r["outcome"] == "mismatch")
    ok = len(probes) - crashes - timeouts - mismatches
    summary = (
        f"{len(probes)} probes; {crashes} crash, {timeouts} timeout, "
        f"{mismatches} mismatch (wrong answer, no crash), {ok} ok; "
        f"suspicious_lines={sorted(suspicious)}"
    )

    return _emit({
        "entry_found": entry_found,
        "ast_lines": ast_lines,
        "probes": probes,
        "suspicious_lines": sorted(suspicious),
        "summary": summary,
    })


if __name__ == "__main__":
    sys.exit(main(sys.argv))
