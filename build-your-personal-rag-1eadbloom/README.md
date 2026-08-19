[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mhxNhwtV)

# Build Your Personal RAG — AI Agent Frameworks Knowledge Base

一個完整的個人 RAG（Retrieval-Augmented Generation）系統，知識領域聚焦於 **AI Agent 開發框架**：
**LangGraph**（圖狀態管理 / 多代理協作）、**MCP — Model Context Protocol**（工具/資源標準化整合）、
以及 **FastAPI**（Agent 後端服務）。系統涵蓋從原始資料收集、清理、Chunking、Embedding、向量索引，
到 RAG 問答與自動生成 Agent Skill 文件的完整管線。

---

## 目錄

- [系統架構](#系統架構)
- [技術選型與理由](#技術選型與理由)
- [專案結構](#專案結構)
- [快速開始](#快速開始)
- [使用說明](#使用說明)
- [資料來源](#資料來源)
- [設計決策說明](#設計決策說明)
- [已知限制](#已知限制)

---

## 系統架構

```
                          ┌─────────────────────────────────────┐
                          │           data/raw/                  │
                          │  langgraph/*.md  mcp/*.md  fastapi/*.md │
                          │        （21 份原創技術筆記）              │
                          └──────────────────┬────────────────────┘
                                             │
                                  python data_update.py
                                             │
                 ┌───────────────────────────┼───────────────────────────┐
                 │                           │                           │
         [1] 清理 (clean_text)      [2] Chunking (chunk_text)    [3] Embedding
         移除 HTML/頁碼/雜訊空白       段落優先、800字+150字重疊       sentence-transformers
                 │                           │                  (paraphrase-multilingual-MiniLM)
                 ▼                           ▼                           │
          data/processed/*.txt      Chunk(text, index, source)           ▼
                                             │                  ┌──────────────────┐
                                             └─────────────────▶│   ChromaDB         │
                                                                │  (persistent,      │
                                                                │   local, 零設定)     │
                                                                └─────────┬──────────┘
                                                                          │
                        ┌─────────────────────────────────────────────────┤
                        │                                                  │
              python rag_query.py                              python skill_builder.py
                        │                                                  │
              [使用者問題] → embed_query                          [7 個全域問題] → 各自 RAG
                        │                                                  │
              collection.query(top_k)                          逐一檢索 + LLM 回答（LiteLLM）
                        │                                                  │
              組裝 context + 對話歷史                              彙整所有回答 + 來源統計
                        │                                                  │
              LiteLLM completion(model)                          LLM 整合生成 skill.md 章節
                        │                                                  │
                        ▼                                                  ▼
              回答 + 引用來源 [來源: file, 段落 N]                   skill.md（含完整來源索引表）
```

### 資料流摘要

1. **`data_update.py`**：掃描 `data/raw/`（支援 `.md` / `.txt` / `.pdf`）→ 清理文字 → 輸出至
   `data/processed/`（保留 SHA-256 hash 註解供增量更新判斷）→ Chunking（段落優先、固定長度退化）
   → 透過本地 sentence-transformers 模型產生 embedding → upsert 進 ChromaDB（id 為
   `<processed相對路徑>::chunk_<index>`，確保重複執行不會造成資料重複）。
2. **`rag_query.py`**：將使用者問題 embed 後在 ChromaDB 中做向量檢索（cosine similarity），
   取得 top-k 相關 chunks 組成 context，連同對話歷史一併送入 LiteLLM 呼叫 LLM 生成回答，
   並在回答中標註引用來源（檔名 + 段落編號）。支援單次查詢與多輪互動式對話。
3. **`skill_builder.py`**：對知識庫提出 7 個「全域性」問題（涵蓋範疇、核心概念、趨勢、
   重要實體、方法論、知識邊界、代表性 Q&A），各自執行完整 RAG 流程取得回答，
   再將所有結果交給 LLM 整合為符合規格的 `skill.md`，最後由程式補上完整的來源索引表格
   （不依賴 LLM 是否完整列出每個檔案，確保可追溯性）。

---

## 技術選型與理由

| 元件 | 選擇 | 理由 |
| --- | --- | --- |
| **Vector DB** | ChromaDB（Persistent Client，本地檔案） | 純 Python、零設定、無需 Docker / 額外服務，最適合個人專案規模（177 chunks）。`chroma_db/` 已加入 `.gitignore`，避免提交二進位資料庫檔案。 |
| **Embedding** | `sentence-transformers`（`paraphrase-multilingual-MiniLM-L12-v2`，本地模型） | 完全免費、無需 API Key、無需網路（下載一次後可離線運作），同時支援中英文，適合本作業中英文混雜的使用情境（程式碼/技術詞彙為英文，問答可能用中文）。 |
| **LLM Provider** | LiteLLM（統一介面，預設 `gemini-2.5-flash`） | LiteLLM 讓我們可以透過環境變數自由切換底層 LLM provider（OpenAI / Gemini / Claude / 課程提供的 endpoint），程式碼完全不需修改。 |
| **Chunking 策略** | 段落優先（800 字元 + 150 字元重疊），超長段落退化為固定長度切分 | 比起單純固定長度切分，段落優先能讓大部分 chunk 在語意完整的段落邊界結束；overlap 確保跨 chunk 邊界的語意不會完全遺失。 |

---

## 專案結構

```
.
├── data/
│   ├── raw/                    # 原始資料（21 份 .md 技術筆記，分 3 個子主題）
│   │   ├── langgraph/           #   7 份：LangGraph 核心概念、持久化、人機協作、多代理、工具呼叫、串流部署、FAQ
│   │   ├── mcp/                 #   7 份：MCP 協定總覽、Server SDK、Client 整合、認證、設計準則、LangGraph 整合、FAQ
│   │   └── fastapi/             #   7 份：核心概念、依賴注入、非同步、認證、中介層、測試、Agent 後端實務
│   └── processed/               # 清理後的純文字（由 data_update.py 自動產生，含 hash 註解）
├── chroma_db/                   # ChromaDB 持久化資料（gitignored，由 data_update.py 產生）
├── data_update.py               # 資料收集/清理/Chunking/Embedding/索引主程式
├── rag_query.py                 # RAG 問答 CLI（單次查詢 / 互動式多輪對話）
├── skill_builder.py             # 自動萃取知識庫洞察，生成 skill.md
├── rag_utils.py                 # 共用工具函式（清理、Chunking、Embedding wrapper、ChromaDB client）
├── requirements.txt             # Python 套件相依（含 Python 版本需求註解）
├── .env.example                 # 環境變數範本
├── .gitignore                   # 排除 .env、chroma_db/、Python cache 等
└── README.md                    # 本檔案
```

---

## 快速開始

### 1. 環境需求

- Python >= 3.10（開發環境為 3.12.3）
- 約 500MB 可用磁碟空間（sentence-transformers 模型 + ChromaDB 索引）

### 2. 安裝套件

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 設定環境變數

```bash
cp .env.example .env
```

編輯 `.env`，填入課程提供的 LiteLLM API Key 與 Base URL：

```
LITELLM_API_KEY=<課程提供的 key>
LITELLM_BASE_URL=<課程提供的 endpoint>
```

> Embedding 使用本地 sentence-transformers 模型，**不需要**額外的 API Key；
> 只有 `rag_query.py` 與 `skill_builder.py` 呼叫 LLM 生成回答時才需要 `LITELLM_API_KEY`。

### 4. 建立索引（第一次執行會自動下載 embedding 模型，約 420MB，請保持網路暢通）

```bash
python data_update.py --rebuild
```

預期輸出：清理 21 份原始文件 → 切分為約 177 個 chunks → 寫入 ChromaDB。

### 5. 開始問答

```bash
# 互動式多輪對話
python rag_query.py

# 單次查詢
python rag_query.py --query "LangGraph 的 checkpointer 有哪些種類？"
```

### 6. 生成 skill.md

```bash
python skill_builder.py
```

---

## 使用說明

### `data_update.py`

```bash
python data_update.py              # 增量更新：只處理 data/raw/ 中新增/變動的檔案
python data_update.py --rebuild    # 全量重建：清空 data/processed/ 與整個 Vector DB，重新索引所有檔案
python data_update.py --dry-run    # 僅顯示會執行哪些動作，不實際寫入任何檔案或資料庫
```

**冪等性保證**：每個 `data/processed/*.txt` 檔案開頭都記錄了來源檔案的 SHA-256 hash；
重複執行（不加 `--rebuild`）只會處理真正有變動的檔案。ChromaDB 寫入使用固定格式的 chunk id
（`<相對路徑>::chunk_<index>`）搭配 `upsert`，重複執行不會造成資料重複累積。
若某個原始檔案被刪除，下次執行時會自動清除其對應的 processed 檔案（孤兒檔案清理）。

### `rag_query.py`

```bash
python rag_query.py                                     # 互動式對話模式（保留最近 6 輪歷史）
python rag_query.py --query "什麼是 MCP 的 sampling？"      # 單次查詢
python rag_query.py --query "..." --top-k 8               # 自訂檢索 chunk 數量（預設 5）
python rag_query.py --query "..." --model gpt-4o-mini      # 自訂 LiteLLM 模型名稱
```

每次回答都會附上引用來源清單（檔名、段落編號、向量距離），方便追溯答案出處。

### `skill_builder.py`

```bash
python skill_builder.py                       # 產生 skill.md
python skill_builder.py --output my_skill.md   # 自訂輸出檔名
python skill_builder.py --model gemini-2.5-flash
```

---

## 資料來源

知識庫共 21 份原創技術筆記（每份 500–900 字），依官方文件與框架設計原理整理撰寫，
涵蓋三個子主題各 7 篇：

| 子主題 | 涵蓋內容 |
| --- | --- |
| **LangGraph**（7 篇） | 核心概念（State/Node/Edge）、持久化與 Checkpointing、人機協作（interrupt）、多代理架構、工具呼叫與 ReAct、串流與部署、常見問題 |
| **MCP**（7 篇） | 協定架構總覽、Python SDK Server 開發、Client 與 Host 整合、認證與遠端 Server、Tools/Resources/Prompts 設計準則、與 LangGraph 整合、常見問題 |
| **FastAPI**（7 篇） | 核心概念（Path Operation/Pydantic）、依賴注入、非同步與併發模型、認證與安全性、中介層與錯誤處理、測試、AI Agent 後端實務 |

> 內容為基於對這些框架官方文件與設計理念的理解所撰寫的原創技術筆記，
> 並非逐字複製官方文件，以符合著作權合理使用原則。

---

## 設計決策說明

- **為什麼選 ChromaDB 而非 pgvector**：本作業資料規模小（21 份文件、約 177 個 chunks），
  ChromaDB 的零設定、純 Python 特性大幅降低環境設置複雜度，符合個人專案的實際需求；
  若未來資料量成長至需要多使用者並發寫入或更強的 SQL 查詢能力，可再遷移至 pgvector。
- **為什麼選本地 Embedding 而非 API**：避免額外的 API 費用與額度限制，同時讓
  `data_update.py` 在第一次下載模型後可以完全離線執行，提升開發與展示時的穩定性。
- **Chunk 大小（800 字元 + 150 重疊）**：經測試後，800 字元大致對應 150–250 個英文 tokens，
  足以包含一個完整的技術概念說明，同時不會過長導致檢索精準度下降；150 字元的 overlap
  確保概念說明跨越 chunk 邊界時，下一個 chunk 仍保有足夠上下文。
- **skill_builder.py 採用「7 個全域問題」而非單純摘要全部文件**：直接把 21 份文件丟給 LLM
  做摘要，容易得到「每篇各講一點」的鬆散羅列；改為針對 skill.md 規格的每個章節設計專屬問題，
  讓 RAG 系統主動跨文件整合資訊（例如「重要實體」這個問題會同時檢索到 LangGraph、MCP、
  FastAPI 三個子主題中提到的工具與類別），產出的 skill.md 更貼近「一份融會貫通的知識摘要」
  而非「逐篇文件的羅列」。

---

## 已知限制

- Embedding 模型（`paraphrase-multilingual-MiniLM-L12-v2`）為中型多語模型，檢索精準度
  與大型 embedding API（如 OpenAI `text-embedding-3-large`）相比仍有落差，但對本作業規模
  的知識庫已足夠使用。
- 知識庫內容截至撰寫當下（2026 年 6 月）的框架版本，未涵蓋之後可能發布的 API 變更。
- `data/raw/` 中所有文件目前皆為 Markdown 格式；雖然 `data_update.py` 已支援 PDF 解析
  （`pypdf`），但尚未針對掃描型 PDF（需要 OCR）做額外處理。
