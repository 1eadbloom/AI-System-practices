## 1. Skill 簡介

給定一個 JSON Schema 和一個 JSON 實例，判斷該實例是否符合 Schema，並輸出結構化的驗證報告（含每個錯誤的 JSON Pointer 路徑、失敗的關鍵字、以及人可讀的描述）。

## 2. Skill 名稱與目錄

`skills/open-jsonvalidate-1eadbloom/`

## 3. 呼叫方式

評分環境以下列方式呼叫：

**Slash command:**
```
/open-jsonvalidate-1eadbloom
```

**輸入 JSON 範例：**

```json
{
  "task_id": "open_001",
  "schema": {
    "type": "object",
    "required": ["name", "age"],
    "properties": {
      "name": {"type": "string"},
      "age": {"type": "integer", "minimum": 0}
    }
  },
  "instance": {"name": "Alice", "age": -1}
}
```

**結果檔（file-based 輸出契約，寫入 `AIASE_RESULT_PATH`）範例：**

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

完整欄位說明：
- `task_id`: 與輸入相同的字串
- `valid`: 布林值，true 代表完全符合 schema
- `errors`: 錯誤陣列；valid=true 時必須為空陣列
- `error_count`: 必須等於 `errors` 陣列的長度
- `confidence`: 永遠是 1.0（完全確定性結果）

## 4. 自定 Verifiable Scenario

本 skill 的核心是 **純確定性驗證**：給定相同的 schema + instance，輸出必然相同，不依賴 LLM 的機率輸出。評分器可直接程式化比對輸出 JSON 與 ground truth。

**Scenarios（6 個）：**

- **Scenario 1（valid = true）：** 合法物件，符合 required + type + minimum 所有限制。
  ```json
  {"task_id":"open_s1","schema":{"type":"object","required":["id","score"],"properties":{"id":{"type":"string"},"score":{"type":"number","minimum":0,"maximum":100}}},"instance":{"id":"abc","score":75.5}}
  ```
  Ground truth: `{"valid":true,"errors":[],"error_count":0}`

- **Scenario 2（valid = false，多重錯誤）：** 缺少 required 欄位 + 數值超出範圍。
  ```json
  {"task_id":"open_s2","schema":{"type":"object","required":["id","score"],"properties":{"id":{"type":"string"},"score":{"type":"number","minimum":0,"maximum":100}}},"instance":{"score":150}}
  ```
  Ground truth: `{"valid":false,"error_count":2}`（缺少 `id`、score > 100）

- **Scenario 3（array items validation）：** 陣列中有型別錯誤的元素。
  ```json
  {"task_id":"open_s3","schema":{"type":"array","minItems":1,"items":{"type":"integer"}},"instance":[1,"two",3]}
  ```
  Ground truth: `{"valid":false,"errors":[{"path":"/1","rule":"type"}],"error_count":1}`

- **Scenario 4（additionalProperties false）：** 不允許額外欄位。
  ```json
  {"task_id":"open_s4","schema":{"type":"object","properties":{"x":{"type":"integer"}},"additionalProperties":false},"instance":{"x":1,"y":2}}
  ```
  Ground truth: `{"valid":false,"error_count":1}`

- **Scenario 5（enum）：** 值不在枚舉清單中。
  ```json
  {"task_id":"open_s5","schema":{"type":"string","enum":["red","green","blue"]},"instance":"yellow"}
  ```
  Ground truth: `{"valid":false,"error_count":1}`

- **Scenario 6（not，否定條件）：** 欄位值不得屬於某個黑名單枚舉；測試 `not` 關鍵字。
  ```json
  {"task_id":"open_s6","schema":{"type":"object","properties":{"status":{"not":{"enum":["banned","deleted"]}}}},"instance":{"status":"banned"}}
  ```
  Ground truth: `{"valid":false,"errors":[{"path":"/status","rule":"not"}],"error_count":1}`

  對照組（應為 valid）：
  ```json
  {"task_id":"open_s6b","schema":{"type":"object","properties":{"status":{"not":{"enum":["banned","deleted"]}}}},"instance":{"status":"active"}}
  ```
  Ground truth: `{"valid":true,"errors":[],"error_count":0}`

