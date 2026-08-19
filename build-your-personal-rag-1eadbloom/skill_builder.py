#!/usr/bin/env python3
"""
skill_builder.py — 自動萃取 RAG 知識庫核心洞察，生成 skill.md（Agent Skill 文件）

用法：
    python skill_builder.py                              # 產生 skill.md
    python skill_builder.py --output skill.md             # 指定輸出檔名
    python skill_builder.py --model gemini-2.5-flash       # 指定 LLM 模型

運作方式：
    1. 向 RAG 系統提出一組預先設計的「全域問題」（涵蓋主題範疇、核心概念、
       趨勢、重要實體、方法論、知識邊界、代表性 Q&A），每個問題各自執行一次
       完整的 RAG retrieve + generate 流程。
    2. 將所有問題的回答結果，連同資料來源統計資訊，一併交給 LLM 做最終整合，
       要求其輸出符合作業規定格式的 skill.md 內容。
    3. 將最終內容寫入 --output 指定的檔案（預設 skill.md）。
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

from rag_query import answer_question
from rag_utils import (
    PROCESSED_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    get_chroma_collection,
    get_embedding_function,
    load_env,
)

DEFAULT_MODEL = "ollama/llama3.2:3b"
DEFAULT_OUTPUT = "skill.md"
TOP_K_FOR_SCANNING = 8  # skill_builder 的全域問題涵蓋面廣，檢索較多 chunks 以取得更完整的脈絡

# -----------------------------------------------------------------------
# 全域問題設計
#
# 設計理念：每個問題對應 skill.md 規格中的一個章節，讓 RAG 系統針對
# 「這個知識庫整體」而非單一細節進行回答，藉此把分散在 21 份文件、
# 177 個 chunks 中的知識「升維」整合為章節層級的摘要。
# 問題刻意涵蓋三個子主題（LangGraph / MCP / FastAPI）的交集與關聯，
# 促使 LLM 在回答時主動連結不同文件的內容，而不只是單篇摘要。
# -----------------------------------------------------------------------
GLOBAL_QUESTIONS = {
    "overview": "這個知識庫整體涵蓋哪些主要主題與子領域？請用一段話（200字以內）概括這個知識庫的核心知識範疇與能力邊界。",
    "core_concepts": "這個知識庫中最重要的 10 到 15 個核心概念是什麼？請條列每個概念，並各自附上 1-2 句說明。",
    "trends": "在這個知識庫涵盓的技術領域中（LangGraph 多代理協作、MCP 標準化整合、FastAPI 作為 Agent 後端），目前最重要的發展方向或最佳實踐趨勢有哪些？請條列 3 到 10 點。",
    "entities": "這個知識庫中提到的重要實體有哪些？包括：框架/函式庫名稱、關鍵 API 或類別名稱、設計模式名稱、協定/標準名稱。請分類條列。",
    "methodology": "這個知識庫中，被廣泛建議或視為最佳實踐的方法論、設計原則或工作流程有哪些？例如：錯誤處理方式、安全性設計、測試策略、架構選型的判斷準則。請條列說明。",
    "limitations": "根據這個知識庫的內容範圍，有哪些相關的子主題或細節是這個知識庫沒有涵蓋到、或涵蓋較淺的？（例如：特定版本的 API 細節、特定雲端平台的部署細節、效能調校的具體數據等）",
    "qa_examples": "請列舉 5 個這個知識庫能夠很好回答的代表性問題範例（不需要附答案，只要問題本身），問題應該涵蓋 LangGraph、MCP、FastAPI 三個子主題，並盡量展現知識庫的深度（避免過於表面的問題）。",
}


def collect_source_stats() -> dict:
    """統計 data/raw 與 data/processed 的檔案數量、子主題分類，供 skill.md 的 Metadata 與 Source References 使用。"""
    raw_files = sorted(p for p in RAW_DIR.rglob("*") if p.is_file())
    by_topic: dict[str, list[str]] = {}
    for p in raw_files:
        rel = p.relative_to(RAW_DIR)
        topic = rel.parts[0] if len(rel.parts) > 1 else "misc"
        by_topic.setdefault(topic, []).append(str(rel))
    return {
        "total_files": len(raw_files),
        "by_topic": by_topic,
        "extensions": sorted({p.suffix for p in raw_files}),
    }


def scan_knowledge_base(collection, embedding_fn, model: str) -> dict:
    """對每一個全域問題執行 RAG 流程，回傳 {key: (answer, sources)}。"""
    results = {}
    for key, question in GLOBAL_QUESTIONS.items():
        print(f"  🔎 掃描中: [{key}] {question[:50]}...")
        try:
            answer, sources = answer_question(
                question, collection, embedding_fn, model, top_k=TOP_K_FOR_SCANNING
            )
        except Exception as e:
            print(f"     ❌ 失敗: {e}")
            answer, sources = f"(查詢失敗: {e})", []
        results[key] = {"question": question, "answer": answer, "sources": sources}
    return results


def build_synthesis_prompt(scan_results: dict, stats: dict, model: str) -> str:
    """將所有掃描結果整合成最終 synthesis prompt，要求 LLM 輸出完整 skill.md 內容。"""
    topic_summary = "\n".join(
        f"  - {topic}: {len(files)} 份文件" for topic, files in stats["by_topic"].items()
    )

    sections_text = ""
    for key, data in scan_results.items():
        sections_text += f"\n### 關於「{key}」的初步調查結果\n問題：{data['question']}\n回答：{data['answer']}\n"

    today = datetime.date.today().isoformat()

    prompt = f"""你是一位資深的知識管理專家，任務是將一個 RAG 知識庫的內容整理成一份結構化的 Agent Skill 文件（skill.md），
