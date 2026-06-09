# HW4 Report：Pi Memory — Reflection \& Analysis

## (1) 如何判斷「記憶有效」，為何指標不可作弊

我採用三個指標量化記憶檢索品質：**Recall@k**（前 k 個結果中是否命中正確答案）、**MRR**（倒排名均值，越高代表正確答案排得越前面）、**nDCG@k**（考慮排名折扣的標準化增益）。

這些指標不可作弊的關鍵在於：**語料（corpus）與查詢（queries）是分離的固定集合，且標準答案（relevant\_ids）事先定義好**。如果只針對公開測試的 30 筆語料硬編碼答案，隱藏測試集的資料會是不同的觀察記錄，hardcode 無效。`bm25\\\_search()` 必須是確定性的通用演算法，每次輸入相同資料就輸出相同排序，才能被客觀重現與驗證。

Verifiability Mindset 的核心：**把「記憶有沒有用」從主觀感受轉換成可客觀驗算的數字。**

## (2) Benchmark 分數與錯誤分析

### 純 BM25（基準語料，k=5）

|指標|分數|
|-|-|
|Recall@5|**0.810**|
|MRR|**0.810**|
|nDCG@5|**0.802**|

與參考基準完全吻合，代表 BM25 實作正確。

### 純 BM25 接不到的題目分析

以下 4 題 Recall=0，原因各有不同：

1. **"how big can an uploaded picture be?"** → 答案記憶用的是「upload size limit」等技術術語，查詢用的是 "big"、"picture"，詞彙不重疊。這是 **vocabulary mismatch** 問題。
2. **"when is the team sync meeting each week?"** → 記憶可能用「weekly standup」或 "weekly sync"，查詢用 "team sync meeting"，部分 overlap 但不夠精確，被 distractor 淹沒。
3. **"我要怎麼把新功能慢慢開放給部分使用者？"** → 中文查詢（feature flag / 逐步推出），若記憶用英文 "feature flag" 記錄，BM25 完全不會有 IDF 增益，完全接不到。**跨語言的 lexical 天花板**。
4. **"怎麼確認我的程式碼風格符合規範？"** → 若記憶寫 "linter"、"ESLint"、"code style check"，查詢是語義描述，BM25 因字面不重疊而失敗。

### Hybrid Retrieval（BM25 + Embedding RRF，基準語料，k=5）

|指標|純 BM25|Hybrid|差異|
|-|-|-|-|
|Recall@5|0.810|**0.810**|= 持平|
|MRR|0.810|**0.786**|↓ −0.024|
|nDCG@5|0.802|**0.788**|↓ −0.014|

任務二實作了 **BM25 + Sentence Embedding RRF fusion**（`memory/hybrid.py`），使用 `sentence-transformers/all-MiniLM-L6-v2`（本地快取，離線執行）。

**結果分析：Hybrid 在小語料上略低於純 BM25，是正常現象。**

原因有三：

1. **小語料對 BM25 有利**：30 筆語料中 distractor 少，lexical overlap 就足夠精確排序，加入 embedding 反而引入微小噪訊。
2. **MRR / nDCG 對「排名位置」敏感**：Recall@5 持平代表 hybrid 依然找到正確答案，但 embedding 的 RRF 融合有時把正確答案從第 1 名推到第 2–3 名，MRR 因此下滑。
3. **alpha=0.5 的 RRF 權重在 lexical 友善語料上不是最佳值**：BM25 在此語料的表現已接近上限，降低 alpha（給 BM25 更高權重）可緩解。

**Hybrid 的預期優勢在大語料上**：100 筆 / 40 題版本的 vocabulary mismatch 題（如中文查詢對英文記憶、"package manager" 對 "pnpm"）是純 BM25 的天花板，embedding 的語義理解才能補回這類遺漏。

## (3) 確定性 vs 機率性的分界

|層|確定性 / 機率性|說明|
|-|-|-|
|`tokenize()`|✅ 確定性|regex，相同輸入永遠相同輸出|
|`bm25\\\_search()`|✅ 確定性|純數學計算，可重現|
|`JsonStore`|✅ 確定性|SHA-256 去重、JSON 序列化|
|Embedding（任務二）|⚠️ 確定性（固定模型）|固定模型版本即固定輸出|
|Local LLM（demo）|❌ 機率性|溫度 > 0，每次回答可能略不同|

設計原則：**確定性外殼包住機率性核心**。BM25 做 retrieval（確定性），LLM 做生成（機率性）——測試只測前者，後者只在 demo 出現。

## (4) Token 預算取捨

`build\\\_injection()` 預設 budget=2000 tokens（粗估：字元數/4）。取捨邏輯：

* 按 BM25 分數由高到低貪心填入，直到接近 budget 上限。
* 本地小模型 context window 通常 4k–8k，2000 tokens 約佔 25–50%，為合理上限。
* 若 budget 太大：context 被低品質記憶佔滿，稀釋當前 user prompt 的注意力；太小：高分記憶截斷。

## (5) 與 `/compact` 的關係

||`/compact`|Pi Memory（本作業）|
|-|-|-|
|範圍|同一 session 內壓縮對話|跨 session 持久記憶|
|存活時間|session 關閉即消失|永久存於硬碟，直到 `store.clear()`|
|用途|節省 context window|補回「上次說了什麼」|

兩者互補：`/compact` 管理當前 session 的 token 效率；本作業的 memory 負責跨 session 的知識傳遞。

## (6) 本系統 vs 手寫 `PROGRESS.md`

||`PROGRESS.md`|Pi Memory|
|-|-|-|
|記憶觸發|人工手動更新|自動（`remember` 工具 / capture）|
|檢索方式|人眼掃描|BM25 自動排序|
|注入 context|人工貼上|`before\\\_agent\\\_start` 自動注入|
|規模|幾十行 → 難以維護|數百筆 observation 仍可精確检索|
|缺點|勞力密集、忘記更新|BM25 有語義天花板（需 hybrid 補足）|

## (7) 環境記錄

* Python：3.10+（開發使用 3.12）
* 本地模型：任意 OpenAI-compatible endpoint（Gemma 4 / Qwen / Llama 均可）
* embedding 模型：`sentence-transformers/all-MiniLM-L6-v2`（首次執行自動下載，\~90MB）
* 後端：LM Studio 或 Ollama（OpenAI-compatible）
* 無 GPU 亦可執行（純 CPU，核心測試與 benchmark 完全不需要 LLM）
* Windows 上 import.meta.url 的 pathname 會多一個前置 /（如 /C:/...），需要用 regex 移除才能正確定位 REPO\_ROOT ((經排查為此為 Windows 平台已知 Node.js 行為，extension.ts 搭配Python 記憶層（capture / inject）在本機驗證均運作正常（見 demo/）。)

