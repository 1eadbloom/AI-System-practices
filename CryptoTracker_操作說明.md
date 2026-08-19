# CryptoTracker v2.0 — 完整操作說明

---

## 一、環境安裝

### 1. 進入 v2 目錄

```bash
cd v2/
```

### 2. 安裝依賴套件

```bash
pip install -r requirements.txt
```

`requirements.txt` 只有一個依賴：`requests>=2.28.0`

### 3. 設定 CoinGecko API Key（重要）

CoinGecko 免費 API 現在需要 Demo Key，否則可能遇到 `429 Rate Limit` 或 `401` 錯誤。

**取得免費 Key**：https://www.coingecko.com/en/api → 點「Get Demo API」免費申請

**設定環境變數**（每次使用前執行，或加入 `.bashrc` / `.zshrc`）：

```bash
# macOS / Linux
export COINGECKO_API_KEY="你的_demo_key"

# Windows PowerShell
$env:COINGECKO_API_KEY="你的_demo_key"
```

### 4. 確認安裝成功

```bash
python main.py --help
python main.py --version   # 輸出：CryptoTracker 2.0.0
```

`--help` 和 `--version` 不需要 API Key，可隨時執行。

---

## 二、資料儲存位置

所有資料自動儲存於使用者家目錄的 `~/.cryptotracker/` 資料夾：

| 檔案 | 說明 |
|---|---|
| `~/.cryptotracker/favorites.json` | 收藏清單 |
| `~/.cryptotracker/price_history.json` | 查詢記錄 |
| `~/.cryptotracker/config.json` | 個人設定 |
| `~/.cryptotracker/alerts.json` | 價格警示規則 |

---

## 三、設定優先順序

```
指令列參數  >  config.json 設定  >  內建預設值（usd / 10 筆）
```

例如：`config set --currency twd` 後，之後所有查詢預設顯示台幣，但下指令時加上 `--currency usd` 可臨時覆蓋。

---

## 四、完整指令說明

### 4-1. `price` — 查詢即時價格

```bash
python main.py price --coin <幣種ID>
python main.py price --coin <幣種ID> --currency <法幣>
```

| 參數 | 說明 | 預設值 |
|---|---|---|
| `--coin` | 幣種 ID（必填） | — |
| `--currency` | 法幣代碼 | 讀取 config，再 fallback 到 `usd` |

支援的法幣代碼：`usd`、`twd`、`eur`、`jpy`、`gbp`，以及 CoinGecko 支援的其他代碼。

**範例**：
```bash
python main.py price --coin bitcoin
python main.py price --coin ethereum --currency twd
python main.py price --coin solana --currency eur
```

**輸出範例**：
```
  Bitcoin (BITCOIN)
  Price: $67,234.50
  24h Change: ▲ +2.35%
```

> 查詢完成後，若有設定警示規則，會自動在底部顯示觸發的警示。

---

### 4-2. `top` — 市值排名

```bash
python main.py top
python main.py top --num <筆數>
```

| 參數 | 說明 | 預設值 |
|---|---|---|
| `--num` | 顯示筆數（1-250） | 讀取 config，再 fallback 到 `10` |

**範例**：
```bash
python main.py top
python main.py top --num 5
python main.py top --num 50
```

**輸出範例**：
```
  Top 5 Cryptocurrencies by Market Cap

  Rank | Name     | Symbol | Price (USD)  | Market Cap   | 24h Change
  -----+----------+--------+--------------+--------------+-----------
  1    | Bitcoin  | BTC    | $67,234.50   | $1.32T       | ▲ +2.35%
  2    | Ethereum | ETH    | $3,456.78    | $415.23B     | ▲ +1.20%
  ...
```

---

### 4-3. `favorite` — 收藏管理

#### 加入收藏
```bash
python main.py favorite add --coin <幣種ID>
```
加入時會先驗證幣種是否存在（呼叫 API），不存在會報錯。

#### 移除收藏
```bash
python main.py favorite remove --coin <幣種ID>
```

#### 列出收藏
```bash
python main.py favorite list
```
列出所有收藏幣種，並即時查詢每個幣種的當前價格與 24h 漲跌幅。

**範例流程**：
```bash
python main.py favorite add --coin bitcoin
# 輸出：Added: bitcoin

python main.py favorite add --coin ethereum
# 輸出：Added: ethereum

python main.py favorite list
# 輸出：
#   Your Favorites
#   ID | Coin     | Price (USD)  | 24h Change   | Added
#   ---+----------+--------------+--------------+----------
#   1  | bitcoin  | $67,234.50   | ▲ +2.35%     | 2024-03-19
#   2  | ethereum | $3,456.78    | ▲ +1.20%     | 2024-03-19

python main.py favorite remove --coin bitcoin
# 輸出：Removed: bitcoin
```

---

