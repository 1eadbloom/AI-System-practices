#!/usr/bin/env python3
"""
text2sql skill output wrapper.
Accepts either:
  1. argv[1] with JSON payload (normal harness call)
  2. stdin with LLM raw output (extracts SQL automatically)
"""
import json, re, sys

def extract_sql(text):
    # Try fenced sql block
    m = re.search(r'```sql\s*(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Try fenced block (any)
    m = re.search(r'```\w*\s*(SELECT.*?)```', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Try bare SELECT
    m = re.search(r'(SELECT\s+.+)', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip().split('\n\n')[0]
    return None

def emit(obj):
    sys.stdout.write("```json\n")
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.stdout.write("\n```\n")

def main():
    if len(sys.argv) >= 2:
        try:
            payload = json.loads(sys.argv[1])
            emit(payload)
            return
        except json.JSONDecodeError:
            pass
    # Read from stdin
    text = sys.stdin.read()
    sql = extract_sql(text)
    if not sql:
        emit({"task_id": "", "sql": "", "rationale": "failed to extract SQL", "confidence": 0.0})
        return
    # Try to get task_id from text
    m = re.search(r'task_id["\s:]+([a-zA-Z0-9_]+)', text)
    task_id = m.group(1) if m else ""
    emit({"task_id": task_id, "sql": sql, "rationale": "extracted from output", "confidence": 0.7})

if __name__ == "__main__":
    main()
