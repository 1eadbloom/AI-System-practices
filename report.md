# 期末報告 — AIASE 2026 Final Project

> 學生：徐祥智 / GitHub: `1eadbloom`

\---

## 1\. 設計決策

### 1.1 Basic — Text2SQL Skill

**SKILL.md 設計理念：** 純 LLM 自由生成 SQL 的最大失敗模式是「語法正確但語意錯誤」——最常見的是 JOIN 放大導致重複列、欄位名拼錯、或忽略 DISTINCT。因此 SKILL.md 的核心設計是把常見 SQL pattern（JOIN+DISTINCT、LEFT JOIN+COUNT、UNION、NOT EXISTS、correlated subquery 等）作為 few-shot exemplar 直接嵌入 Procedure，強迫 LLM 對照 question 語意選擇 pattern，而非從頭自由生成。

**Schema grounding（v2.1 新增）：** Procedure 的 Step 0 強制執行 `scripts/extract\\\_schema.py`——一支純 Python、regex-based 的 DDL parser，把 `db\\\_schema` 解析成 `{table: \\\[columns]}` 的權威對照表。LLM 在後續所有步驟都必須以這份對照表為唯一依據，不能憑記憶猜欄位名。這是把「記住欄位名」這個最容易出錯的步驟，從機率性的 LLM 移到確定性的 Python——`deterministic shell wrapping probabilistic core` 的延伸應用。已對 dev set 全部 21 個 DDL 跑過驗證，21/21 正確解析（見第 2 節）。

**故障排除表（v2.1 新增）：** `validate\\\_sql.py` 回傳 `ok=false` 時，SKILL.md 提供一張「錯誤訊息 → 成因 → 修法」對照表（例如 `no such column: T1.name` → 回查 step 0 的對照表找出正確的 table/column），取代原本「retry 但不知道怎麼改」的盲目重試。

**harness 設計：** `scripts/validate\\\_sql.py` 用 SQLite in-memory EXPLAIN 做語法與欄位解析，確認 SQL 合法後再由 `scripts/run.py` 寫入結果檔。LLM 的機率性被三層確定性 harness（extract\_schema → validate\_sql → run）框住。

**DISTINCT rule：** bag equality 計入重複列，因此 SKILL.md 明確規定：question 中有「names of X who/that...」時必加 DISTINCT，防止 JOIN 放大造成 bag mismatch。

### 1.2 Pairwise — Code Author + Bug Hunter（雙角色）

**Code Author 設計：** SKILL.md 嵌入 5 種實作 pattern（interval merge、binary search、CSV parsing、DP、k-th element）作為 exemplar，並強制規定 `sample\\\_inputs` 必須包含 `\\\[]`（空輸入）、single element、boundary value 三類 edge case，再傳給 `scripts/selftest.py` 驗證。

**Bug Hunter 設計：** 最重要的設計決策是「task-specific edge input generation」——依 task\_description 的函式類型（list/search/string/grid/k-th）自動選對應的 probe 組合傳給 `scripts/analyze.py`。

**Oracle-based 探測（v2.1 新增）：** 原版 `analyze.py` 只能判斷「crash / timeout / ok」三種結果，對「跑得通但答案錯」的靜默邏輯錯誤（例如 binary search 的 `while lo < hi` 邊界寫錯，靜默回傳 -1）完全無法偵測——`outcome="ok"` 會誤導 LLM 認為函式正確。v2.1 在 `analyze.py` 為每個 probe 加入可選的 `expected` 欄位：若提供，分析器會比對 `actual == expected`，不符則回報 `outcome="mismatch"`，並把 AST 解析出的 `return\\\_lines` 一併標記為 suspicious lines（因為 mismatch 沒有 traceback 可定位）。SKILL.md 明確要求「凡是 spec 能推導出正確答案的 probe，一律加上 expected」。已用一個刻意寫錯邊界的 binary\_search 驗證：未加 expected 時三個 probe 全部 `ok`（看起來乾淨）；加上 expected 後，`first` probe 正確標記為 `mismatch`（expected 0, got -1），`suspicious\\\_lines` 也正確指向兩個 return 語句所在行（6, 11）。

