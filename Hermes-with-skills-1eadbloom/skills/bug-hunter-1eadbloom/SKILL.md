---
name: bug-hunter-1eadbloom
description: Audit a Python function for bugs against its task description and write a structured bug report via scripts/run.py (file-based output contract). AIASE 2026 Pairwise Track (Bug Hunter role).
version: 2.1.0
metadata:
  hermes:
    tags: [code, audit, python, aiase-2026]
    category: code
    requires_toolsets: [terminal]
---

# Bug Hunter Skill (Pairwise Track, file-based output contract)

## When to Use

When the user sends a JSON payload with `code` (Python source), `task_description`, and `task_id`. Produce a structured bug report.

Trigger example:
```
/bug-hunter-1eadbloom {"task_id":"task_042","code":"def merge_intervals(intervals): ...","task_description":"Merge overlapping intervals, empty input returns []."}
```

## Procedure

1. **Parse** the payload. Extract `task_id`, `code`, `task_description`. Note: `code` is 1-indexed, every line counts (including blank lines and comments).

2. **Extract the entry function name** from the code by looking for the first `def` statement.

3. **Run the deterministic analyzer** to get AST structure + edge-input probe results, using the `terminal` tool with an **absolute path** (`<skill_dir>` is given to you by Hermes via `[Skill directory: ...]`):
   ```
   python3 <skill_dir>/scripts/analyze.py '{"code":"<code>","entry_function":"<entry>","edge_inputs":[<task_specific_probes>]}'
   ```
   Use task-specific `edge_inputs` based on the `task_description`:
   - For **list/interval/array** functions: `[{"input":[[]],"label":"empty"},{"input":[[[1,3]]],"label":"single"},{"input":[[[1,3],[2,4]]],"label":"overlap"},{"input":[[[1,2],[2,3]]],"label":"touching"}]`
   - For **search** functions: `[{"input":[[],0],"label":"empty arr"},{"input":[[5],5],"label":"singleton hit"},{"input":[[5],9],"label":"singleton miss"},{"input":[[1,2,3],1],"label":"first"},{"input":[[1,2,3],3],"label":"last"}]`
   - For **string/CSV** functions: `[{"input":[""],"label":"empty string"},{"input":["a"],"label":"single char"},{"input":["a,b"],"label":"two fields"},{"input":["\"a,b\",c"],"label":"quoted comma"},{"input":["\"\""],"label":"empty quoted"}]`
   - For **grid/DP** functions: `[{"input":[1,1],"label":"1x1"},{"input":[1,5],"label":"single row"},{"input":[5,1],"label":"single col"},{"input":[3,3],"label":"3x3"},{"input":[0,3],"label":"zero dim"}]`
   - For **k-th element** functions: `[{"input":[[],1],"label":"empty"},{"input":[[5],1],"label":"single k1"},{"input":[[1,2,3],0],"label":"k=0 invalid"},{"input":[[1,2,3],4],"label":"k>len"},{"input":[[1,1,1],2],"label":"duplicates"}]`
   - For **unknown type**: use the default battery (omit `edge_inputs` key).

   **Oracle-based probing (important — use whenever you can compute the right answer):**
   If `task_description` gives you enough information to know the *correct* return value for a probe input (e.g. "binary_search([1,2,3], 1) should return 0" follows directly from the spec), add an `"expected"` key to that probe:
   ```json
   {"input":[[1,2,3],1],"label":"first","expected":0}
   ```
   The analyzer will then report `outcome: "mismatch"` (with `actual` vs `expected`) for probes whose result is *wrong but does not crash*. This is the ONLY way to catch silent logic errors — e.g. a `binary_search` with `while lo < hi` (instead of `<=`) that returns `-1` for a target that exists, without raising any exception. A probe that only checks "does it crash" will report `outcome: "ok"` for such a function and miss the bug entirely. Add `"expected"` to at least the 2-3 probes where you can confidently derive the correct value from the spec.