讓任何 AI Agent 或人類在不需要重新查詢知識庫的情況下，就能快速掌握這個知識領域的全貌。

以下是這個知識庫的基本統計資訊：
- 總文件數：{stats['total_files']} 份
- 子主題分布：
{topic_summary}
- 檔案格式：{', '.join(stats['extensions'])}

以下是針對這個知識庫進行的多輪全域調查結果（每一輪都是一次獨立的 RAG 查詢）：
{sections_text}

請根據以上資訊，撰寫一份完整的 skill.md，**必須嚴格遵循以下章節結構**（章節標題必須完全一致，包含 "## " 前綴）：

# Skill: [請根據知識庫內容自行命名一個精準的主題名稱]

## Metadata
- **知識領域**：[請填寫]
- **資料來源數量**：{stats['total_files']} 份文件
- **最後更新時間**：{today}
- **適用 Agent 類型**：[請填寫，例如：開發助手 / 技術顧問]

## Overview（一段話摘要）
[200字以內，說明這個 Skill 的核心知識範疇與能力邊界]

## Core Concepts（核心概念）
[條列 5–15 個最重要的概念，每個概念附 1–2 句說明]

## Key Trends（最新趨勢）
[條列 3–10 個目前最重要的發展方向或研究趨勢]

## Key Entities（重要實體）
[作者、機構、工具、框架、資料集等，分類條列]

## Methodology & Best Practices（方法論與最佳實踐）
[這個領域中被廣泛接受的方法、流程或原則]

## Knowledge Gaps & Limitations（知識邊界）
[說明這個 Skill 目前的知識侷限，例如資料截止日期、未覆蓋的子主題等]

## Example Q&A（代表性問答）
[列出 3–5 組具代表性的問題與簡短答案，展示此 Skill 能回答的問題類型]

## Source References（來源索引）
[列出資料來源清單，包含文件名稱、類型、日期]

