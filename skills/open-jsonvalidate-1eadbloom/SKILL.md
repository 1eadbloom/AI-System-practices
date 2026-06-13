---
name: open-jsonvalidate-1eadbloom
description: Validate a JSON object against a JSON Schema (draft-07 subset) and emit a structured validation report with per-error path annotations.
version: 1.0.0
metadata:
  hermes:
    tags: [json, schema, validation, aiase-2026]
    category: data
---

# JSON Schema Validator Skill (Open Track)

## When to Use

When the user sends a JSON payload with `task_id`, `schema` (a JSON Schema object), and `instance` (the JSON value to validate). The skill must produce a structured report stating whether the instance is valid, and if not, exactly which paths and rules failed.

Trigger example:
```
/open-jsonvalidate-1eadbloom {"task_id":"open_001","schema":{"type":"object","required":["name","age"],"properties":{"name":{"type":"string"},"age":{"type":"integer","minimum":0}}},"instance":{"name":"Alice","age":-1}}
```

## Procedure

1. **Parse** the input JSON. Extract `task_id`, `schema`, `instance`.

2. **Run the deterministic validator** by executing:
   ```
   python scripts/validate.py '{"schema":<schema>,"instance":<instance>}'
   ```
   The script returns a fenced JSON block with:
   - `valid`: bool
   - `errors`: list of error objects (empty if valid)
   Each error object has `path` (JSON pointer string), `rule` (which keyword failed), `message` (human-readable).

3. **Review** the validator output. The deterministic script handles all validation logic ??do NOT second-guess its `valid` result or add/remove errors. Your job is to format the final contract output.

4. **Emit** the contract by running:
   ```
   python scripts/run.py '{"task_id":"<task_id>","valid":<true/false>,"errors":[<errors>],"error_count":<n>,"confidence":1.0}'
   ```
   Output the resulting fenced JSON block **unchanged as your final response**. Do not add text after it.

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

## Output Contract

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
- `confidence`: always 1.0 (deterministic result ??no LLM guessing).

## Pitfalls

- Do not add or remove errors from the validator output.
- `error_count` must match `len(errors)` exactly.
- `valid=true` requires `errors=[]` and `error_count=0`.
- `task_id` must match input exactly.



## Verification

`scripts/validate.py` is a fully deterministic JSON Schema draft-07 subset validator (pure stdlib). Given the same `schema` and `instance`, it always produces the same `valid` boolean and `errors` list. The grader compares `valid`, `error_count`, and each error's `path`+`rule` against ground truth.

`scripts/run.py` enforces the output contract shape: `valid=true` requires `errors=[]` and `error_count=0`; if `valid=true` but `errors` is non-empty, `run.py` overrides `valid` to `false`. The last fenced JSON block in stdout is the grader's input.
