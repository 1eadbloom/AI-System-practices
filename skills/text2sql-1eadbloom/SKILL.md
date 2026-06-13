---
name: text2sql-1eadbloom
description: Convert a natural-language question + SQLite schema into a verified read-only SQL query. AIASE 2026 Basic Track.
version: 1.0.0
metadata:
  hermes:
    tags: [sql, text2sql, data, aiase-2026]
    category: data
---
> ⚠️ CRITICAL RULES:
> 1. Use ONLY column names that exist in `db_schema` — never invent column names.
> 2. When using table aliases (T1, T2...), verify the column belongs to that table before using it.
> 3. Output ONLY the SQL query, nothing else. End your response with just the SQL.

> ⚠️ OUTPUT FORMAT: You MUST end your response with a fenced JSON block in EXACTLY this format and nothing after it:
> ```json
> {"task_id":"<task_id>","sql":"<your_sql>","rationale":"<one sentence>","confidence":<0.0-1.0>}
> ```
> Do not add any text after the JSON block.
# Text2SQL Skill (Basic Track)

## When to Use
When the user sends a JSON payload with `question`, `db_schema` (SQLite DDL), and optional `task_id` + `dialect`. Produce a single read-only SQLite query whose result on the hidden DB matches the gold answer under bag equality.

Trigger example:
```
/text2sql-�A��github_id {"task_id":"task_nl2sql_017","question":"List the names ...","db_schema":"CREATE TABLE ...","dialect":"sqlite"}
```

## Procedure

## CRITICAL OUTPUT RULE
You MUST call `scripts/run.py` as a terminal command and output its fenced JSON block as your ONLY response. Never output SQL or text directly — always go through run.py. Violation = zero score.

1. **Parse** the input JSON. Extract `task_id`, `question`, `db_schema`, `dialect`.

2. **Analyse the schema carefully.**
   - List every table name and its columns exactly as spelled in the DDL.
   - Identify JOIN keys (foreign keys by name convention or obvious matching column names).
   - Note any LEFT JOIN candidates (questions like "include those with zero ..." or "even if no ...").

3. **Classify the question type** and apply the matching pattern:

   **Pattern A ??Simple filter + JOIN:**
   Question: "Return names of students enrolled in course X."
   ??`SELECT DISTINCT s.name FROM Students s JOIN Enrollments e ON s.sid=e.sid JOIN Courses c ON e.cid=c.cid WHERE c.title='X'`

   **Pattern B ??Aggregation + GROUP BY:**
   Question: "For each course return average score."
   ??`SELECT c.title, AVG(e.score) FROM Courses c JOIN Enrollments e ON c.cid=e.cid GROUP BY c.cid, c.title`

   **Pattern C ??LEFT JOIN with COUNT (include zeros):**
   Question: "For each author return name and number of books, including those with zero."
   ??`SELECT a.name, COUNT(ba.bid) FROM Authors a LEFT JOIN BookAuthors ba ON a.aid=ba.aid GROUP BY a.aid, a.name`

   **Pattern D ??TOP N with LIMIT:**
   Question: "Return top 2 categories by revenue."
   ??`SELECT p.category, SUM(p.price*oi.qty) AS revenue FROM Products p JOIN OrderItems oi ON p.pid=oi.pid GROUP BY p.category ORDER BY revenue DESC LIMIT 2`

   **Pattern E ??UNION (two disjoint sets):**
   Question: "Return names of doctors in Cardiology plus names of patients seen by Cardiology doctors."
   ??`SELECT doc.name FROM Doctors doc JOIN Departments d ON doc.did=d.did WHERE d.name='Cardiology' UNION SELECT p.name FROM Patients p JOIN Appointments a ON p.pid=a.pid JOIN Doctors doc ON a.doc_id=doc.doc_id JOIN Departments d ON doc.did=d.did WHERE d.name='Cardiology'`

   **Pattern F ??Nested subquery (tie-breaking / max of aggregates):**
   Question: "Return team that played most games as home team; if tie return all."
   ??`SELECT t.name FROM Teams t WHERE t.tid IN (SELECT home_tid FROM Games GROUP BY home_tid HAVING COUNT(*)=(SELECT MAX(c) FROM (SELECT COUNT(*) AS c FROM Games GROUP BY home_tid)))`

   **Pattern G ??NOT EXISTS / NOT IN (exclusion):**
   Question: "Authors who wrote at least one book and none of whose books are on loan."
   ??`SELECT a.name FROM Authors a WHERE a.aid IN (SELECT aid FROM BookAuthors) AND a.aid NOT IN (SELECT aid FROM BookAuthors WHERE bid IN (SELECT bid FROM Loans WHERE returned=0))`

   **Pattern H ??Correlated subquery:**
   Question: "Departments where every patient seen is older than 60."
   ??`SELECT d.name FROM Departments d WHERE d.did IN (SELECT doc.did FROM Doctors doc JOIN Appointments a ON doc.doc_id=a.doc_id) AND NOT EXISTS (SELECT 1 FROM Patients p WHERE p.age<=60 AND p.pid IN (SELECT pid FROM Appointments WHERE doc_id IN (SELECT doc_id FROM Doctors WHERE did=d.did)))`

4. **DISTINCT rule:** Apply `DISTINCT` whenever the question uses "distinct", "unique", or implies a set result (e.g. "names of students who ...") and a JOIN could produce duplicate rows. Bag equality counts duplicates ??always deduplicate unless aggregation already does it.

5. **Draft** a single SQLite read-only SQL statement using only the tables and column names present in `db_schema`.

6. **Validate** by running:
   ```
   python scripts/validate_sql.py '{"schema_ddl": "<db_schema>", "sql": "<draft_sql>"}'
   ```
   Read the `ok` field from the output JSON block.
   - If `ok=false`: read the `error` field, fix the specific issue (wrong column name, wrong table alias, missing table reference), and retry. Maximum **3 retries**. After 3 failures, use the best draft and set `confidence=0.2`.

7. **Emit** the final result by running these two commands:
   ```
   python3 scripts/run.py '{"task_id":"<task_id>","sql":"<validated_sql>","rationale":"<one sentence>","confidence":<0.0-1.0>}' | tee /tmp/hermes_skill_result.txt
   ```
   Then output the fenced JSON block as your final response.

## Pitfalls

- **Missing DISTINCT on JOIN:** Without DISTINCT, a student enrolled in 3 courses appears 3 times. Bag equality will fail. When the question asks for a set of entities (not counts), add DISTINCT.
- **Wrong column/table names:** Copy column names exactly from DDL ??case matters in SQLite for comparison but not for identifiers. Validate with `validate_sql.py` to catch these before output.
- **Multiple statements:** Only one SQL statement. No semicolon-separated multiples.
- **DDL/DML forbidden:** Only SELECT. No CREATE, DROP, INSERT, UPDATE, DELETE.
- **CTE / window functions forbidden:** SQLite dialect, spec §2.2. No `WITH`, no `OVER()`.
- **task_id mismatch:** Copy `task_id` from input exactly ??do not modify it.
- **LEFT JOIN vs INNER JOIN:** Use LEFT JOIN when the question says "include ... with zero" or "even if no matching rows".
- **Correlated subqueries:** When the outer query's condition depends on the inner, reference the outer alias inside the subquery (e.g., `WHERE did = d.did`).

## Verification

`scripts/validate_sql.py` checks: single statement, no DDL/DML, schema compiles in-memory, EXPLAIN succeeds (column resolution). It cannot verify correctness against data ??that is the grader's job.

`scripts/run.py` enforces the output contract shape. The last fenced JSON block in stdout is the grader's input.


