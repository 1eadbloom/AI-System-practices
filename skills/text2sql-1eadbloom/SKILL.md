---
name: text2sql-1eadbloom
description: Convert a natural-language question + SQLite schema into a verified read-only SQL query, then write the result via scripts/run.py (file-based output contract). AIASE 2026 Basic Track.
version: 2.0.0
metadata:
  hermes:
    tags: [sql, text2sql, data, aiase-2026]
    category: data
    requires_toolsets: [terminal]
---

# Text2SQL Skill (Basic Track, file-based output contract)

## When to Use

When the user sends a JSON payload with `question`, `db_schema` (SQLite DDL), and optional `task_id` + `dialect`. Produce a single read-only SQLite query whose result on the hidden DB matches the gold answer under bag equality.

Trigger example:
```
/text2sql-1eadbloom {"task_id":"task_nl2sql_017","question":"List the names ...","db_schema":"CREATE TABLE ...","dialect":"sqlite"}
```

## Procedure

1. **Parse** the input JSON. Extract `task_id`, `question`, `db_schema`, `dialect`.

2. **Analyse the schema carefully.**
   - List every table name and its columns exactly as spelled in the DDL.
   - Identify JOIN keys (foreign keys by name convention or obvious matching column names).
   - Note any LEFT JOIN candidates (questions like "include those with zero ..." or "even if no ...").

3. **Classify the question type** and apply the matching pattern:

   **Pattern A — Simple filter + JOIN:**
   Question: "Return names of students enrolled in course X."
   `SELECT DISTINCT s.name FROM Students s JOIN Enrollments e ON s.sid=e.sid JOIN Courses c ON e.cid=c.cid WHERE c.title='X'`

   **Pattern B — Aggregation + GROUP BY:**
   Question: "For each course return average score."
   `SELECT c.title, AVG(e.score) FROM Courses c JOIN Enrollments e ON c.cid=e.cid GROUP BY c.cid, c.title`

   **Pattern C — LEFT JOIN with COUNT (include zeros):**
   Question: "For each author return name and number of books, including those with zero."
   `SELECT a.name, COUNT(ba.bid) FROM Authors a LEFT JOIN BookAuthors ba ON a.aid=ba.aid GROUP BY a.aid, a.name`

   **Pattern D — TOP N with LIMIT:**
   Question: "Return top 2 categories by revenue."
   `SELECT p.category, SUM(p.price*oi.qty) AS revenue FROM Products p JOIN OrderItems oi ON p.pid=oi.pid GROUP BY p.category ORDER BY revenue DESC LIMIT 2`

   **Pattern E — UNION (two disjoint sets):**
   Question: "Return names of doctors in Cardiology plus names of patients seen by Cardiology doctors."
   `SELECT doc.name FROM Doctors doc JOIN Departments d ON doc.did=d.did WHERE d.name='Cardiology' UNION SELECT p.name FROM Patients p JOIN Appointments a ON p.pid=a.pid JOIN Doctors doc ON a.doc_id=doc.doc_id JOIN Departments d ON doc.did=d.did WHERE d.name='Cardiology'`

   **Pattern F — Nested subquery (tie-breaking / max of aggregates):**
   Question: "Return team that played most games as home team; if tie return all."
   `SELECT t.name FROM Teams t WHERE t.tid IN (SELECT home_tid FROM Games GROUP BY home_tid HAVING COUNT(*)=(SELECT MAX(c) FROM (SELECT COUNT(*) AS c FROM Games GROUP BY home_tid)))`

   **Pattern G — NOT EXISTS / NOT IN (exclusion):**
   Question: "Authors who wrote at least one book and none of whose books are on loan."
   `SELECT a.name FROM Authors a WHERE a.aid IN (SELECT aid FROM BookAuthors) AND a.aid NOT IN (SELECT aid FROM BookAuthors WHERE bid IN (SELECT bid FROM Loans WHERE returned=0))`

   **Pattern H — Correlated subquery:**
   Question: "Departments where every patient seen is older than 60."
   `SELECT d.name FROM Departments d WHERE d.did IN (SELECT doc.did FROM Doctors doc JOIN Appointments a ON doc.doc_id=a.doc_id) AND NOT EXISTS (SELECT 1 FROM Patients p WHERE p.age<=60 AND p.pid IN (SELECT pid FROM Appointments WHERE doc_id IN (SELECT doc_id FROM Doctors WHERE did=d.did)))`

4. **DISTINCT rule:** Apply `DISTINCT` whenever the question uses "distinct", "unique", or implies a set result (e.g. "names of students who ...") and a JOIN could produce duplicate rows. Bag equality counts duplicates — always deduplicate unless aggregation already does it.

5. **Draft** a single read-only SQLite SQL statement (one line, no trailing semicolon needed) using only the tables and column names present in `db_schema`. Only `SELECT` / `WITH ... SELECT` style read queries — no DDL/DML, no multiple statements.

6. **Write the result file.** Use the `terminal` tool (NOT a process/background tool) and run, with an **absolute path** (`<skill_dir>` is given to you by Hermes via `[Skill directory: ...]`):
   ```
   python3 <skill_dir>/scripts/run.py \
     --task_id "<task_id>" \
     --sql "<your single-line SQL>" \
     --rationale "<one sentence>" \
     --confidence <0.0-1.0>
   ```
   This writes the result to the file given by the `AIASE_RESULT_PATH` environment variable (or `./aiase_result.json` if unset). **You do not need to print or repeat the JSON in the chat message** — the grader reads the result file, not your reply.

## Pitfalls

- **Missing DISTINCT on JOIN:** Without DISTINCT, a student enrolled in 3 courses appears 3 times. Bag equality will fail. When the question asks for a set of entities (not counts), add DISTINCT.
- **Wrong column/table names:** Copy column names exactly from DDL — case matters for string comparisons but not for identifiers.
- **Multiple statements:** Only one SQL statement. No semicolon-separated multiples.
- **DDL/DML forbidden:** Only SELECT-style read queries. No CREATE, DROP, INSERT, UPDATE, DELETE.
- **CTE / window functions forbidden:** SQLite dialect, no `WITH ... OVER()` window functions.
- **task_id mismatch:** Pass `task_id` to `run.py` exactly as received — do not modify it.
- **LEFT JOIN vs INNER JOIN:** Use LEFT JOIN when the question says "include ... with zero" or "even if no matching rows".
- **Correlated subqueries:** When the outer query's condition depends on the inner, reference the outer alias inside the subquery (e.g., `WHERE did = d.did`).
- **Do not use process/background tools** to run `scripts/run.py` — use the synchronous `terminal` tool so the write completes before your turn ends.

## Verification

The result file must exist, be a valid JSON object, have `task_id` matching the input, `sql` as a non-empty string, and `confidence` in `[0, 1]`. The grader executes your SQL and the gold SQL on the hidden DB and compares results with bag equality (order-insensitive, duplicates counted).
