# CryptoTracker — CLI 加密貨幣查詢與趨勢分析工具

## 專案簡介

CryptoTracker 是一款基於 CLI 的加密貨幣即時查詢與趨勢分析工具。透過 CoinGecko Free API 取得即時市場數據，提供價格查詢、市值排名、收藏管理、歷史價格查詢、趨勢分析及資料匯出等功能。

### v1.0 功能描述與設計動機

v1.0 的設計動機是建立一個**架構清晰、易於擴展**的 CLI 加密貨幣查詢基礎。選擇此主題的原因是加密貨幣市場的數據查詢需求明確（價格、排名、歷史），同時具備豐富的延伸可能性（警示、比較、進階分析）。

核心功能：
- **即時價格查詢**：支援多種法幣（USD、TWD、EUR 等）
- **市值排名**：列出市值前 N 名的加密貨幣
- **收藏管理**：新增、移除、列出收藏幣種
- **歷史價格**：查詢過去 N 天的價格走勢
- **趨勢分析**：基於雙移動平均線交叉策略的趨勢判斷
- **資料匯出**：匯出歷史資料為 CSV 或 JSON 格式

### 從 v1.0 到 v2.0 的演化摘要

v2.0 根據助教 Agent 產生的需求，在不破壞 v1.0 任何介面的前提下，新增了四項主要功能：

1. **啟用個人設定檔**：`config.json` 從預留狀態正式啟用，支援預設法幣與預設筆數
2. **價格警示功能**：為收藏幣種設定價格閾值，執行任何涉及價格的指令時自動檢查
3. **多幣種比較指令**：一次輸入多個幣種，以對齊表格並排顯示關鍵資訊
4. **強化趨勢分析**：新增 RSI 指標與自然語言文字摘要

---

## v1.0 設計決策（Design Decisions）

### 1. 選用 `argparse` 而非 `click` 作為 CLI 框架

**理由**：v1.0 最初設計時考慮過 `click`，但最終選擇 Python 內建的 `argparse`，基於以下考量：
- **零依賴啟動**：即使環境尚未安裝任何 pip 套件，`python main.py --help` 仍可正確執行。這在 CI/CD 環境中尤為重要，GitHub Actions 的檢查項目要求 `--help` 不報錯。
- **Lazy Import 相容性**：`argparse` 完全在標準庫內，不需要在模組頂部匯入第三方套件，使得 Lazy Import 架構得以自然實現——只有在真正執行業務邏輯時才載入 `requests` 等依賴。
- **子指令支援**：`argparse` 的 `add_subparsers()` 雖然語法較 `click` 繁瑣，但對於本專案的指令複雜度已足夠，且未來新增子指令只需追加一段 parser 定義，不影響既有邏輯。

**前瞻性考量**：若 v2.0 需要更複雜的 CLI 框架（如 `typer`），由於 `main.py` 僅負責解析與路由，業務邏輯完全在 `commands.py` 中，替換框架只需重寫 `main.py`，完全不影響其他模組。

### 2. 三層架構分離：CLI → 業務邏輯 → 資料存取

**理由**：將程式拆為三層是 v1.0 最重要的架構決策：
- `main.py`（CLI 介面層）：僅負責參數解析與路由，不包含任何業務邏輯
- `commands.py`（業務邏輯層）：透過依賴注入接收 `storage` 與 `api`，處理核心邏輯
- `storage.py`（資料存取層）：封裝所有 I/O 操作

**前瞻性考量**：這樣的設計確保了 v2.0 的任何改動只影響單一模組：
- 更換儲存後端（JSON → SQLite）→ 只改 `storage.py`
- 更換 API 來源 → 只改 `crypto_api.py`
- 新增 TUI 介面 → 可直接呼叫 `commands.py` 的方法
- 新增 CLI 指令 → 在 `main.py` 加路由、在 `commands.py` 加 handler

