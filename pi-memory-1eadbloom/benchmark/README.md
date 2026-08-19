# Benchmark — 記憶檢索評測（study tool）

本資料夾提供兩組語料，皆**不計入自動評分**，供自行量測與探索：

| 用途 | 語料 | 查詢 | 規模 |
|---|---|---|---|
| **基準（與單元測試同一掛）** | `corpus.jsonl` | `queries.jsonl` | 30 筆 / 21 題 |
| **自行探索（較大、較真實）** | `corpus_large.jsonl` | `queries_large.jsonl` | 100 筆 / 40 題 |

> 自動評分只看 `tests/` 的單元測試（30 筆等級的固定資料）。本資料夾的兩組語料都是讓你**自己**觀察、迭代用的，分數不直接計分；但在 REPORT 中報告與分析所得數字會列入評量。

## 執行

```bash
# 基準語料（預設）
python benchmark/run_benchmark.py --k 5 --per-query

# 大語料（自行探索）
python benchmark/run_benchmark.py --corpus corpus_large.jsonl --queries queries_large.jsonl --k 5 --per-query
```

輸出含 **Recall@k / MRR / nDCG@k**，並印出對應語料的純 BM25 參考值。

## 為什麼提供大語料？

30 筆語料偏小，每題命中與否會讓分數波動約 5%，distractor（語義相近但不相關的干擾項）也較少。100 筆 / 40 題的版本刻意加入大量同主題、不同細節的記憶（例如多筆都談 database、deploy、security），更能呈現以下兩個在小語料上不易觀察到的現象：

1. **詞彙不匹配（vocabulary mismatch）**：查詢用的詞與記憶實際用字不同（例如查詢說 "package manager"，記憶寫的是 pnpm / npm；查詢說 "payment provider"，記憶寫的是 Stripe），純 BM25 因為只比對字面而完全接不到。
2. **distractor 稀釋**：語料變大後，常見詞被許多文件共享，正確記憶的排序被雜訊文件擠下，Recall 反而下降。

這兩點正是 lexical 檢索（BM25）的天花板，也是任務二導入 hybrid retrieval（BM25 + 本地 embedding）想要改善的目標。建議流程：先用大語料跑出純 BM25 的數字 → 找出哪些題接不到、為什麼 → 做 hybrid → 回來再跑一次，觀察是否提升，並把分析寫進 REPORT。

## 實測結果（基準語料，k=5）

### 純 BM25

| 指標 | 分數 | 參考基準 |
|---|---|---|
| Recall@5 | 0.810 | ≈ 0.810 ✅ |
| MRR | 0.810 | ≈ 0.810 ✅ |
| nDCG@5 | 0.802 | ≈ 0.802 ✅ |

### Hybrid BM25 + Embedding（RRF，`sentence-transformers/all-MiniLM-L6-v2`）

| 指標 | 純 BM25 | Hybrid | 差異 |
|---|---|---|---|
| Recall@5 | 0.810 | 0.810 | = 持平 |
| MRR | 0.810 | 0.786 | ↓ −0.024 |
| nDCG@5 | 0.802 | 0.788 | ↓ −0.014 |

**說明：** Recall@5 持平——正確答案仍找得到；MRR / nDCG 微降是因為 RRF 融合偶爾把正確答案從第 1 名推到第 2–3 名。此現象在小型、詞彙重疊度高的語料（30 筆）上屬正常，原因是 BM25 在這類語料已達上限，加入 embedding 引入微小噪訊。Hybrid 的優勢預期在大語料（100 筆 / 40 題）的 vocabulary mismatch 與跨語言題上顯現。

執行指令：

```bash
# 純 BM25（預設）
python benchmark/run_benchmark.py --k 5

# Hybrid
python benchmark/run_benchmark.py --hybrid --k 5

# Hybrid（需離線快取模型）
set HF_HUB_OFFLINE=1
python benchmark/run_benchmark.py --hybrid --k 5
```