另一關鍵是 **severity 校準**：SKILL.md 明確規定 clean code FP rate 佔 25% 分數，因此「不確定是否為 bug 時預設不報」，避免 over-report。

### 1.3 Open Track — JSON Schema Validator（`open-jsonvalidate-1eadbloom`）

**選題理由：** 選 JSON Schema Validation 的核心原因是「ground truth 完全確定」——給定相同 schema + instance，答案唯一，不需要人工判斷。`scripts/validate.py` 是完整的 draft-07 subset validator（純 stdlib），LLM 的角色被最小化為「解析輸入 → 呼叫 validate.py → 呼叫 run.py 寫結果檔」。

**`not` 關鍵字（v2.1 新增）：** 原版漏了 draft-07 的 `not` 邏輯組合子——這是 staff perturbation 常見的測試點（"instance must NOT match this sub-schema"）。已補上，並在 `OPEN\\\_TRACK.md` 新增 Scenario 6（一組正反例：`{"status":"banned"}` 應 `valid=false, rule="not"`；`{"status":"active"}` 應 `valid=true`）。`not` 的方向容易寫反（子 schema「通過」才是違反 `not`），SKILL.md 的 Pitfalls 明確提醒此處的常見錐誤，並強調這個方向判斷完全交給確定性程式碼，LLM 不需自行推導。

**不可 gameable 的原因：** staff perturbation 會改變 schema 結構（不同欄位名稱、不同數值邊界、不同 required 列表、不同 `not` 黑名單），必須跑正確演算法才能通過，無法 hardcode 或猜測。

\---

## 2\. 實際遭遇之失敗與分析

### 失敗 1 — LiteLLM Proxy 拒絕 max\_tokens=65536（環境配置）

* **觸發場景：** 煙霧測試 `/hello-aiase {"name":"world"}` 時，Hermes 預設送出 `max\\\_tokens=65536`，課程 LiteLLM proxy 後端（vLLM，context window 32768）拒絕請求。
* **log 片段：**

```
  BadRequestError: (parameter=max\\\_tokens, value=65536) ... context\\\_window=32768
  Context length exceeded (3,721 tokens). Cannot compress further.
  ```

* **成因分析：** Hermes 的 custom provider 設定不讀取 `config.yaml`／`hermes model` 互動設定裡的 `max\\\_tokens` 或 `context\\\_length` 欄位（即使手動設定 `context\\\_length: 64000` 仍重現同樣錯誤），hardcode 送出 65536。
* **修正方式：** 在本機架設 Flask proxy（`proxy\\\_fix.py`），攔截所有 `/chat/completions` 請求，把 `max\\\_tokens > 8192` 截斷為 8192，再轉發給課程 proxy；同時移除 `stream\\\_options`（只在 `stream=True` 合法）。
* **MAST 分類：** (3) 驗證與品質 — 環境配置與 provider 相容性問題，導致所有 skill 呼叫失敗。
* **與評分的關係：** 此 workaround 完全是本機檔案（`\\\~/.hermes/config.yaml`、`\\\~/proxy\\\_fix.py`），不在 repo 內、不影響 push 的內容。規格更新第 3 點說明評分用「較強的模型」，其 backend 的 context window 通常遠大於 32768，理論上不會卡在這個限制。

### 失敗 2 — 舊版「對話輸出 JSON」契約不穩定，已由 file-based 契約取代

* **觸發場景（舊契約）：** text2sql skill 呼叫時，LLM 完全忽略 SKILL.md 裡「在對話最後輸出 fenced JSON」的指示，直接以純文字輸出 SQL（`0 tool calls`），或是把 `run.py` 的輸出顯示為 Hermes 專屬的 `<channel|>json` 格式而非標準 `json `，導致 `run\\\_dev.py` 從 stdout 擷取 JSON 全部失敗。
* **log 片段（舊契約下的兩種失敗模式）：**