**v2.0 驗證**：四項新需求中，`config` 和 `alert` 確實同時觸及了 `main.py`、`commands.py`、`storage.py` 三個模組，但每個模組的改動範圍都是**新增方法**而非修改既有方法，證明了三層架構的有效性。

### 3. `StorageBackend` 以 class 封裝而非函式

**理由**：使用 class 封裝資料存取邏輯，使得 `CommandHandler` 可以透過建構子接收不同的儲存後端。在 v1.0 中已經預先定義了 `get_config()` 和 `save_config()` 方法，即使當時 config 功能尚未啟用。

**前瞻性考量**：class 封裝使得未來可以透過繼承或替換來切換儲存後端（如 `SQLiteBackend(StorageBackend)`），而不需修改 `commands.py` 中的任何呼叫。

**v2.0 驗證**：v2.0 的 `storage.py` 只需要新增 `Alert` 相關的 CRUD 方法（`get_all_alerts`、`add_alert`、`remove_alert`）和正式啟用 `config` 的 `reset_config()` 方法，所有 v1.0 的方法完全不變。

### 4. `CryptoAPIClient` 抽象化 API 呼叫

**理由**：將 API 呼叫封裝為獨立的 class，並透過依賴注入傳入 `CommandHandler`。

**前瞻性考量**：未來若需替換為其他 API（CoinMarketCap、Binance），只需實作相同介面的新 client class。加入快取機制也只需在 client 內部加入快取層。

**v2.0 驗證**：v2.0 的 `crypto_api.py` 完全沒有任何修改。四項新需求全部複用了 v1.0 已有的 `get_price()`、`get_price_history()` 等方法，證明了 API 層抽象的成功。

### 5. 資料模型預留 `metadata` 欄位

**理由**：`Favorite` 與 `PriceRecord` 都預留了 `metadata: dict` 欄位，v1.0 未使用。

**前瞻性考量**：v2.0 可能新增的欄位需求（如標籤、分類、備註等），不需修改資料模型的 schema 就能擴充。

**v2.0 驗證**：v2.0 新增了 `Alert` 資料模型，同樣包含 `metadata` 欄位，保持了一致的設計風格。原有的 `Favorite` 和 `PriceRecord` 資料模型完全不變。

### 6. 趨勢分析演算法獨立於 `utils.py`

**理由**：趨勢分析邏輯放在 `utils.py` 而非 `commands.py`，使得替換或新增演算法不影響其他模組。

**前瞻性考量**：v2.0 若需替換演算法（如從 SMA 換為 EMA、RSI、MACD），只需修改 `utils.py`。

**v2.0 驗證**：v2.0 在 `utils.py` 中新增了 `calculate_rsi()` 和 `generate_trend_summary()` 兩個純函式，修改了 `analyze_trend()` 以加入 RSI 計算，修改了 `format_trend_report()` 以加入摘要顯示。`commands.py` 中的 `cmd_trend()` 只需在呼叫時多傳一個 `summary` 參數，改動極小。

### 7. 所有輸出透過格式化函式

**理由**：`format_currency()`、`format_percentage()`、`format_table()` 等函式統一處理輸出格式。

**v2.0 驗證**：新增的 `compare` 指令直接複用了這三個格式化函式，無需編寫任何新的格式化邏輯。

### 8. 指令介面設計為可擴充

**理由**：使用 `argparse` 的 `add_subparsers()` 設計指令結構，新增指令只需追加一段 parser 定義。

**v2.0 驗證**：v2.0 新增了 `config`（含 get/set/reset 子指令）、`alert`（含 add/remove/list 子指令）、`compare` 三組指令，全部透過追加 parser 定義實現，完全沒有修改 v1.0 的任何 parser 定義。

### 9. `config.json` 預先保留

**理由**：v1.0 的 `storage.py` 已經預先實作了 `get_config()` 和 `save_config()` 方法，config 檔案路徑也已定義，即使當時功能尚未啟用。