### 4-4. `history` — 歷史價格

```bash
python main.py history --coin <幣種ID>
python main.py history --coin <幣種ID> --days <天數>
```

| 參數 | 說明 | 預設值 |
|---|---|---|
| `--coin` | 幣種 ID（必填） | — |
| `--days` | 查詢天數（正整數） | `7` |

**範例**：
```bash
python main.py history --coin bitcoin
python main.py history --coin bitcoin --days 30
python main.py history --coin ethereum --days 14
```

**輸出範例**：
```
  Price History: BITCOIN (last 7 days)

  Date       | Price (USD)
  -----------+------------
  2024-03-13 | $68,234.00
  2024-03-14 | $67,890.00
  ...
  2024-03-19 | $67,234.50
```

---

### 4-5. `trend` — 趨勢分析（v2.0 強化）

```bash
python main.py trend --coin <幣種ID>
python main.py trend --coin <幣種ID> --days <天數>
```

| 參數 | 說明 | 預設值 |
|---|---|---|
| `--coin` | 幣種 ID（必填） | — |
| `--days` | 分析天數（正整數） | `30` |

v2.0 在原有 SMA 分析基礎上，新增了 RSI 指標與自然語言摘要。

**分析指標說明**：

| 指標 | 說明 |
|---|---|
| SMA (short) | 短期簡單移動平均線 |
| SMA (long) | 長期簡單移動平均線 |
| RSI | 相對強弱指標（0-100）；>70 超買，<30 超賣 |
| Trend | `BULLISH`（看漲）/ `BEARISH`（看跌）/ `NEUTRAL`（中性） |
| Volatility | 波動率（標準差 / 均值 × 100%） |

**範例**：
```bash
python main.py trend --coin bitcoin --days 30
python main.py trend --coin ethereum --days 14
```

**輸出範例**：
```
═══ Trend Analysis: BITCOIN (30 days) ═══

  Current Price:  $67,234.50
  Period High:    $73,000.00
  Period Low:     $58,000.00
  SMA (short):    $68,100.00
  SMA (long):     $65,200.00
  RSI:            62.3
  Price Change:   ▲ +15.92%
  Volatility:     7.45%

  Trend: 📈 BULLISH (看漲)

  ── Summary ──
  BITCOIN 近 30 天呈現上升趨勢，短期均線位於長期均線上方。
  期間內價格大幅上漲 +15.92%，顯示強勁的多頭動能。
  RSI 為 62.3，偏向多方，買方力量略強。

══════════════════════════════════════════════════
```

---

### 4-6. `export` — 匯出歷史資料

```bash
python main.py export --coin <幣種ID>
python main.py export --coin <幣種ID> --days <天數> --format <格式>
```

| 參數 | 說明 | 預設值 |
|---|---|---|
| `--coin` | 幣種 ID（必填） | — |
| `--days` | 天數 | `7` |
| `--format` | 匯出格式：`csv` 或 `json` | `csv` |

匯出的檔案會存在**當前目錄**，檔名格式為 `<幣種>_<天數>d_<時間戳>.csv/json`。

**範例**：
```bash
python main.py export --coin bitcoin --days 30 --format csv
# 輸出：Exported: bitcoin_30d_20240319_143022.csv (31 records)

python main.py export --coin ethereum --days 7 --format json
# 輸出：Exported: ethereum_7d_20240319_143055.json (8 records)
```

---

### 4-7. `config` — 個人設定（v2.0 新增）

#### 查看目前設定
```bash
python main.py config get
```
輸出：
```
  CryptoTracker Configuration

  Setting          | Value
  -----------------+-------
  Default Currency | usd
  Default Top Num  | 10
  Version          | 2.0
```

#### 修改設定
```bash
python main.py config set --currency <法幣代碼>
python main.py config set --top-num <筆數>
python main.py config set --currency twd --top-num 20   # 可同時修改
```

**範例**：
```bash
python main.py config set --currency twd
# 之後所有 price / favorite list / compare 都預設顯示台幣

python main.py config set --top-num 20
# 之後 top 指令預設顯示 20 筆
```

#### 重設回預設值
```bash
python main.py config reset
# 輸出：
#   Configuration reset to defaults:
#     default_currency = usd
#     default_top_num = 10
#     version = 2.0
```

---

### 4-8. `alert` — 價格警示（v2.0 新增）

警示機制的運作方式：**每次執行任何涉及價格的指令**（price、top、favorite list、history、trend、compare）時，系統會自動比對所有警示規則，若當前價格觸發條件則在輸出底部顯示警告框。

#### 新增警示
```bash
python main.py alert add --coin <幣種ID> --above <價格>   # 價格高於時警示
python main.py alert add --coin <幣種ID> --below <價格>   # 價格低於時警示
python main.py alert add --coin bitcoin --above 80000 --below 60000  # 可同時設定
```

