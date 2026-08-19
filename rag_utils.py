"""
rag_utils.py
共用工具函式：文字清理、Chunking、檔案 hash 計算、Embedding/LLM client 初始化。
被 data_update.py / rag_query.py / skill_builder.py 共用，避免邏輯重複。
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import chromadb

# ---------------------------------------------------------------------------
# 路徑常數
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CHROMA_PERSIST_DIR_DEFAULT = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "personal_rag_knowledge_base"

# 支援的原始檔格式
SUPPORTED_RAW_EXTENSIONS = {".md", ".txt", ".pdf"}


# ---------------------------------------------------------------------------
# 文字清理
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+\n")


def clean_text(raw_text: str) -> str:
    """
    清理原始文字：
    - 移除 HTML tag
    - 移除行尾多餘空白
    - 將連續空白壓縮為單一空格
    - 將 3 個以上連續換行壓縮為 2 個（保留段落邊界）
    - 移除常見頁首/頁尾雜訊（PDF 常見的頁碼、Header pattern）
    """
    text = raw_text

    # 移除 HTML tag（若資料來源含 HTML 片段）
    text = _HTML_TAG_RE.sub(" ", text)

    # 移除常見 PDF 頁碼樣式，例如獨立一行的 "12" 或 "Page 12 of 40"
    text = re.sub(r"(?im)^\s*page\s+\d+(\s+of\s+\d+)?\s*$", "", text)
    text = re.sub(r"(?m)^\s*\d{1,4}\s*$", "", text)

    # 統一換行符號
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 移除行尾空白
    text = _TRAILING_WS_RE.sub("\n", text)

    # 壓縮連續空白（但保留換行）
    text = _MULTI_SPACE_RE.sub(" ", text)

    # 壓縮過多空行
    text = _MULTI_BLANK_RE.sub("\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Chunking：固定長度（以字元數為單位）+ overlap，並盡量在段落/句子邊界切分
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    text: str
    chunk_index: int
    source_file: str  # 相對於 data/processed 的檔名，例如 "langgraph/01_core_concepts.txt"


def chunk_text(
    text: str,
    source_file: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> list[Chunk]:
    """
    Chunking 策略：固定長度（字元數）+ overlap，並在段落邊界（\n\n）做優先切點。

    做法：
    1. 先以段落（連續兩個換行）切分整篇文章。
    2. 逐段落累加進目前 chunk buffer，若加入後超過 chunk_size，
       則先把目前 buffer 切成一個 chunk，並保留結尾 overlap 字元數作為下一個 chunk 的開頭，
       避免把語意完整的段落硬生生攔腰切斷。
    3. 若單一段落本身就超過 chunk_size（例如一大段程式碼或長段落），
       則退化為固定字元數切分，仍保留 overlap。

    這個策略的好處：大部分情況下 chunk 會在段落邊界結束，語意較完整；
    對於異常長的段落，仍有保底的固定長度切分機制，避免產生單一巨大 chunk。
    """
    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[Chunk] = []
    buffer = ""

    def flush_buffer(buf: str) -> str:
        """將 buffer 內容切成 chunk(s)，回傳要保留作為下一個 chunk 開頭的 overlap 字串。"""
        if not buf.strip():
            return ""
        chunks.append(Chunk(text=buf.strip(), chunk_index=len(chunks), source_file=source_file))
        if chunk_overlap > 0 and len(buf) > chunk_overlap:
            return buf[-chunk_overlap:]
        return ""

    for para in paragraphs:
        # 單一段落本身超過 chunk_size：先 flush 目前 buffer，再對這個段落做固定長度切分
        if len(para) > chunk_size:
            overlap_tail = flush_buffer(buffer)
            buffer = ""
            start = 0
            working = overlap_tail + (" " if overlap_tail else "") + para
            while start < len(working):
                end = start + chunk_size
                piece = working[start:end]
                chunks.append(Chunk(text=piece.strip(), chunk_index=len(chunks), source_file=source_file))
                start = end - chunk_overlap if (end - chunk_overlap) > start else end
            continue

        candidate = (buffer + "\n\n" + para) if buffer else para
        if len(candidate) <= chunk_size:
            buffer = candidate
        else:
            overlap_tail = flush_buffer(buffer)
            buffer = (overlap_tail + "\n\n" + para) if overlap_tail else para

    if buffer.strip():
        chunks.append(Chunk(text=buffer.strip(), chunk_index=len(chunks), source_file=source_file))

    return chunks


# ---------------------------------------------------------------------------
# 檔案 hash（用於 idempotent 增量更新判斷）
# ---------------------------------------------------------------------------

def file_sha256(path: Path) -> str:
    """計算檔案內容的 SHA-256 hash，用於判斷檔案是否有變動。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 原始檔案讀取（依副檔名分派）
