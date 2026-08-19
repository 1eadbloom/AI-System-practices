#!/usr/bin/env python3
"""
rag_query.py — RAG 問答 CLI 介面

用法：
    python rag_query.py                                  # 互動式多輪對話模式
    python rag_query.py --query "你的問題"                  # 單次查詢模式
    python rag_query.py --query "..." --top-k 5            # 自訂檢索 chunk 數量
    python rag_query.py --query "..." --model gemini-2.5-flash  # 自訂 LLM 模型

每次查詢完整執行 RAG 流程：Embed Query → Retrieve top-k Chunks → 組裝 Prompt
→ 透過 LiteLLM 呼叫 LLM → 回傳含引用來源的回答。

互動式模式會保留對話歷史（至少 3 輪），讓使用者可以進行連續追問。
"""

from __future__ import annotations

import argparse
import os
import sys

from rag_utils import (
    PROJECT_ROOT,
    get_chroma_collection,
    get_embedding_function,
    load_env,
)

DEFAULT_MODEL = "ollama/llama3.2:3b"
DEFAULT_TOP_K = 5
MAX_HISTORY_TURNS = 6  # 保留最近 6 輪（3 組使用者問題 + 3 組助理回答）以上的歷史

SYSTEM_PROMPT = """你是一個基於檢索增強生成（RAG）技術的知識問答助手。
你會被提供一組從個人知識庫中檢索出的相關文件片段（context），請僅根據這些 context 回答使用者的問題。

規則：
1. 回答必須基於提供的 context，不可憑空捏造 context 中沒有的資訊。
2. 如果 context 中沒有足夠資訊回答問題，請誠實說明「知識庫中沒有找到足夠相關的資訊」，不要瞎猜。
3. 回答中，請在引用特定事實或說法時，標註其來源（使用 context 中提供的 [來源: 檔名, 段落 N] 標記）。
4. 回答語氣專業、簡潔，避免不必要的贅詞。
5. 若使用者的問題與先前對話有關聯，請結合對話歷史理解問題的完整脈絡。
"""


def format_context(retrieved: dict) -> tuple[str, list[dict]]:
    """
    將檢索結果組裝成 prompt context 字串，並回傳結構化的來源清單（供顯示用）。
    """
    documents = retrieved["documents"][0]
    metadatas = retrieved["metadatas"][0]
    distances = retrieved.get("distances", [[None] * len(documents)])[0]

    context_blocks = []
    sources = []
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        source_file = meta.get("source_file", "unknown")
        chunk_index = meta.get("chunk_index", "?")
        tag = f"[來源: {source_file}, 段落 {chunk_index}]"
        context_blocks.append(f"{tag}\n{doc}")
        sources.append({
            "source_file": source_file,
            "chunk_index": chunk_index,
            "distance": dist,
            "snippet": doc[:150] + ("..." if len(doc) > 150 else ""),
        })

    context_str = "\n\n---\n\n".join(context_blocks)
    return context_str, sources


def build_user_prompt(question: str, context_str: str) -> str:
    return f"""以下是從知識庫中檢索出的相關文件片段：

{context_str}

---

使用者問題：{question}

請根據上方 context 回答問題，並標註引用來源。"""


def retrieve(collection, embedding_fn, question: str, top_k: int) -> dict:
    query_vector = embedding_fn.embed_query(question)
    results = collection.query(query_embeddings=[query_vector], n_results=top_k)
    return results


def call_llm(model: str, messages: list[dict]) -> str:
    """
    透過 LiteLLM 統一介面呼叫 LLM。
    支援：
      - Ollama 本地模型：model="ollama/llama3.2:3b"（需先啟動 Ollama）
      - HuggingFace Inference API：model="huggingface/HuggingFaceH4/zephyr-7b-beta"
        並在 .env 設定 LITELLM_API_KEY=hf_xxxx
      - 其他（OpenAI / Gemini 等）：設定對應的 LITELLM_API_KEY / LITELLM_BASE_URL
    """
    from litellm import completion

    api_key = os.environ.get("LITELLM_API_KEY")
    base_url = os.environ.get("LITELLM_BASE_URL")

    kwargs = {"model": model, "messages": messages}
    if api_key:
        kwargs["api_key"] = api_key

    # Ollama：自動設定 base_url（除非 .env 已覆寫）
    if model.startswith("ollama/") and not base_url:
        base_url = "http://localhost:11434"

    if base_url:
        kwargs["api_base"] = base_url

    response = completion(**kwargs)
    return response["choices"][0]["message"]["content"]