**Metric：**
評分器從結果檔中提取 `valid`、`error_count`、每個 error 的 `path` 和 `rule`，與 ground truth 做精確比對：
1. `valid` 欄位 exact match（boolean）
2. `error_count` exact match（integer）
3. 每個 error 的 `path` + `rule` 組合的集合 subset match（ground truth 中的每個 path/rule 都必須出現在輸出中）

**為何不可 gameable：**
- Ground truth 對學生不可見（hidden set）
- 結果為純確定性：相同輸入必給相同輸出，無法靠猜測或關鍵字抽取取分
- Staff perturbation 會改變 schema 結構（例如不同的欄位名稱、不同的數值邊界、不同的 required 列表、不同的 `not` 黑名單），skill 必須正確執行演算法才能通過，而不是 hardcode 答案
- `valid=true` 的 scenario 要求 `errors=[]` 且 `error_count=0`，無法同時用「永遠報錯」策略取分
- `valid=false` 的 scenario 要求精確的 path 和 rule，無法靠「永遠說 clean」取分
- Scenario 6 的一組正反例（s6 / s6b）特別針對「`not` 容易被誤判方向」這種常見錐誤——`not` 違反時是 `valid=false`，但很多 naive 實作會把方向寫反；正反例對照可直接抓出這類錐誤

## 5. 預期失敗模式

- **失敗 1 — 輸出契約格式錯誤（MAST 類別 3：驗證與品質）：**
  觸發點：LLM 產出自然語言描述而非呼叫 `scripts/run.py` 寫結果檔，導致 `AIASE_RESULT_PATH` 指向的檔案不存在。
  處理方式：`SKILL.md` 的 Procedure 明確規定「最後一步必須執行 `python3 <skill_dir>/scripts/run.py` 並寫入結果檔」，且 `run.py` 的錯誤路徑也產出符合契約的 JSON 而非 exception。

- **失敗 2 — task_id 不一致（MAST 類別 1：規格與角色）：**
  觸發點：LLM 忘記把輸入的 `task_id` 傳給 `run.py`，導致結果檔的 `task_id` 為空字串。
  處理方式：`SKILL.md` Procedure 步驟 4 明確要求將輸入的 `task_id` 帶入 `run.py` 的 `--task_id` 參數。

- **失敗 3 — valid/errors 不一致（MAST 類別 3：驗證與品質）：**
  觸發點：LLM 呼叫 validate.py 後，自行修改 `valid` 的值而非直接轉發。
  處理方式：`run.py` 中有防禦性檢查：若 `valid=true` 但 `errors` 非空，則強制覆蓋 `valid=false`。

- **失敗 4 — `not` 方向判斷錯誤（MAST 類別 1：規格與角色）：**
  觸發點：LLM 誤以為「`not` 區塊裡的規則沒違反」代表整體合法，但實際上 `not` 是反向邏輯——子 schema 驗證「通過」才是違反 `not`。
  處理方式：`validate.py` 完全由確定性程式碼處理 `not` 的方向判斷，LLM 不需要、也不應該自己推導；`SKILL.md` 的 Pitfalls 區段明確提醒此處容易弄反方向。

## 6. 互動對象

本 skill 完全獨立，不依賴其他學生的 skill 或 Hermes subagent。驗證邏輯完全在 `scripts/validate.py` 中（確定性，無 LLM）。LLM 的角色只是：解析輸入、呼叫 validate.py、呼叫 run.py 寫結果檔。

## 7. Token Budget 估算

| Scenario | 預估 input tokens | 預估 output tokens | 預估 total |
|---|---:|---:|---:|
| Scenario 1（valid=true） | ~300 | ~150 | ~450 |
| Scenario 2（多重錯誤） | ~350 | ~200 | ~550 |
| Scenario 3（array items） | ~280 | ~180 | ~460 |
| Scenario 4（additionalProperties） | ~280 | ~160 | ~440 |
| Scenario 5（enum） | ~250 | ~150 | ~400 |
| Scenario 6（not，含正反例） | ~320 | ~180 | ~500 |
