# 期末報告 — AIASE 2026 Final Project

> 學生：韓倫語 / GitHub: `1eadbloom`

---

## 1. 設計決策

### 1.1 Basic — Text2SQL Skill

**SKILL.md 設計理念：** 純 LLM 自由生成 SQL 的最大失敗模式是「語法正確但語意錯誤」——最常見的是 JOIN 放大導致重複列、欄位名拼錯、或忽略 DISTINCT。因此 SKILL.md 的核心設計是把常見 SQL pattern（JOIN+DISTINCT、LEFT JOIN+COUNT、UNION、NOT EXISTS、correlated subquery 等）作為 few-shot exemplar 直接嵌入 Procedure，強迫 LLM 對照 question 語意選擇 pattern，而非從頭自由生成。

**harness 設計：** `scripts/validate_sql.py` 用 SQLite in-memory EXPLAIN 做語法與欄位解析，確認 SQL 合法後再由 `scripts/run.py` 強制輸出 fenced JSON。LLM 的機率性被這兩層確定性 harness 框住——即使 LLM 輸出錯誤 SQL，EXPLAIN 會攔截並觸發 retry。

**DISTINCT rule：** bag equality 計入重複列，因此 SKILL.md 明確規定：question 中有「names of X who/that...」時必加 DISTINCT，防止 JOIN 放大造成 bag mismatch。

### 1.2 Pairwise — Code Author + Bug Hunter（雙角色）

**Code Author 設計：** SKILL.md 嵌入 5 種實作 pattern（interval merge、binary search、CSV parsing、DP、k-th element）作為 exemplar，並強制規定 `sample_inputs` 必須包含 `[]`（空輸入）、single element、boundary value 三類 edge case，再傳給 `scripts/selftest.py` 驗證。原因是空輸入 guard 是最常見的 bug，若 sample_inputs 沒有涵蓋則 selftest 無法偵測。

**Bug Hunter 設計：** 最重要的設計決策是「task-specific edge input generation」——依 task_description 的函式類型（list/search/string/grid/k-th）自動選對應的 probe 組合傳給 `scripts/analyze.py`。泛用 battery（`[]`、`None`、`0`）對 binary search 的 off-by-one 完全無效；而 `([5], 5)`、`([5], 9)`、`([1,2,3], 1)` 等型別專屬 probe 才能觸發靜默邏輯錯誤。

另一關鍵是 **severity 校準**：SKILL.md 明確規定 clean code FP rate 佔 25% 分數，因此「不確定是否為 bug 時預設不報」，避免 over-report。

### 1.3 Open Track — JSON Schema Validator（`open-jsonvalidate-1eadbloom`）

**選題理由：** 選 JSON Schema Validation 的核心原因是「ground truth 完全確定」——給定相同 schema + instance，答案唯一，不需要人工判斷，評分器可直接程式化比對。這是最接近純 deterministic shell 的設計：`scripts/validate.py` 是完整的 draft-07 subset validator（純 stdlib），LLM 的角色被最小化為「解析輸入 → 呼叫 validate.py → 呼叫 run.py → 輸出結果」。

**不可 gameable 的原因：** staff perturbation 會改變 schema 結構（不同欄位名稱、不同數值邊界、不同 required 列表），必須跑正確演算法才能通過，無法 hardcode 或猜測。`valid=true` 要求 `errors=[]` 且 `error_count=0`，`valid=false` 要求精確的 `path` 和 `rule`，兩者無法同時被「永遠回答 clean」或「永遠回答 buggy」的策略騙過。

---

## 2. 實際遭遇之失敗與分析

### 失敗 1 — LiteLLM Proxy 拒絕 max_tokens=65536（環境配置）

- **觸發場景：** 煙霧測試 `/hello-aiase {"name":"world"}` 時，Hermes 預設送出 `max_tokens=65536`，課程 LiteLLM proxy 後端（vLLM，context window 32768）拒絕請求。
- **log 片段：**
  ```
  BadRequestError: (parameter=max_tokens, value=65536) ... context_window=32768
  Context length exceeded (3,721 tokens). Cannot compress further.
  ```
- **成因分析：** Hermes 的 custom provider 設定不讀取 `config.yaml` 裡的 `max_tokens` 欄位，hardcode 送出 65536。proxy 沒有自動截斷而是直接拒絕。
- **修正方式：** 在本機架設 Flask proxy（`proxy_fix.py`），攔截所有 `/chat/completions` 請求，把 `max_tokens > 8192` 截斷為 8192，再轉發給課程 proxy。同時移除 `stream_options`（只在 `stream=True` 合法）。
- **MAST 分類：** (3) 驗證與品質 — 環境配置與 provider 相容性問題，導致所有 skill 呼叫失敗。

### 失敗 2 — Hermes 輸出寫到 TTY 而非 stdout/stderr，run_dev.py 捕捉為空字串

- **觸發場景：** `run_dev.py` 用 `subprocess.run(capture_output=True)` 呼叫 Hermes，所有 task 的 `stdout` 欄位均為空字串，導致全部 "no valid fenced JSON in stdout"。
- **log 片段：**
  ```python
  stdout repr: ''   # subprocess.run 捕捉到的內容
  # 但終端上可以看到 Hermes 輸出了正確的 SQL
  SELECT Students.name FROM Students JOIN ...
  ```