# ---------------------------------------------------------------------------

def extract_text_from_file(path: Path) -> str:
    """依副檔名讀取原始檔案內容為純文字。支援 .md / .txt / .pdf"""
    suffix = path.suffix.lower()
    if suffix in (".md", ".txt"):
        return path.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".pdf":
        return _extract_text_from_pdf(path)
    else:
        raise ValueError(f"Unsupported file extension: {suffix}")


def _extract_text_from_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages_text = []
    for page in reader.pages:
        pages_text.append(page.extract_text() or "")
    return "\n\n".join(pages_text)


# ---------------------------------------------------------------------------
# Embedding：使用 sentence-transformers（本地、免費、無需 API Key）
# ---------------------------------------------------------------------------

class EmbeddingFunction(chromadb.EmbeddingFunction):
    """
    包裝 sentence-transformers 模型，提供 ChromaDB 相容的 embedding function 介面
    （實作 __call__ / name / get_config / build_from_config，符合 ChromaDB >= 0.5
    對 EmbeddingFunction Protocol 的要求）。

    模型名稱由 .env 中的 EMBEDDING_MODEL 控制，預設為 sentence-transformers 本地
    多語模型，完全免費、無需 API Key（首次執行需從 HuggingFace 下載模型一次，
    之後完全離線運作）。
    """

    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name or os.environ.get(
            "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        )
        self._model = SentenceTransformer(self.model_name)

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 (Chroma API 要求參數名為 input)
        embeddings = self._model.encode(
            input, show_progress_bar=False, convert_to_numpy=True
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode([text], show_progress_bar=False, convert_to_numpy=True)[0].tolist()

    def name(self) -> str:
        return f"sentence-transformers-{self.model_name}"

    def get_config(self) -> dict:
        return {"model_name": self.model_name}

    @staticmethod
    def build_from_config(config: dict) -> "EmbeddingFunction":
        return EmbeddingFunction(model_name=config.get("model_name"))


def get_embedding_function(model_name: str | None = None) -> EmbeddingFunction:
    """取得 embedding function 單例（每次呼叫會重新建立，呼叫端可自行快取）。"""
    return EmbeddingFunction(model_name=model_name)


# ---------------------------------------------------------------------------
# ChromaDB client
# ---------------------------------------------------------------------------

def get_chroma_collection(embedding_fn: EmbeddingFunction | None = None, persist_dir: str | None = None):
    """
    取得（或建立）ChromaDB persistent collection。

    persist_dir 預設讀取環境變數 CHROMA_PERSIST_DIR，若未設定則使用專案根目錄下的 ./chroma_db。
    """
    import chromadb

    persist_path = persist_dir or os.environ.get("CHROMA_PERSIST_DIR", str(CHROMA_PERSIST_DIR_DEFAULT))
    client = chromadb.PersistentClient(path=persist_path)

    if embedding_fn is not None:
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    else:
        collection = client.get_or_create_collection(name=COLLECTION_NAME)

    return client, collection


# ---------------------------------------------------------------------------
# .env 載入
# ---------------------------------------------------------------------------

def load_env() -> None:
    """載入 .env 檔案（若存在）。在所有進入點腳本最開頭呼叫。"""
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
