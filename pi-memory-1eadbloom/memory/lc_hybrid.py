"""LangChain 版混合檢索（對照實驗用）：BM25 + 向量檢索，以 EnsembleRetriever（RRF）融合。

與 hybrid.py 的差異（比較重點）：
- 索引只建一次（LCHybridIndex），之後每次查詢不必重算全部文件的嵌入。
- BM25 使用 rank_bm25（經 BM25Retriever），斷詞沿用 bm25.tokenize()，確保兩版條件一致。
- 融合由 EnsembleRetriever 完成（weights = [1-alpha, alpha]）。

原本的 bm25.py / hybrid.py 完全不動。
注意：LangChain 1.x 中 EnsembleRetriever 位於 langchain_classic；
BM25Retriever / FAISS 仍在 langchain_community（該套件已宣布逐步停止維護）。
"""
from __future__ import annotations
import os

from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_classic.retrievers import EnsembleRetriever

from .bm25 import tokenize

_DEFAULT_MODEL = os.environ.get("MEMORY_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def default_embeddings():
    """與 hybrid.py 相同的嵌入模型，避免模型差異影響比較。"""
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=_DEFAULT_MODEL)


class LCHybridIndex:
    """docs = [{"id": str, "text": str}, ...]。embeddings=None 時退化為純 BM25 檢索。"""

    def __init__(self, docs: list[dict], embeddings=None, alpha: float = 0.5, rrf_c: int = 60):
        n = len(docs)
        lc_docs = [Document(page_content=d["text"], metadata={"id": d["id"]}) for d in docs]
        # k=n：和 hybrid.py 一樣先對「全部文件」排名再融合
        self.bm25 = BM25Retriever.from_documents(lc_docs, preprocess_func=tokenize, k=n)
        if embeddings is None:
            self.retriever = self.bm25
        else:
            vs = FAISS.from_documents(lc_docs, embeddings)
            vec = vs.as_retriever(search_kwargs={"k": n})
            self.retriever = EnsembleRetriever(
                retrievers=[self.bm25, vec],
                weights=[1 - alpha, alpha],
                c=rrf_c,
                id_key="id",
            )

    def search(self, query: str, k: int = 8) -> list[dict]:
        hits = self.retriever.invoke(query)
        return [{"id": h.metadata["id"]} for h in hits[:k]]