- **成因分析：** Hermes 的 TUI 渲染器直接寫到 `/dev/tty`（terminal device），繞過了 stdout/stderr pipe。`capture_output=True` 只捕捉 pipe，因此捕捉結果永遠是空的。
- **修正方式：** 改用 `script -q -e -c "hermes ..." outfile` 把整個 TTY session 錄製到檔案，再讀取並清除 ANSI escape codes。同時加入 `_extract_sql_fallback()` 從純文字輸出用 regex 萃取 SQL，作為沒有 fenced JSON 時的 fallback。
- **MAST 分類：** (3) 驗證與品質 — 驗證層（run_dev.py 的 stdout 捕捉）不適配 agent 的實際輸出通道。

### 失敗 3 — LLM 不主動呼叫 terminal tool，直接輸出 SQL 文字

- **觸發場景：** text2sql skill 呼叫時，LLM 完全忽略 SKILL.md 裡「呼叫 `scripts/run.py`」的指示，直接以純文字輸出 SQL，`0 tool calls`，導致 run_dev.py 找不到 fenced JSON。
- **log 片段：**
  ```
  Messages: 2 (1 user, 0 tool calls)
  SELECT T1.name FROM Students AS T1 JOIN Enrollments AS T2 ...
  ```
- **成因分析：** `aiase_model`（nvidia/Gemma-4-31B）的 tool-calling 能力較弱，看到簡單可直接回答的 task 時不會主動呼叫工具。SKILL.md 的 Procedure 雖然有「Step 7: run scripts/run.py」，但沒有足夠強的強制性指示。
- **修正方式：** 在 SKILL.md frontmatter 後立即加入 `⚠️ CRITICAL RULES` 和 `⚠️ OUTPUT FORMAT` 強制指示。對 run_dev.py 同步加入 `_extract_sql_fallback()` 作為雙重保障——即使 LLM 沒呼叫 run.py，也能從純文字輸出萃取 SQL 並包裝成符合契約的 JSON。最終 dev set pass rate 從 0% 提升到 57%（12/21）。
- **MAST 分類：** (1) 規格與角色 — LLM 沒有遵循 SKILL.md 的角色指示（tool-calling agent）。

---

## 3. 改進方向

**Text2SQL：** 加入 schema grounding step——在 Procedure 的 Draft 步驟前，先用 Python 從 DDL parse 出所有表名和欄位名，以 `{table: [col1, col2]}` 格式注入 prompt，減少 LLM 憑記憶猜欄位名的機率（目前 "no such column" 是主要失敗原因之一）。

**Bug Hunter：** 對 `analyze.py` 加入 expected-value 比對——若 task_description 包含具體的輸入輸出範例，把這些當作 oracle probe 而非只測 crash。這樣可偵測靜默的 logic error（例如 binary search 靜默回傳 -1 而不 crash）。

**Open Track：** 增加 `anyOf` 的 nested error path 報告，目前只報「anyOf 整體失敗」而非指出哪個 sub-schema 最接近通過，改進後 error_count 計算更精確。

**通用環境：** run_dev.py 的 `script` 捕捉方式會污染 TTY 狀態，每次跑完需要手動 `reset`。改用 `pty` 模組或 `pexpect` 的 `logfile` 模式可避免 TTY 損壞，但需要在 WSL2 環境下額外測試相容性。

**LiteLLM 整合：** 直接在課程 LiteLLM proxy 的 key 層設定 `max_tokens` 限制，不需要本機 Flask proxy 作為中介層，可減少一個故障點。

---

## 4. 分工（單人組，不適用）

---

## 5. 引用說明

- Starter repo（課程提供）：`scripts/run.py`、`scripts/selftest.py`、`scripts/analyze.py`、`scripts/validate_sql.py` 的基礎骨架，以及 `run_dev.py`、`verify_repo.py`。本作業在其上進行以下擴充：
  - `text2sql/SKILL.md`：新增 8 種 SQL pattern few-shot exemplar、DISTINCT rule、CRITICAL RULES 強制輸出指示
  - `code-author/SKILL.md`：新增 5 種實作 pattern、明確的 sample_inputs edge case 規定、MANDATORY FINAL STEP 指示
  - `bug-hunter/SKILL.md`：新增 task-specific edge_inputs 分類、code reading checklist、severity 校準規則、MANDATORY FINAL STEP 指示
  - `run_dev.py`：新增 `_strip_ansi()`、`_extract_sql_fallback()`、`script` TTY 捕捉、`extract_last_json_block` 的 task_id 傳遞、`--toolsets skills,terminal --yolo --cli` 參數

- `skills/open-jsonvalidate-1eadbloom/scripts/validate.py`：自行撰寫，參考 [JSON Schema draft-07 specification](https://json-schema.org/draft-07/json-schema-validation.html) 實作，非借用任何現有 library 或 repo。支援 type/required/properties/additionalProperties/minimum/maximum/minLength/maxLength/items/enum/const/pattern/allOf/anyOf/oneOf。

- AI coding assistant（Claude）：用於草稿生成、debug 協助、指令建議。所有最終提交內容由作者審閱、測試並驗證。
