#!/usr/bin/env python3
"""
scripts/extract_schema.py — deterministic SQLite DDL -> {table: [columns]} extractor.

This is a pure-Python, deterministic helper: given the `db_schema` DDL string,
it parses every `CREATE TABLE` statement and returns the authoritative list of
table names and column names. The LLM should treat this output as ground truth
for column/table names — never guess from memory.

Usage:
    python3 extract_schema.py '{"schema_ddl": "CREATE TABLE Students (sid INTEGER PRIMARY KEY, name TEXT NOT NULL);\nCREATE TABLE Courses (cid INTEGER PRIMARY KEY, title TEXT);"}'

Output (fenced JSON):
    {"ok": true, "tables": {"Students": ["sid", "name"], "Courses": ["cid", "title"]}}
"""
import json
import re
import sys


# Matches: CREATE TABLE <name> ( <body> ) ;
_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"'`\[]?(\w+)[\"'`\]]?\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)

# A column definition starts with an identifier followed by a type/keyword.
# We exclude lines that are themselves constraints (PRIMARY KEY(...), FOREIGN KEY, etc.)
_CONSTRAINT_KEYWORDS = {
    "primary", "foreign", "unique", "check", "constraint",
}

_COL_NAME_RE = re.compile(r"^[\"'`\[]?(\w+)[\"'`\]]?\s+(.+)$")


def _split_top_level(body: str) -> list[str]:
    """Split a CREATE TABLE body on top-level commas (ignore commas inside parens)."""
    parts = []
    depth = 0
    cur = []
    for ch in body:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def extract_schema(ddl: str) -> dict:
    """Return {table_name: [column_name, ...]} for every CREATE TABLE in ddl."""
    tables = {}
    for m in _TABLE_RE.finditer(ddl):
        table_name = m.group(1)
        body = m.group(2)
        columns = []
        for piece in _split_top_level(body):
            first_word = piece.split(None, 1)[0].strip("\"'`[]").lower()
            if first_word in _CONSTRAINT_KEYWORDS:
                continue
            cm = _COL_NAME_RE.match(piece)
            if not cm:
                continue
            col_name = cm.group(1)
            columns.append(col_name)
        tables[table_name] = columns
    return tables


def _emit(obj: dict) -> int:
    sys.stdout.write("```json\n")
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.stdout.write("\n```\n")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _emit({"ok": False, "error": "usage: extract_schema.py '{\"schema_ddl\": \"...\"}'"})
    try:
        payload = json.loads(argv[1])
    except json.JSONDecodeError as e:
        return _emit({"ok": False, "error": f"invalid argv JSON: {e}"})

    ddl = payload.get("schema_ddl", "")
    if not isinstance(ddl, str) or not ddl.strip():
        return _emit({"ok": False, "error": "schema_ddl is empty or not a string"})

    tables = extract_schema(ddl)
    if not tables:
        return _emit({"ok": False, "error": "no CREATE TABLE statements found", "tables": {}})

    return _emit({"ok": True, "tables": tables})


if __name__ == "__main__":
    sys.exit(main(sys.argv))
