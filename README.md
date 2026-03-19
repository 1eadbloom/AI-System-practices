# CryptoTracker — CLI 加密貨幣查詢與趨勢分析工具

## 專案簡介

CryptoTracker 是一款基於 CLI 的加密貨幣即時查詢與趨勢分析工具。透過 CoinGecko Free API 取得即時市場數據，提供價格查詢、市值排名、收藏管理、歷史價格查詢、趨勢分析及資料匯出等功能。

### v1.0 功能描述

- **即時價格查詢**：支援多種法幣（USD、TWD、EUR 等）
- **市值排名**：列出市值前 N 名的加密貨幣
- **收藏管理**：新增、移除、列出收藏幣種
- **歷史價格**：查詢過去 N 天的價格走勢
- **趨勢分析**：基於雙移動平均線交叉策略的趨勢判斷
- **資料匯出**：匯出歷史資料為 CSV 或 JSON 格式

### 從 v1.0 到 v2.0 的演化摘要

> v2.0 的方向將由助教 Agent 決定，此處將在收到 `requirements_v2.md` 後更新。

---

## v1.0 設計決策（Design Decisions）

### 1. 選用 `click` 而非 `argparse` 作為 CLI 框架

**理由**：`click` 原生支援子指令群組（Group），使得 `favorite add` / `favorite remove` / `favorite list` 這類巢狀指令可以自然地表達。相較之下，`argparse` 的 subparser 巢狀較為繁瑣，且未來若需新增第二層子指令（如 `trend analyze --method sma`），`click` 的擴充性更佳。此外，`click` 的 decorator 語法讓新增指令只需加一個函式與裝飾器，不需修改已有程式碼，符合 Open-Closed Principle。

### 2. 三層架構分離：CLI → 業務邏輯 → 資料存取

**理由**：將程式拆為三層：
- `main.py`（CLI 介面層）：僅負責參數解析與路由
- `commands.py`（業務邏輯層）：處理核心邏輯
- `storage.py`（資料存取層）：封裝所有 I/O 操作

這樣的設計使得 v2.0 若需：
- 更換 CLI 框架（如 `typer`）→ 只改 `main.py`
- 更換儲存後端（如 JSON → SQLite）→ 只改 `storage.py`
- 更換 API 來源 → 只改 `crypto_api.py`
- 新增 TUI 介面 → 可直接呼叫 `commands.py` 的方法

### 3. `StorageBackend` 以 class 封裝而非函式

**理由**：使用 class 封裝資料存取邏輯，可以在 v2.0 時透過繼承或替換來切換儲存後端（如 `SQLiteBackend(StorageBackend)`），而不需修改 `commands.py` 中的任何呼叫。`CommandHandler` 透過依賴注入接收 `storage` 參數，使得替換後端只需在初始化時指定。

### 4. `CryptoAPIClient` 抽象化 API 呼叫

**理由**：將 API 呼叫封裝為獨立的 class，並透過依賴注入傳入 `CommandHandler`。未來若需：
- 替換為 CoinMarketCap API → 實作新的 client class，介面相同
- 加入快取機制 → 在 client 內部加入快取層
- 加入 mock 測試 → 注入 mock client

### 5. 資料模型預留 `metadata` 欄位

**理由**：`Favorite` 與 `PriceRecord` 都預留了 `metadata: dict` 欄位，v1.0 未使用。這是為了 v2.0 可能新增的欄位需求（如標籤、分類、備註等），不需修改資料模型的 schema 就能擴充。

### 6. 趨勢分析演算法獨立於 `utils.py`

**理由**：趨勢分析邏輯放在 `utils.py` 而非 `commands.py`，使得 v2.0 若需替換演算法（如從 SMA 換為 EMA、RSI、MACD 等），只需修改 `utils.py` 中的函式，不影響其他模組。

### 7. 所有輸出透過格式化函式

**理由**：`format_currency()`、`format_percentage()`、`format_table()` 等函式統一處理輸出格式。v2.0 若需改為 rich TUI 或其他格式化方式，只需替換這些函式。

### 8. 指令介面設計為可擴充

**理由**：使用 `click.group()` 設計指令結構，新增指令只需加一個 `@cli.command()` 函式，不會影響現有指令。`favorite` 作為子群組，未來可擴充更多子指令（如 `favorite sort`、`favorite tag`）。

---

## 環境需求與執行方式

### v1.0

```bash
cd v1/
pip install -r requirements.txt
python main.py --help