#### 列出所有警示
```bash
python main.py alert list
```
輸出：
```
  Price Alerts

  ID | Coin     | Condition | Threshold    | Currency | Created
  ---+----------+-----------+--------------+----------+----------
  1  | bitcoin  | ABOVE     | $80,000.00   | USD      | 2024-03-19
  2  | ethereum | BELOW     | $3,000.00    | USD      | 2024-03-19
```

#### 移除警示
```bash
python main.py alert remove --id <ID>
# 輸出：Removed alert [1]: bitcoin > 80000 USD
```

**觸發警示的顯示效果**：
```
┌─────────────────────────────────────────────┐
│  ⚠️  PRICE ALERTS TRIGGERED                  │
├─────────────────────────────────────────────┤
│ 🚨   BITCOIN = $82,500.00 > $80,000.00      │
└─────────────────────────────────────────────┘
```

---

### 4-9. `compare` — 多幣種比較（v2.0 新增）

```bash
python main.py compare --coins <幣種1,幣種2,幣種3>
python main.py compare --coins <幣種列表> --days <天數>
```

| 參數 | 說明 | 預設值 |
|---|---|---|
| `--coins` | 幣種 ID，逗號分隔（必填） | — |
| `--days` | 比較的歷史天數 | `7` |

**範例**：
```bash
python main.py compare --coins bitcoin,ethereum,solana
python main.py compare --coins bitcoin,ethereum,solana,cardano --days 30
```

**輸出範例**：
```
  Coin Comparison (7-day period)

  Coin     | Price (USD)  | Change (7d) | 24h Change
  ---------+--------------+-------------+-----------
  bitcoin  | $67,234.50   | ▲ +5.23%    | ▲ +2.35%
  ethereum | $3,456.78    | ▲ +3.10%    | ▲ +1.20%
  solana   | $178.45      | ▼ -1.45%    | ▼ -0.80%
```

---

## 五、常見錯誤與排除

| 錯誤訊息 | 原因 | 解決方法 |
|---|---|---|
| `Error: Missing dependencies` | 未安裝 `requests` | 執行 `pip install -r requirements.txt` |
| `API error - HTTP 429` | 超過 API 呼叫限制 | 設定 `COINGECKO_API_KEY` 環境變數；或等待 1 分鐘後重試 |
| `API error - HTTP 401` | API Key 無效或未設定 | 確認 `COINGECKO_API_KEY` 環境變數已正確設定 |
| `Error: Coin 'xxx' not found` | 幣種 ID 不正確 | 幣種 ID 要用完整小寫名稱，如 `bitcoin`（非 `BTC`） |
| `Network error - Request timed out` | 網路連線問題 | 確認網路連線，或稍後重試 |
| `Error: Days must be a positive integer` | `--days` 傳入 0 或負數 | 使用正整數，如 `--days 7` |
| `Error: Alert ID X not found` | 警示 ID 不存在 | 先執行 `alert list` 確認 ID |

---

## 六、完整使用流程範例

以下是從零開始的完整使用流程：

```bash
# 1. 安裝依賴
cd v2/
pip install -r requirements.txt
export COINGECKO_API_KEY="你的key"

# 2. 設定個人偏好（台幣、顯示 20 筆）
python main.py config set --currency twd --top-num 20

# 3. 查看市值排名（自動套用 20 筆設定）
python main.py top

# 4. 加入收藏
python main.py favorite add --coin bitcoin
python main.py favorite add --coin ethereum
python main.py favorite add --coin solana

# 5. 設定價格警示
python main.py alert add --coin bitcoin --above 5000000    # 500 萬台幣時警示
python main.py alert add --coin ethereum --below 100000    # 跌破 10 萬台幣時警示

# 6. 查看收藏（附帶台幣價格 + 自動警示檢查）
python main.py favorite list

# 7. 分析趨勢
python main.py trend --coin bitcoin --days 30

# 8. 多幣種比較
python main.py compare --coins bitcoin,ethereum,solana --days 14

# 9. 匯出數據
python main.py export --coin bitcoin --days 30 --format csv

# 10. 管理警示
python main.py alert list
python main.py alert remove --id 2
```

---

## 七、幣種 ID 參考

CoinGecko 使用**全名小寫**作為幣種 ID（不是交易代碼）：

| 常見幣種 | ID |
|---|---|
| Bitcoin | `bitcoin` |
| Ethereum | `ethereum` |
| Solana | `solana` |
| BNB | `binancecoin` |
| XRP | `ripple` |
| Cardano | `cardano` |
| Dogecoin | `dogecoin` |
| Polkadot | `polkadot` |
| Avalanche | `avalanche-2` |
| Chainlink | `chainlink` |

若不確定 ID，可先執行 `python main.py top --num 50` 查看 `Coin` 欄位的小寫名稱即為 ID。