請直接輸出完整的 Markdown 內容（從 "# Skill:" 開始），不要加上任何額外的開場白、解釋或 Markdown code fence 包裹。
內容應該寫得像一份「由領域專家整理的入門指南」，具體、有資訊密度，避免空泛的套話。
"""
    return prompt


def synthesize_skill_md(scan_results: dict, stats: dict, model: str) -> str:
    from litellm import completion

    prompt = build_synthesis_prompt(scan_results, stats, model)

    api_key = os.environ.get("LITELLM_API_KEY")
    base_url = os.environ.get("LITELLM_BASE_URL")

    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一個專業的技術知識管理與文件撰寫助手。"},
            {"role": "user", "content": prompt},
        ],
    }
    if api_key:
        kwargs["api_key"] = api_key

    # Ollama：自動設定 base_url
    if model.startswith("ollama/") and not base_url:
        base_url = "http://localhost:11434"

    if base_url:
        kwargs["api_base"] = base_url

    response = completion(**kwargs)
    content = response["choices"][0]["message"]["content"].strip()

    # 防呆：若 LLM 仍包了 markdown code fence，移除最外層的 ```...``` 包裹
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    return content


def append_source_table(skill_md: str, stats: dict) -> str:
    """
    若 LLM 產出的 Source References 章節過於簡略，補充一份完整的、由程式直接生成的
    資料來源清單表格，確保來源資訊完整、可追溯（不依賴 LLM 是否完整列出每個檔案）。
    """
    today = datetime.date.today().isoformat()
    table_lines = [
        "",
        "### 完整資料來源清單（自動生成）",
        "",
        "| 子主題 | 檔案路徑 | 類型 | 收錄日期 |",
        "| --- | --- | --- | --- |",
    ]
    for topic, files in sorted(stats["by_topic"].items()):
        for f in sorted(files):
            ext = Path(f).suffix.lstrip(".").upper()
            table_lines.append(f"| {topic} | `data/raw/{f}` | {ext} | {today} |")

    return skill_md.rstrip() + "\n" + "\n".join(table_lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="自動萃取 RAG 知識庫核心洞察，生成 skill.md（Build Your Personal RAG）"
    )
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help=f"輸出檔名（預設 {DEFAULT_OUTPUT}）")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"LiteLLM 模型名稱（預設 {DEFAULT_MODEL}）")
    args = parser.parse_args()

    load_env()

    if not PROCESSED_DIR.exists() or not any(PROCESSED_DIR.rglob("*.txt")):
        print("❌ 尚未建立任何索引資料。請先執行：python data_update.py --rebuild")
        return 1

    print("=" * 70)
    print("🛠️  skill_builder.py — 知識庫萃取與 skill.md 生成")
    print(f"   模型: {args.model}　|　輸出: {args.output}")
    print("=" * 70)

    embedding_fn = get_embedding_function()
    _, collection = get_chroma_collection(embedding_fn=embedding_fn)

    if collection.count() == 0:
        print("❌ Vector DB 中沒有任何資料。請先執行：python data_update.py --rebuild")
        return 1

    stats = collect_source_stats()
    print(f"\n[1/3] 知識庫統計：共 {stats['total_files']} 份原始文件，{len(stats['by_topic'])} 個子主題")
    for topic, files in stats["by_topic"].items():
        print(f"   - {topic}: {len(files)} 份")

    print(f"\n[2/3] 執行 {len(GLOBAL_QUESTIONS)} 個全域問題掃描...")
    scan_results = scan_knowledge_base(collection, embedding_fn, args.model)

    print("\n[3/3] 整合知識為 skill.md...")
    try:
        skill_md_content = synthesize_skill_md(scan_results, stats, args.model)
    except Exception as e:
        print(f"❌ LLM 整合失敗: {e}")
        print("   請確認 .env 中的 LITELLM_API_KEY / LITELLM_BASE_URL 是否正確設定。")
        return 1

    skill_md_content = append_source_table(skill_md_content, stats)

    output_path = PROJECT_ROOT / args.output
    output_path.write_text(skill_md_content, encoding="utf-8")

    print(f"\n✅ skill.md 已產生：{output_path}（{len(skill_md_content)} 字元）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