**v2.0 驗證**：v2.0 啟用 config 功能時，只需在 `storage.py` 新增 `reset_config()` 方法和 `DEFAULT_CONFIG` 常數，並在 `commands.py` 加入 `_get_effective_currency()` 和 `_get_effective_top_num()` 輔助方法，改動極小。

---

## v2.0 實作說明

### 閱讀與理解 v2.0 需求

收到 `requirements_v2.md` 後，我將四項需求依照「對既有架構的影響程度」進行分類：

1. **需求一（啟用設定檔）**：影響三個模組（storage, commands, main），但主要是「啟用已預留的功能」，改動量最小
2. **需求二（價格警示）**：需要新增資料模型與 CRUD 操作，但儲存架構可完全複用
3. **需求三（多幣種比較）**：純新增功能，完全不影響既有邏輯
4. **需求四（強化趨勢分析）**：修改 `utils.py` 中的分析邏輯，`commands.py` 改動極小

### 需求到 SDD 的映射

| 需求 | 影響的模組 | SDD 章節 |
|---|---|---|
| 啟用設定檔 | storage.py, commands.py, main.py | §2 CLI 規格新增 config 指令、§3 Config 資料模型 |
| 價格警示 | models.py, storage.py, commands.py, utils.py, main.py | §2 CLI 規格新增 alert 指令、§3 Alert 資料模型 |
| 多幣種比較 | commands.py, main.py | §2 CLI 規格新增 compare 指令 |
| 強化趨勢分析 | utils.py, models.py, commands.py | §3 TrendResult 新增 rsi 欄位 |

### 非顯而易見的實作選擇

#### 警示檢查時機的設計決策

我選擇**每次執行涉及價格的指令時都檢查警示**，而非只在特定指令檢查。理由：
- 使用者可能不常執行 `favorite list`，但經常執行 `price` 或 `top`
- 警示的核心價值是「主動通知」，若只在少數指令觸發，使用者可能錯過重要警報
- 為避免額外 API 呼叫，`_check_and_display_alerts()` 接受 `known_prices` 參數，複用指令執行時已取得的價格資料

#### RSI 週期的動態調整

RSI 的標準週期是 14 天，但若使用者查詢的天數少於 14 天，固定週期會導致 RSI 始終回傳預設值 50。因此我設計了動態調整邏輯：`rsi_period = min(14, max(3, len(prices) // 2))`，在資料量不足時自動縮短週期，確保始終有意義的輸出。

#### 設定優先順序的實作

設定優先順序為「指令列參數 > config 設定 > 預設值」。在 `commands.py` 中透過 `_get_effective_currency()` 和 `_get_effective_top_num()` 兩個輔助方法實現：
- 若指令列參數不為 `None`，直接使用
- 否則讀取 config 設定
- config 中若無該項設定，`storage.py` 的 `get_config()` 會自動合併 `DEFAULT_CONFIG`

v1.0 的 `main.py` 中 `--currency` 的 `default` 值為 `"usd"`，v2.0 改為 `None`，讓 `commands.py` 判斷是使用者明確指定還是應讀取設定檔。`--num` 同理。

#### 警示格式的設計

使用 Unicode 方框字元繪製醒目的警告框，確保在任何終端機都能正確顯示，不依賴 ANSI 色彩碼（考慮到部分 CI 環境不支援）。

---

## 向下相容性實作細節

### 核心原則

**v1.0 的任何指令在不修改設定的情況下，行為完全一致。**

### 具體措施

1. **參數預設值策略**：v1.0 的 `--currency` 預設值是 `"usd"`，v2.0 改為 `None`。但在 `_get_effective_currency()` 中，若 `config.json` 不存在或未設定 `default_currency`，會 fallback 到 `DEFAULT_CONFIG` 中的 `"usd"`，行為等同 v1.0。

2. **輸出擴充而非替換**：`trend` 指令的輸出在原有的所有行之後追加 RSI 和 Summary 段落，原有資訊的順序與格式完全不變。