```
  Messages: 2 (1 user, 0 tool calls)
  SELECT T1.name FROM Students AS T1 JOIN Enrollments AS T2 ...   # 純文字，無 JSON

  <|channel>thought
  <channel|>json
  {"task\\\_id": "task\\\_nl2sql\\\_EXAMPLE", "sql": "SELECT ...", ...}    # 非標準 fenced block
  ```

* **成因分析：** (a) `aiase\\\_model`（nvidia/Gemma-4-31B）的 tool-calling 能力較弱，簡單任務時不主動呼叫工具；(b) 即使呼叫了 `run.py`，Hermes 的 TUI 渲染層會把 fenced code block 轉換成自己的 channel 格式，破壞了「對話輸出即契約」這個假設。
* **修正方式：** 課程第二次規則更新將輸出契約從「對話輸出 fenced JSON」改為「`scripts/run.py` 寫入 `AIASE\\\_RESULT\\\_PATH` 指定的結果檔，評分器直接讀檔」。本專案已完整改版：四個 skill 的 `scripts/run.py` 全部改為 `argparse` 接收參數、原子寫入（`os.replace` tmp file）、自帶 `resolve\\\_result\\\_path()`（不 import `aiase\\\_contract`，因為安裝後找不到 repo 根模組）；四個 `SKILL.md` 的 Procedure 最後一步改為「呼叫 `<skill\\\_dir>/scripts/run.py` 寫結果檔，不需在對話輸出 JSON」。改版後，無論 LLM 把對話顯示成 `<channel|>json`、純文字 SQL 還是其他格式，只要 `run.py` 被正確呼叫並寫檔，評分就不受影響。
* **驗證結果：** 用 `python3 run\\\_dev.py --skill text2sql-1eadbloom --track basic --task task\\\_nl2sql\\\_001`（搭配 `aiase\\\_contract.py` 做 bag equality 比對）單題測試 PASS；`task\\\_nl2sql\\\_004` 同樣 PASS。批次跑 21 題時一度因本機 WSL2 DNS 設定中斷（見失敗 1）；修復 DNS 後重跑，21/21 全數 PASS（100%），log 見 dev\_run\_results/filebased\_basic\_run.log。
* **MAST 分類：** (3) 驗證與品質 — 驗證層（「對話輸出即契約」）不適配 agent 的實際輸出通道；改為「寫檔即契約」後問題消失。

### 失敗 3 — Bug Hunter 對 binary\_search 的靜默邏輯錯誤完全無感知

* **觸發場景：** 給定一個 `while lo < hi` / `hi = mid - 1`（邊界不一致）的 binary\_search，原版 `analyze.py` 對所有 probe 只回報 `outcome: "ok"`（因為函式不會 crash，只是回傳錯誤的 -1），導致 Bug Hunter 看到「probe 全過」而誤判 `verdict=clean`。
* **log 片段：**

```
  // 原版 analyze.py（無 expected）
  probes: \\\[{"label":"first","outcome":"ok","error":""}, ...]
  → Bug Hunter 傾向輸出: {"verdict":"clean","bugs":\\\[]}   ← 漏報

  // v2.1 加入 expected 後
  probes: \\\[{"label":"first","outcome":"mismatch","error":"expected 0, got -1","actual":-1,"expected":0}, ...]
  suspicious\\\_lines: \\\[6, 11]
  summary: "3 probes; 0 crash, 0 timeout, 1 mismatch (wrong answer, no crash), 2 ok; ..."
  ```

* **成因分析：** "crash vs ok vs timeout" 的探測模型隱含假設「bug 必然以例外形式出現」，但邊界條件錯誤（off-by-one）的典型表現正是「不 crash、答案錯」——這類 bug 對 probe-only 的 harness 完全不可見。
* **修正方式：** `analyze.py` 新增 `expected` 欄位與 `mismatch` outcome；SKILL.md 第 3 步明確要求「凡是 spec 能推導出正確答案的 probe，一律加上 expected」，第 4 步要求把 `mismatch` 與 crash 同等看待為 bug 證據。
* **MAST 分類：** (3) 驗證與品質 — 確定性 harness 的探測模型本身有覆蓋率盲點，已透過 oracle-based 比對補上。

