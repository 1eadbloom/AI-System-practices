#!/usr/bin/env python3
"""
Deterministic JSON Schema validator (draft-07 subset).

Usage:
    python validate.py '{"schema": {...}, "instance": <any>}'

Prints a single fenced JSON block:
    {"valid": bool, "errors": [{"path": str, "rule": str, "message": str}]}

Supported keywords:
    type, required, properties, additionalProperties,
    minimum, maximum, exclusiveMinimum, exclusiveMaximum,
    minLength, maxLength, minItems, maxItems, items,
    enum, const, pattern, allOf, anyOf, oneOf, not
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


def _emit(obj: dict) -> int:
    sys.stdout.write("```json\n")
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.stdout.write("\n```\n")
    return 0


def _type_name(v: Any) -> str:
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    if v is None:
        return "null"
    return type(v).__name__


def _matches_type(v: Any, t: str) -> bool:
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    return _type_name(v) == t


def validate(schema: Any, instance: Any, path: str = "") -> list[dict]:
    """Recursively validate instance against schema; return list of error dicts."""
    if not isinstance(schema, dict):
        return []

    errors: list[dict] = []

    def err(rule: str, msg: str) -> None:
        errors.append({"path": path or "/", "rule": rule, "message": msg})

    # --- type ---
    if "type" in schema:
        t = schema["type"]
        types = t if isinstance(t, list) else [t]
        if not any(_matches_type(instance, tp) for tp in types):
            err("type", f"Expected type {t}, got {_type_name(instance)}")
            # If type is fundamentally wrong, skip further keyword checks
            return errors

    # --- enum ---
    if "enum" in schema:
        if instance not in schema["enum"]:
            err("enum", f"Value {json.dumps(instance)} not in enum {json.dumps(schema['enum'])}")

    # --- const ---
    if "const" in schema:
        if instance != schema["const"]:
            err("const", f"Value {json.dumps(instance)} does not equal const {json.dumps(schema['const'])}")

    # --- string keywords ---
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            err("minLength", f"String length {len(instance)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            err("maxLength", f"String length {len(instance)} > maxLength {schema['maxLength']}")
        if "pattern" in schema:
            try:
                if not re.search(schema["pattern"], instance):
                    err("pattern", f"String {json.dumps(instance)!r} does not match pattern {schema['pattern']!r}")
            except re.error as e:
                err("pattern", f"Invalid regex pattern: {e}")

    # --- numeric keywords ---
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            err("minimum", f"Value {instance} is less than minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            err("maximum", f"Value {instance} is greater than maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            err("exclusiveMinimum", f"Value {instance} is not greater than exclusiveMinimum {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            err("exclusiveMaximum", f"Value {instance} is not less than exclusiveMaximum {schema['exclusiveMaximum']}")

    # --- array keywords ---
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            err("minItems", f"Array length {len(instance)} < minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            err("maxItems", f"Array length {len(instance)} > maxItems {schema['maxItems']}")
        if "items" in schema:
            item_schema = schema["items"]
            for i, item in enumerate(instance):
                child_path = f"{path}/{i}"
                errors.extend(validate(item_schema, item, child_path))

    # --- object keywords ---
    if isinstance(instance, dict):
        if "required" in schema:
            for key in schema["required"]:
                if key not in instance:
                    err("required", f"Required property {key!r} is missing")
        if "properties" in schema:
            for key, sub_schema in schema["properties"].items():
                if key in instance:
                    child_path = f"{path}/{key}"
                    errors.extend(validate(sub_schema, instance[key], child_path))
        if "additionalProperties" in schema:
            ap = schema["additionalProperties"]
            known = set(schema.get("properties", {}).keys())
            extra_keys = [k for k in instance if k not in known]
            if ap is False:
                for k in extra_keys:
                    err("additionalProperties", f"Additional property {k!r} not allowed")
            elif isinstance(ap, dict):
                for k in extra_keys:
                    child_path = f"{path}/{k}"
                    errors.extend(validate(ap, instance[k], child_path))

    # --- logical combinators ---
    if "allOf" in schema:
        for i, sub in enumerate(schema["allOf"]):
            sub_errors = validate(sub, instance, path)
            if sub_errors:
                for e in sub_errors:
                    e["rule"] = f"allOf[{i}]/{e['rule']}"
                errors.extend(sub_errors)

    if "anyOf" in schema:
        sub_results = [validate(sub, instance, path) for sub in schema["anyOf"]]
        if not any(not r for r in sub_results):
            closest_idx = min(range(len(sub_results)), key=lambda i: len(sub_results[i]))
            err("anyOf", f"Failed all anyOf branches. Closest branch={closest_idx}, errors={len(sub_results[closest_idx])}")

    if "oneOf" in schema:
        branch_results = [validate(sub, instance, path) for sub in schema["oneOf"]]
        matching = [i for i, r in enumerate(branch_results) if not r]
        if len(matching) != 1:
            if len(matching) == 0:
                closest_idx = min(range(len(branch_results)), key=lambda i: len(branch_results[i]))
                err("oneOf", f"Expected exactly one branch. Matched none. Closest branch={closest_idx}")
            else:
                err("oneOf", f"Expected exactly one branch. Matched branches={matching}")

    # --- not ---
    if "not" in schema:
        sub_errors = validate(schema["not"], instance, path)
        if not sub_errors:
            err("not", "Value must NOT match the 'not' sub-schema, but it does")

    return errors


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _emit({"valid": False, "errors": [{"path": "/", "rule": "usage", "message": "usage: validate.py '<json>'"}]})
    try:
        payload = json.loads(argv[1])
    except json.JSONDecodeError as e:
        return _emit({"valid": False, "errors": [{"path": "/", "rule": "parse", "message": f"argv JSON invalid: {e}"}]})

    schema = payload.get("schema", {})
    instance = payload.get("instance")
    errors = validate(schema, instance)
    return _emit({"valid": len(errors) == 0, "errors": errors})


if __name__ == "__main__":
    sys.exit(main(sys.argv))