def print_sources(sources: list[dict]) -> None:
    print("\n📚 引用來源：")
    for i, s in enumerate(sources, 1):
        dist_str = f"(相似度距離: {s['distance']:.4f})" if s["distance"] is not None else ""
        print(f"  [{i}] {s['source_file']} — 段落 {s['chunk_index']} {dist_str}")
        print(f"      \"{s['snippet']}\"")


def answer_question(
    question: str,
    collection,
    embedding_fn,
    model: str,
    top_k: int,
    history: list[dict] | None = None,
) -> tuple[str, list[dict]]:
    """執行完整 RAG 流程：retrieve -> build prompt -> call LLM。回傳 (answer, sources)。"""
    retrieved = retrieve(collection, embedding_fn, question, top_k)

    if not retrieved["documents"][0]:
        return "知識庫中目前沒有任何資料，請先執行 `python data_update.py --rebuild` 建立索引。", []

    context_str, sources = format_context(retrieved)
    user_prompt = build_user_prompt(question, context_str)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-MAX_HISTORY_TURNS:])
    messages.append({"role": "user", "content": user_prompt})

    answer = call_llm(model, messages)
    return answer, sources


def run_single_query(args) -> int:
    embedding_fn = get_embedding_function()
    _, collection = get_chroma_collection(embedding_fn=embedding_fn)

    print(f"🔎 問題: {args.query}")
    print(f"   (top-k={args.top_k}, model={args.model})\n")

    try:
        answer, sources = answer_question(
            args.query, collection, embedding_fn, args.model, args.top_k
        )
    except Exception as e:
        print(f"❌ LLM 呼叫失敗: {e}")
        print("   請確認 .env 中的 LITELLM_API_KEY / LITELLM_BASE_URL 是否正確設定。")
        return 1

    print("💡 回答:")
    print(answer)
    if sources:
        print_sources(sources)
    return 0


def run_interactive(args) -> int:
    embedding_fn = get_embedding_function()
    _, collection = get_chroma_collection(embedding_fn=embedding_fn)

    print("=" * 70)
    print("🤖 Personal RAG 互動式問答模式")
    print(f"   模型: {args.model}　|　top-k: {args.top_k}")
    print("   輸入問題開始對話，輸入 'exit' 或 'quit' 離開。")
    print("=" * 70)

    history: list[dict] = []

    while True:
        try:
            question = input("\n🧑 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再見！")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            print("👋 再見！")
            break

        try:
            answer, sources = answer_question(
                question, collection, embedding_fn, args.model, args.top_k, history=history
            )
        except Exception as e:
            print(f"❌ LLM 呼叫失敗: {e}")
            print("   請確認 .env 中的 LITELLM_API_KEY / LITELLM_BASE_URL 是否正確設定。")
            continue

        print(f"\n🤖 助理: {answer}")
        if sources:
            print_sources(sources)

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})
        history = history[-MAX_HISTORY_TURNS:]

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RAG 問答 CLI 介面（Build Your Personal RAG）"
    )
    parser.add_argument("--query", type=str, default=None, help="單次查詢模式：直接提供問題字串")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help=f"檢索 top-k 個相關 chunks（預設 {DEFAULT_TOP_K}）")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"LiteLLM 模型名稱（預設 {DEFAULT_MODEL}）")
    args = parser.parse_args()

    load_env()

    if not (PROJECT_ROOT / "data" / "processed").exists():
        print("⚠️  尚未建立任何索引資料。請先執行：python data_update.py --rebuild")

    if args.query:
        return run_single_query(args)
    else:
        return run_interactive(args)


if __name__ == "__main__":
    sys.exit(main())
