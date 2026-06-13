---
name: code-author-1eadbloom
description: Implement a Python function from a natural-language task description, self-test with edge cases, and emit the AIASE 2026 Pairwise Code Author contract.
version: 1.0.0
metadata:
  hermes:
    tags: [code, python, aiase-2026]
    category: code
---

# Code Author Skill (Pairwise Track)

## When to Use

When the user sends a JSON payload with `task_description`, `constraints` (entry_function, max_loc, imports_forbidden), and `task_id`. Produce a correct Python implementation.

Trigger example:
```
/code-author-1eadbloom {"task_id":"task_042","task_description":"Implement merge_intervals(intervals): merge overlapping intervals, empty input returns [].","constraints":{"entry_function":"merge_intervals","max_loc":500,"imports_forbidden":["os","sys"]}}
```

## Procedure

1. **Parse** the payload. Extract `task_id`, `task_description`, `constraints.entry_function`, `constraints.max_loc`, `constraints.imports_forbidden`.

2. **Analyse the spec carefully.** Before writing code, identify:
   - What does the function receive as input? What types?
   - What must it return?
   - What edge cases does the spec mention? (Empty input, single element, None, negative, duplicates, unsorted input, boundary values.)
   - What **must not** be imported from `imports_forbidden`?

3. **Write the implementation.** Rules:
   - Define exactly the function named `constraints.entry_function`.
   - Handle ALL edge cases explicitly (empty list/string/dict, single-element, None inputs, k out-of-bounds, etc.).
   - Use only stdlib unless other imports are clearly needed and not forbidden.
   - Keep code idiomatic and lean (under `constraints.max_loc` S-LOC).
   - Do NOT use `os`, `sys`, `subprocess`, or any module in `imports_forbidden`.

4. **Generate sample_inputs** for self-testing. For every function, include AT MINIMUM:
   - Empty input case (e.g., `[]`, `""`, `{}`)
   - Single-element case
   - Two-element case (both equal and distinct)
   - Typical multi-element case
   - Boundary/extreme cases mentioned in the spec

   Format:
   ```json
   [
     {"input": [[]], "expected": []},
     {"input": [[[1,3]]], "expected": [[1,3]]},
     {"input": [[[1,3],[2,4]]], "expected": [[1,4]]}
   ]
   ```
   Where `input` is a list of positional arguments to the function.

5. **Self-test** by running:
   ```
   python scripts/selftest.py '{"code":"<your_code>","constraints":<constraints_object>,"sample_inputs":<your_sample_inputs>}'
   ```
   Read the fenced JSON block returned. Check `passed`, `failed`, `errors`, `sloc`, `loc_violation`, `import_violations`.
   - If `failed > 0` or `import_violations` non-empty or `loc_violation=true`: fix the code and retry. Maximum **3 retries**.
   - If `sloc > constraints.max_loc`: simplify code.
   - After 3 failures, proceed with best version and `confidence=0.3`.

6. **Emit** the contract by running:
   ```
   python scripts/run.py '{"task_id":"<task_id>","code":"<final_code>","loc":<sloc>,"self_test_results":{"passed":<n>,"failed":<m>},"rationale":"<one sentence>","confidence":<0.0-1.0>}'
   ```
   Output the resulting fenced JSON block **unchanged as your final response**. Do not add text after it.

## Implementation Patterns

**Always guard empty input first:**
```python
def f(items):
    if not items:
        return []
    # ... rest of logic
```

**Validate k-index parameters before use:**
```python
def kth_smallest(nums, k):
    if not nums or k < 1 or k > len(nums):
        return None
    return sorted(nums)[k - 1]  # 1-indexed
```

**Sort-then-sweep for interval/merge problems:**
```python
def merge_intervals(intervals):
    if not intervals:
        return []
    items = sorted(intervals, key=lambda x: x[0])
    merged = [list(items[0])]
    for cur in items[1:]:
        if cur[0] <= merged[-1][1]:  # Note: <= to handle touching intervals
            merged[-1][1] = max(merged[-1][1], cur[1])
        else:
            merged.append(list(cur))
    return merged
```

**Binary search ??use inclusive bounds consistently:**
```python
def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1  # inclusive on both ends
    while lo <= hi:            # <= not <
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
```

**CSV parsing ??track quoting state explicitly:**
```python
def parse_csv_line(line):
    fields, cur, in_q = [], [], False
    i = 0
    while i < len(line):
        c = line[i]
        if in_q:
            if c == '"' and i + 1 < len(line) and line[i+1] == '"':
                cur.append('"'); i += 2; continue
            elif c == '"':
                in_q = False
            else:
                cur.append(c)
        else:
            if c == '"':
                in_q = True
            elif c == ',':
                fields.append(''.join(cur)); cur = []
            else:
                cur.append(c)
        i += 1
    fields.append(''.join(cur))
    return fields
```

## Pitfalls

- **Missing empty-input guard** ??most common failure. ALWAYS add `if not items: return ...` at the top.
- **Off-by-one in binary search** ??use `while lo <= hi` with inclusive `hi = len(arr)-1`, never `while lo < hi`.
- **Touching intervals** ??use `<=` not `<` when merging: `[1,2]` and `[2,3]` should merge to `[1,3]`.
- **1-indexed k** ??when spec says "k-th smallest with k=1 returns minimum", use `sorted(nums)[k-1]`, not `[k]`.
- **set() removes duplicates** ??if spec says duplicates count, do NOT deduplicate before sorting.
- **Mutating input** ??`intervals.sort()` mutates caller's list; use `sorted(intervals, ...)` to be safe.
- **Forbidden imports** ??always check `constraints.imports_forbidden`. The harness will catch violations.

## Verification

`scripts/selftest.py` checks: SLOC with radon, import violations via AST, runs each sample_input and compares to expected. The grader re-runs `radon raw` independently ??your reported `loc` is for reference only.