4. **Analyse the probe results.**
   - For each crashed/timed-out probe: is the crash on a line inside the function (`bad_line` > 0)? → Strong evidence of bug.
   - **For each `mismatch` probe: this is direct evidence of a silent logic error** — the function ran without error but returned the wrong value. Treat this with the same weight as a crash; read the code around `suspicious_lines` (which includes `return_lines` for mismatches, since there's no traceback to pin a line) to find the faulty condition/recurrence.
   - What type of input caused it? → Classify (edge_case, off_by_one, unhandled_input, logic_error, etc.)

5. **Read the code carefully** for the following patterns:
   - **Missing empty guard:** Does the first line of the function body access `input[0]`, `input[-1]`, or iterate without checking `if not input`?
   - **Off-by-one in loops:** `range(n-1)` vs `range(n)`, `< n` vs `<= n`, `while lo < hi` vs `while lo <= hi`.
   - **1-indexed vs 0-indexed k:** Does `sorted(arr)[k]` appear when spec says k=1 means minimum? → off_by_one.
   - **set() deduplication:** Does `set(arr)` appear before sorting when spec says duplicates count? → logic_error.
   - **Inconsistent bounds in binary search:** `hi = len(arr)` (exclusive) paired with `hi = mid - 1` (inclusive shrink) → logic_error. **This is the classic silent-mismatch case** — it doesn't crash, it just returns -1 incorrectly.
   - **Touching-interval off-by-one:** `cur[0] < merged[-1][1]` instead of `<=` when spec says touching intervals merge → off_by_one.
   - **Quoted-field CSV parsing:** Simple split or toggle-on-every-quote approach → unhandled_input or edge_case.
   - **Wrong DP recurrence:** `dp[i][j] + dp[i][j]` (reads self) instead of `dp[i][j-1]` → logic_error.
   - **Missing k bounds validation:** No check `k < 1 or k > len(nums)` → unhandled_input.

6. **Calibrate severity accurately:**
   - `critical`: Always produces wrong answer on typical input, or crashes on normal non-edge input.
   - `high`: Wrong answer or crash on common inputs (e.g., sorted array with target at position 0, standard interval list). A `mismatch` on a "first/last element" style probe is typically `high`.
   - `medium`: Wrong answer only on edge/boundary inputs (empty list, touching intervals, k=len, single element).
   - `low`: Correctness unaffected; only style/efficiency concern.

   **Do NOT over-report.** False positives on clean code are penalized (25% of your grade). If you are unsure whether something is a bug vs design choice, default to NOT reporting it unless the probe directly crashed or mismatched on it.

7. **Decide verdict:**
   - `buggy` if you found at least one concrete, evidence-backed bug (crash, timeout, or mismatch).
   - `clean` if all probes passed (`outcome: "ok"` for all) and no clear logic/spec violation found.
   - If `verdict=clean`, `bugs` MUST be `[]`.

8. **Write the result file.** Use the `terminal` tool (NOT a process/background tool) and run, with an **absolute path**:
   ```
   python3 <skill_dir>/scripts/run.py \
     --task_id "<task_id>" \
     --verdict "<buggy|clean>" \
     --bugs '<JSON array of bug objects, or [] if clean>' \
     --confidence <0.0-1.0>
   ```
   This writes the result to the file given by the `AIASE_RESULT_PATH` environment variable (or `./aiase_result.json` if unset). **You do not need to print or repeat the JSON in the chat message** — the grader reads the result file, not your reply.

## Bug Object Format

Each bug object must have exactly:
- `line_start`: integer, 1-indexed, first line of the buggy code region
- `line_end`: integer, 1-indexed, >= line_start
- `severity`: one of `critical`, `high`, `medium`, `low`
- `type`: one of `off_by_one`, `null_deref`, `type_error`, `logic_error`, `edge_case`, `api_misuse`, `inefficient`, `unhandled_input`
- `description`: what is wrong and on what input it manifests
- `suggested_fix`: specific, actionable fix

**Line numbers point to the bug location in `code`, not to the task description or test harness.**

## Pitfalls

- **Over-reporting clean code:** If probes all pass and code logic looks correct, report `verdict=clean`. Marking style issues as `high` severity destroys your false-positive score.
- **Under-reporting obvious bugs:** If `empty list` probe crashes, that's definitely a bug. Report it.
- **Under-reporting silent bugs:** A probe with `outcome: "ok"` but no `expected` key tells you NOTHING about correctness — it only means "didn't crash". Always add `expected` to probes where the spec gives you an unambiguous correct answer, otherwise you will systematically miss off-by-one bugs that don't crash.
- **Wrong line numbers:** Count from line 1 of the `code` field (including blank lines). If line 3 is `merged = [intervals[0]]` and that crashes on empty input, `line_start=3`.
- **Reporting test infrastructure as bugs:** Don't report things like "no type hints" or "no docstring" — these are not bugs.
- **Wrong bug type:** An empty-input IndexError is `edge_case` (medium), not `null_deref`. Wrong operator (`<` vs `<=`) is `off_by_one`, not `logic_error`. A `mismatch` from wrong DP recurrence is `logic_error`.
- **Do not use process/background tools** to run `scripts/run.py` — use the synchronous `terminal` tool so the write completes before your turn ends.

## Verification

`scripts/analyze.py` gives deterministic probe evidence, including oracle-based `mismatch` detection when `expected` values are supplied. The LLM's job is to interpret that evidence + read the code carefully to produce a precise, calibrated bug report. The result file must exist, be a valid JSON object, have `task_id` matching the input, `verdict` in `{buggy, clean}`, and `bugs=[]` whenever `verdict=clean`.