\---

## 3\. 改進方向

**Text2SQL：** 目前 `extract\\\_schema.py` 只解析 table/column 名稱，未解析外鍵關係。若再做一次，會額外解析 `FOREIGN KEY ... REFERENCES` 子句，直接輸出 JOIN graph，讓 LLM 不需自己從命名慣例猜測 JOIN key。

**Bug Hunter：** `expected` 目前由 LLM 手動為每個 probe 填寫，仰賴 LLM 對 spec 的理解正確。可以再加一層：若 `task\\\_description` 本身含有形式化的 input/output 範例（如 `f(\\\[1,2,3], 1) == 0`），用 regex 自動抽取成 `edge\\\_inputs` 的 `expected`，減少 LLM 推導錯誤的風險。

**Open Track：** `anyOf`/`oneOf` 目前只回報「整體失敗」，未指出哪個 sub-schema 最接近通過。可加入「per-branch error 數量最少的分支」作為輔助訊息，幫助使用者更快定位問題（雖然不影響 `valid`/`error\\\_count` 的判定）。

**通用環境：** WSL2 的 `/etc/resolv.conf` 在 `wsl --shutdown` 後會被 WSL2 自動產生機制覆寫，即使 `/etc/wsl.conf` 設了 `generateResolvConf = false` 似乎仍偶發失效。下次會改用 `resolv.conf` 設為唯讀（`chattr +i`）或在 `\\\~/.bashrc` 加入自動修復腳本，避免每次重開 WSL2 都要手動重設 DNS。

\---

## 4\. 分工（單人組，不適用）

\---

## 5\. 引用說明

* Starter repo（課程提供）：`scripts/run.py`、`scripts/selftest.py`、`scripts/analyze.py`、`scripts/validate\\\_sql.py` 的基礎骨架，以及 `run\\\_dev.py`、`verify\\\_repo.py`、`aiase\\\_contract.py`（file-based 更新版）。本作業在其上進行以下擴充：

  * `text2sql/SKILL.md` + `scripts/extract\\\_schema.py`（全新）：新增 8 種 SQL pattern few-shot exemplar、DISTINCT rule、schema grounding 強制步驟、錯誤對照表
  * `code-author/SKILL.md`：新增 5 種實作 pattern、明確的 sample\_inputs edge case 規定
  * `bug-hunter/SKILL.md` + `scripts/analyze.py`（擴充）：新增 task-specific edge\_inputs 分類、code reading checklist、severity 校準規則、oracle-based mismatch 偵測
  * `open-jsonvalidate/scripts/validate.py`（擴充）：新增 `not` 邏輯組合子；`OPEN\\\_TRACK.md` 新增 Scenario 6 正反例
  * `run\\\_dev.py`：依課程 file-based 更新版調整 `load\\\_tasks()` 以對應本 repo 的 `dev\\\_set/basic/task\\\_nl2sql\\\_\\\*.json` 與 `dev\\\_set/pairwise/reference\\\_tasks/task\\\_\\\*.json` 結構，並加入 120 秒可調 timeout
* `skills/open-jsonvalidate-1eadbloom/scripts/validate.py`：自行撰寫，參考 [JSON Schema draft-07 specification](https://json-schema.org/draft-07/json-schema-validation.html) 實作，非借用任何現有 library 或 repo。支援 type/required/properties/additionalProperties/minimum/maximum/minLength/maxLength/items/enum/const/pattern/allOf/anyOf/oneOf/not。
* `skills/text2sql-1eadbloom/scripts/extract\\\_schema.py`：自行撰寫，純 stdlib（`re` + `json`），對 21 個 dev set DDL 全數驗證通過（21/21）。
* AI coding assistant（Claude）：用於草稿生成、debug 協助、指令建議。所有最終提交內容由作者審閱、測試並驗證。

