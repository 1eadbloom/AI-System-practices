"""BM25-lite：給每筆文件對查詢打相關度分數，回傳排序後的前 K 筆。整個作業的核心。
tokenize() 已給你；bm25_search() 的計分要你填。"""
from __future__ import annotations
import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """小寫化後，取出英數字詞與單個 CJK 字元。不做 stemming。（已提供）"""
    return _TOKEN_RE.findall(text.lower())


def bm25_search(
    query: str,
    docs: list[dict],
    k: int = 8,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[dict]:
    """
    實作標準 BM25 排序。
    docs = [{"id": str, "text": str}, ...]；回傳 [{"id", "score"}, ...]（高到低，前 k 筆）。

      score(q,d) = Σ_qi IDF(qi) * (tf*(k1+1)) / (tf + k1*(1 - b + b*|d|/avgdl))
      IDF(qi)    = ln( (N - n + 0.5)/(n + 0.5) + 1 )
    """
    if not docs:
        return []

    # 1) Tokenize all documents and the query
    N = len(docs)
    tokenized_docs = [tokenize(d["text"]) for d in docs]
    query_tokens = tokenize(query)

    # Compute document lengths and avgdl
    doc_lengths = [len(tokens) for tokens in tokenized_docs]
    avgdl = sum(doc_lengths) / N if N > 0 else 1.0

    # 2) Compute document frequency (df) for each unique query term
    df: dict[str, int] = {}
    for token in set(query_tokens):
        df[token] = sum(1 for tokens in tokenized_docs if token in tokens)

    # 3) Score each document
    results = []
    for i, (doc, tokens) in enumerate(zip(docs, tokenized_docs)):
        tf_counts = Counter(tokens)
        dl = doc_lengths[i]
        score = 0.0
        for qi in query_tokens:
            tf = tf_counts.get(qi, 0)
            if tf == 0:
                continue
            n = df.get(qi, 0)
            idf = math.log((N - n + 0.5) / (n + 0.5) + 1)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avgdl)
            score += idf * (numerator / denominator)
        results.append({"id": doc["id"], "score": score})

    # 4) Sort by score descending; stable sort preserves original order on ties
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:k]
