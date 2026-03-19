\# CryptoTracker v1.0 — SDD 規格文件



\## 1. 專案概覽（Project Overview）



\- \*\*程式名稱\*\*：CryptoTracker

\- \*\*版本\*\*：v1.0

\- \*\*一句話描述（Elevator Pitch）\*\*：一款 CLI 加密貨幣即時查詢與趨勢分析工具，支援價格查詢、收藏管理、歷史紀錄與簡易趨勢分析。

\- \*\*目標使用者\*\*：對加密貨幣有興趣的個人投資者、開發者與學習者。

\- \*\*核心價值\*\*：透過簡潔的 CLI 介面，快速查詢加密貨幣即時價格，追蹤收藏幣種的價格變化趨勢，無需開啟瀏覽器或複雜的交易平台。



\---



\## 2. CLI 介面規格（Interface Specification）



\### `python main.py <command> \[options]`



| 指令 | 參數 | 說明 | 範例 |

|---|---|---|---|

| `price` | `--coin TEXT` | 查詢指定幣種的即時價格（USD） | `python main.py price --coin bitcoin` |

| `price` | `--coin TEXT --currency TEXT` | 查詢指定幣種的即時價格（指定法幣） | `python main.py price --coin bitcoin --currency twd` |

| `top` | `--num INT` | 列出市值前 N 名的加密貨幣（預設 10） | `python main.py top --num 5` |

| `favorite add` | `--coin TEXT` | 將幣種加入收藏清單 | `python main.py favorite add --coin bitcoin` |

| `favorite remove` | `--coin TEXT` | 將幣種從收藏清單移除 | `python main.py favorite remove --coin bitcoin` |

| `favorite list` | （無） | 列出所有收藏幣種及其即時價格 | `python main.py favorite list` |

| `history` | `--coin TEXT --days INT` | 查詢指定幣種過去 N 天的價格歷史 | `python main.py history --coin bitcoin --days 7` |

| `trend` | `--coin TEXT --days INT` | 對指定幣種進行簡易趨勢分析（移動平均線） | `python main.py trend --coin bitcoin --days 30` |

| `export` | `--coin TEXT --days INT --format TEXT` | 匯出歷史資料為 CSV 或 JSON | `python main.py export --coin bitcoin --days 7 --format csv` |



\### 全域旗標



| 旗標 | 說明 |

|---|---|

| `--help` | 顯示幫助訊息 |

| `--version` | 顯示版本號 |



\---



\## 3. 資料模型（Data Model）



\### Favorite



| 欄位 | 型別 | 說明 | 必填 |

|---|---|---|---|

| id | int | 唯一識別碼，自動遞增 | ✅ |

| coin\_id | str | 幣種 ID（如 `bitcoin`） | ✅ |

| added\_at | str | 加入時間（ISO 8601 格式） | ✅ |

| metadata | dict | 預留擴充欄位 | ❌ |



\### PriceRecord



| 欄位 | 型別 | 說明 | 必填 |

|---|---|---|---|

| id | int | 唯一識別碼，自動遞增 | ✅ |

| coin\_id | str | 幣種 ID | ✅ |

| price\_usd | float | 美元價格 | ✅ |

| queried\_at | str | 查詢時間（ISO 8601 格式） | ✅ |

| metadata | dict | 預留擴充欄位（如其他法幣價格） | ❌ |



\### 儲存格式



資料以 JSON 檔案儲存於 `\~/.cryptotracker/` 目錄下：

~/.cryptotracker/
├── favorites.json ← 收藏清單
├── price_history.json ← 查詢歷史紀錄
└── config.json ← 設定檔（預留）


---

## 4. 模組架構（Module Design）

```mermaid
graph TD
    A[main.py - CLI Entry Point] --> B[commands.py - Command Handlers]
    B --> C[crypto_api.py - API Client]
    B --> D[storage.py - Data Access Layer]
    B --> E[utils.py - Utility Functions]
    D --> F[~/.cryptotracker/*.json]
    C --> G[CoinGecko Free API]
    E --> H[Trend Analysis / Formatting]

模組職責
模組	職責	設計考量
main.py	CLI 入口，解析指令與參數，路由至對應 handler	使用 click library，便於未來擴充子指令
commands.py	各指令的業務邏輯處理	純邏輯層，不直接碰 I/O 細節
crypto_api.py	封裝 CoinGecko API 的呼叫邏輯	抽象化 API 介面，未來可替換為其他資料來源
storage.py	資料存取抽象層（讀寫 JSON）	以 class 封裝，未來可替換為 SQLite 等後端
models.py	資料模型定義（dataclass）	統一資料結構，便於序列化與驗證
utils.py	格式化輸出、趨勢分析演算法	獨立於業務邏輯，可單獨測試與替換

