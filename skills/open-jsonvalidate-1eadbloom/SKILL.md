---
name: open-jsonvalidate-1eadbloom
description: Validate a JSON object against a JSON Schema (draft-07 subset) and write a structured validation report via scripts/run.py (file-based output contract). AIASE 2026 Open Track.
version: 2.1.0
metadata:
  hermes:
    tags: [json, schema, validation, aiase-2026]
    category: data
    requires_toolsets: [terminal]
---

# JSON Schema Validator Skill (Open Track, file-based output contract)

## When to Use

When the user sends a JSON payload with `task_id`, `schema` (a JSON Schema object), and `instance` (the JSON value to validate). The skill must produce a structured report stating whether the instance is valid, and if not, exactly which paths and rules failed.

Trigger example:
```
/open-jsonvalidate-1eadbloom {"task_id":"open_001","schema":{"type":"object","required":["name","age"],"properties":{"name":{"type":"string"},"age":{"type":"integer","minimum":0}}},"instance":{"name":"Alice","age":-1}}
```

## Procedure

1. **Parse** the input JSON. Extract `task_id`, `schema`, `instance`.

2. **Run the deterministic validator** using the `terminal` tool with an **absolute path**:(`<skill_dir>` is given to you by Hermes via `[Skill directory: ...]`):
   ```
   python3 <skill_dir>/scripts/validate.py '{"schema":<schema>,"instance":<instance>}'
   ```
   The script returns a fenced JSON block with:
   - `valid`: bool
   - `errors`: list of error objects (empty if valid)
   Each error object has `path` (JSON pointer string), `rule` (which keyword failed), `message` (human-readable).

3. **⚠️ CRITICAL — copy the validator's output verbatim.** Read the `valid` field and `errors` array EXACTLY as printed by `validate.py`. Do NOT recompute, re-judge, or override these values based on your own reading of the schema — even if your intuition disagrees. The validator is the deterministic ground truth; your own judgment is not. If `validate.py` says `valid: false`, you MUST pass `--valid false` to `run.py`, with no exceptions.

4. **Write the result file.** Use the `terminal` tool and run, with an **absolute path**, using the EXACT `valid` and `errors` values from step 2's output:
```
python3 <skill_dir>/scripts/run.py 

--task_id "<task_id>" 

--valid <exact value from validate.py> 

--errors '<exact errors array from validate.py, or [] if valid>' 

--confidence 1.0   
```
This writes the result to the file given by the `AIASE_RESULT_PATH` environment variable (or `./aiase_result.json` if unset). **You do not need to print or repeat the JSON in the chat message** — the grader reads the result file, not your reply.

## Supported JSON Schema keywords (draft-07 subset)

The validator supports:
- `type`: string, number, integer, boolean, array, object, null (and arrays of types)
- `required`: list of required property names
- `properties`: per-property sub-schemas
- `additionalProperties`: false (rejects extra keys) or a sub-schema
- `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`: numeric bounds
- `minLength`, `maxLength`: string length bounds
- `minItems`, `maxItems`: array length bounds
- `items`: array item sub-schema (applied to all items)
- `enum`: value must be one of the listed values
- `const`: value must equal this constant
- `pattern`: string must match this regex
- `allOf`, `anyOf`, `oneOf`: logical combinators
- `not`: instance must NOT validate against the given sub-schema (e.g. `{"not":{"enum":["banned","deleted"]}}` rejects those two values and accepts anything else)

## Output Contract (result file)

```json
{
  "task_id": "open_001",
  "valid": false,
  "errors": [
    {
      "path": "/age",
      "rule": "minimum",
      "message": "Value -1 is less than minimum 0"
    }
  ],
  "error_count": 1,
  "confidence": 1.0
}
```

- `valid`: true iff the instance fully conforms to the schema.
- `errors`: empty array when valid=true; list of error objects otherwise.
- `error_count`: must equal `len(errors)`.
- `confidence`: always 1.0 (deterministic result — no LLM guessing).

## Pitfalls

- Do not add or remove errors from the validator output.
- `error_count` must match `len(errors)` exactly.
- `valid=true` requires `errors=[]` and `error_count=0`.
- `task_id` must match input exactly.
- A `not` violation reports `rule: "not"` at the path of the sub-schema that was supposed to fail but didn't — don't confuse this with the keyword inside the `not` block.
- **Do not use process/background tools** to run `scripts/run.py` — use the synchronous `terminal` tool so the write completes before your turn ends.

## Verification

`scripts/validate.py` is a fully deterministic JSON Schema draft-07 subset validator (pure stdlib). Given the same `schema` and `instance`, it always produces the same `valid` boolean and `errors` list. The grader compares `valid`, `error_count`, and each error's `path`+`rule` against ground truth.

`scripts/run.py` enforces the output contract shape: `valid=true` requires `errors=[]` and `error_count=0`; if `valid=true` but `errors` is non-empty, `run.py` overrides `valid` to `false`. The result file must exist and be a valid JSON object with `task_id` matching the input.