3. **警示為附加資訊**：所有警示訊息出現在正常輸出的最末尾，以視覺分隔框呈現，不影響原有輸出的任何部分。

4. **資料檔案不衝突**：新增的 `alerts.json` 是獨立檔案，不修改 `favorites.json` 和 `price_history.json` 的格式。

5. **Lazy Import 保持不變**：`main.py` 繼續使用 Lazy Import 架構，`--help` 和 `--version` 在無依賴環境下仍可正常執行。

---

## 架構演化比較

| 面向 | v1.0 | v2.0 |
|---|---|---|
| CLI 框架 | argparse（Lazy Import） | argparse（Lazy Import，不變） |
| 儲存層 | JSON 檔案（3 個） | JSON 檔案（4 個，新增 alerts.json） |
| 資料模型數 | 4（Favorite, PriceRecord, CoinInfo, TrendResult） | 5（新增 Alert） |
| CLI 指令數 | 6 群組（price, top, favorite, history, trend, export） | 9 群組（新增 config, alert, compare） |
| 趨勢分析指標 | SMA | SMA + RSI + 自然語言摘要 |
| 個人化設定 | 預留但未啟用 | 正式啟用（法幣、筆數） |
| 主動通知 | 無 | 價格警示（每次查詢自動檢查） |
| `crypto_api.py` 變更 | — | **無變更**（完全複用） |
| `models.py` 變更 | — | 新增 Alert class、TrendResult 加 rsi 欄位 |
| `storage.py` 變更 | — | 新增 Alert CRUD + reset_config() |
| `commands.py` 變更 | — | 新增 4 組指令處理器 + 警示檢查機制 |
| `utils.py` 變更 | — | 新增 RSI、摘要、警示格式化 |
| `main.py` 變更 | — | 新增 3 組指令路由 |

### 架構變動最小化分析

- **`crypto_api.py`**：0 行修改，完全複用
- **`storage.py`**：v1.0 的所有方法完全不變，只新增 4 個 Alert 方法和 1 個 reset_config 方法
- **`commands.py`**：v1.0 的所有 cmd_* 方法核心邏輯不變，僅在結尾加入 `_check_and_display_alerts()` 呼叫
- **`main.py`**：v1.0 的所有 parser 定義不變，只新增 3 組子指令的 parser 和派發邏輯
- **`utils.py`**：v1.0 的所有函式不變，新增 4 個函式，修改 `analyze_trend` 加入 RSI 計算和 `format_trend_report` 加入 summary 參數

---

## 環境需求與執行方式

### v1.0

```bash
cd v1/
pip install -r requirements.txt
python main.py --help

cd v2/
pip install -r requirements.txt
python main.py --help

```
---

## 常用指令範例

# === v1.0 保留指令 ===

# 查詢 Bitcoin 價格
python main.py price --coin bitcoin

# 查詢 Bitcoin 價格（以新台幣顯示）
python main.py price --coin bitcoin --currency twd

# 列出市值前 5 名
python main.py top --num 5

# 收藏管理
python main.py favorite add --coin bitcoin
python main.py favorite add --coin ethereum
python main.py favorite list
python main.py favorite remove --coin bitcoin

# 歷史價格
python main.py history --coin bitcoin --days 7

# 趨勢分析（v2.0 強化：含 RSI + 文字摘要）
python main.py trend --coin bitcoin --days 30

# 匯出資料
python main.py export --coin bitcoin --days 7 --format csv

# === v2.0 新增指令 ===

# 個人設定
python main.py config get
python main.py config set --currency twd
python main.py config set --top-num 20
python main.py config reset

# 價格警示
python main.py alert add --coin bitcoin --above 100000
python main.py alert add --coin ethereum --below 2000
python main.py alert list
python main.py alert remove --id 1

# 多幣種比較
python main.py compare --coins bitcoin,ethereum,solana --days 7
python main.py compare --coins bitcoin,ethereum,solana,cardano --days 30

