#!/usr/bin/env python3
"""
data_update.py — 資料收集、清理、Chunking、Embedding、索引腳本

用法：
    python data_update.py                # 增量更新：只處理新增/變動的檔案
    python data_update.py --rebuild       # 全量重建：清空 data/processed/ 與 Vector DB，重新索引所有檔案
    python data_update.py --dry-run       # 只顯示會執行哪些動作，不實際寫入

冪等性設計：
    - data/processed/ 中每個 .txt 檔案都會在檔案開頭寫入一行 hash 註解（# source_hash: <sha256>），
      記錄產生它的原始檔案內容 hash。
    - 每次執行時，比對 data/raw/ 中檔案的目前 hash 與 data/processed/ 中記錄的 hash，
      只有不一致（檔案內容變動，或 processed 檔案不存在）時才重新清理 + chunk + embed + upsert。
    - Vector DB 中每個 chunk 的 id 為 "<source_file>::chunk_<index>"，使用 ChromaDB 的 upsert
      語意：同樣的 id 再次寫入會覆蓋舊資料，不會重複累積。
    - --rebuild 會先清空 data/processed/ 與整個 ChromaDB collection，確保 Vector DB 完整反映
      data/raw/ 的最新狀態，不殘留任何已刪除來源檔案的舊 chunk。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from rag_utils import (
    CHROMA_PERSIST_DIR_DEFAULT,
    PROCESSED_DIR,
    RAW_DIR,
    SUPPORTED_RAW_EXTENSIONS,
    chunk_text,
    clean_text,
    extract_text_from_file,
    file_sha256,
    get_chroma_collection,
    get_embedding_function,
    load_env,
)

HASH_COMMENT_PREFIX = "# source_hash: "


def relative_raw_path(raw_file: Path) -> str:
    """回傳相對於 data/raw/ 的路徑字串，例如 'langgraph/01_core_concepts.md'"""
    return str(raw_file.relative_to(RAW_DIR))


def processed_path_for(raw_file: Path) -> Path:
    """
    原始檔 -> 清理後 .txt 檔的路徑對應，保留子目錄結構。
    例如 data/raw/langgraph/01_core_concepts.md -> data/processed/langgraph/01_core_concepts.txt
    """
    rel = raw_file.relative_to(RAW_DIR)
    return (PROCESSED_DIR / rel).with_suffix(".txt")


def read_stored_hash(processed_file: Path) -> str | None:
    """讀取 processed .txt 檔案開頭記錄的 source hash（若存在）。"""
    if not processed_file.exists():
        return None
    with open(processed_file, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    if first_line.startswith(HASH_COMMENT_PREFIX):
        return first_line[len(HASH_COMMENT_PREFIX):].strip()
    return None


def read_processed_body(processed_file: Path) -> str:
    """讀取 processed .txt 檔案內容，跳過第一行的 hash 註解。"""
    with open(processed_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if lines and lines[0].strip().startswith(HASH_COMMENT_PREFIX):
        return "".join(lines[1:]).lstrip("\n")
    return "".join(lines)


def write_processed_file(processed_file: Path, source_hash: str, cleaned_text: str) -> None:
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    with open(processed_file, "w", encoding="utf-8") as f:
        f.write(f"{HASH_COMMENT_PREFIX}{source_hash}\n")
        f.write(cleaned_text)
        if not cleaned_text.endswith("\n"):
            f.write("\n")


def discover_raw_files() -> list[Path]:
    if not RAW_DIR.exists():
        return []
    files = [
        p for p in sorted(RAW_DIR.rglob("*"))
        if p.is_file() and p.suffix.lower() in SUPPORTED_RAW_EXTENSIONS
    ]
    return files


def find_orphaned_processed_files(raw_files: list[Path]) -> list[Path]:
    """找出 data/processed/ 中存在，但對應的原始檔已被刪除的 .txt 檔案。"""
    expected = {processed_path_for(f) for f in raw_files}
    if not PROCESSED_DIR.exists():
        return []
    existing = [p for p in PROCESSED_DIR.rglob("*.txt") if p.is_file()]
    return [p for p in existing if p not in expected]


def clean_and_chunk_step(rebuild: bool, dry_run: bool) -> dict[str, list]:
    """
    執行資料載入、清理、輸出至 data/processed/、Chunking。
    回傳 {"to_index": [(source_rel_path, [Chunk, ...]), ...], "skipped": [...], "removed": [...]}
    """
    raw_files = discover_raw_files()
    if not raw_files:
        print(f"⚠️  在 {RAW_DIR} 中找不到任何支援格式（{', '.join(sorted(SUPPORTED_RAW_EXTENSIONS))}）的檔案。")
        return {"to_index": [], "skipped": [], "removed": []}

    orphaned = find_orphaned_processed_files(raw_files)

    if rebuild:
        print(f"🔄 --rebuild：清空 {PROCESSED_DIR} 後重新處理全部 {len(raw_files)} 個原始檔案")
        if not dry_run and PROCESSED_DIR.exists():
            for f in PROCESSED_DIR.rglob("*.txt"):
                f.unlink()
        files_to_process = raw_files
        orphaned = []  # rebuild 後沒有殘留檔案的問題
    else:
        files_to_process = []
        for raw_file in raw_files:
            current_hash = file_sha256(raw_file)
            proc_path = processed_path_for(raw_file)
            stored_hash = read_stored_hash(proc_path)
            if stored_hash != current_hash:
                files_to_process.append(raw_file)

    to_index: list[tuple[str, list]] = []
    skipped: list[str] = []

    for raw_file in raw_files:
        rel = relative_raw_path(raw_file)
        proc_path = processed_path_for(raw_file)

        if raw_file in files_to_process:
            current_hash = file_sha256(raw_file)
            print(f"  📄 處理中: {rel}")
            if dry_run:
                to_index.append((rel, []))
                continue
            try:
                raw_text = extract_text_from_file(raw_file)
            except Exception as e:
                print(f"  ❌ 讀取失敗，略過: {rel} ({e})")
                continue
            cleaned = clean_text(raw_text)
            if not cleaned.strip():
                print(f"  ⚠️  清理後內容為空，略過: {rel}")
                continue
            write_processed_file(proc_path, current_hash, cleaned)
            chunks = chunk_text(cleaned, source_file=str(proc_path.relative_to(PROCESSED_DIR)))
            to_index.append((rel, chunks))
        else:
            skipped.append(rel)
            # 仍需要把既有 chunk 資訊準備好，因為即使檔案沒變，重啟流程時 collection 仍應保有該檔案資料
            # （此處不重新 embed，由 Vector DB 端的 upsert idempotency 保證舊資料已存在，不需動作）

    if orphaned and not dry_run:
        print(f"🗑️  偵測到 {len(orphaned)} 個孤兒 processed 檔案（原始檔已刪除），將一併清除：")
        for p in orphaned:
            print(f"    - {p.relative_to(PROCESSED_DIR)}")
            p.unlink()

    return {"to_index": to_index, "skipped": skipped, "removed": [str(p.relative_to(PROCESSED_DIR)) for p in orphaned]}


def embed_and_upsert_step(to_index: list[tuple[str, list]], rebuild: bool, dry_run: bool) -> int:
    """將 chunks embed 後 upsert 至 ChromaDB。回傳實際寫入的 chunk 數量。"""
    chunks_flat = [c for _, chunks in to_index for c in chunks]

    if not chunks_flat and not rebuild:
        print("✅ 沒有需要重新 embedding 的新內容。")
        return 0

    if dry_run:
        print(f"🧪 [dry-run] 會 embed 並寫入 {len(chunks_flat)} 個 chunks（不實際執行）")
        return len(chunks_flat)

    print("🧠 載入 Embedding 模型中（首次執行需從 HuggingFace 下載，請耐心等候）...")
    embedding_fn = get_embedding_function()
    client, collection = get_chroma_collection(embedding_fn=embedding_fn)

    if rebuild:
        print("🗑️  --rebuild：清空 Vector DB collection")
        try:
            client.delete_collection(collection.name)
        except Exception:
            pass
        client, collection = get_chroma_collection(embedding_fn=embedding_fn)
        # rebuild 模式下，需要對 *所有* processed 檔案重新 chunk + embed（即使前面只重新清理了部分）
        all_processed = sorted(PROCESSED_DIR.rglob("*.txt"))
        chunks_flat = []
        for p in all_processed:
            body = read_processed_body(p)
            rel_name = str(p.relative_to(PROCESSED_DIR))
            chunks_flat.extend(chunk_text(body, source_file=rel_name))

    if not chunks_flat:
        print("⚠️  沒有任何 chunk 可寫入 Vector DB。")
        return 0

    batch_size = 64
    total = 0
    for i in range(0, len(chunks_flat), batch_size):
        batch = chunks_flat[i : i + batch_size]
        ids = [f"{c.source_file}::chunk_{c.chunk_index}" for c in batch]
        documents = [c.text for c in batch]
        metadatas = [{"source_file": c.source_file, "chunk_index": c.chunk_index} for c in batch]
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        total += len(batch)
        print(f"  ✅ 已寫入 {total}/{len(chunks_flat)} chunks")

    return total


def main() -> int:
    parser = argparse.ArgumentParser(
        description="資料收集、清理、Chunking、Embedding 與 Vector DB 索引腳本（Build Your Personal RAG）"
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="全量重建：清空 data/processed/ 與 Vector DB，重新處理並索引 data/raw/ 中所有檔案"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="僅顯示將執行的動作，不實際寫入 data/processed/ 或 Vector DB"
    )
    args = parser.parse_args()

    load_env()

    start = time.time()
    print("=" * 70)
    print("📚 data_update.py — Personal RAG 資料索引流程")
    print(f"   模式: {'REBUILD（全量重建）' if args.rebuild else 'INCREMENTAL（增量更新）'}"
          f"{' [DRY-RUN]' if args.dry_run else ''}")
    print("=" * 70)

    print(f"\n[1/3] 掃描並清理 {RAW_DIR} 中的原始檔案 → 輸出至 {PROCESSED_DIR}")
    result = clean_and_chunk_step(rebuild=args.rebuild, dry_run=args.dry_run)

    n_changed = len(result["to_index"])
    n_skipped = len(result["skipped"])
    print(f"\n   變動/新增檔案: {n_changed}　|　未變動（略過）: {n_skipped}　|　已刪除: {len(result['removed'])}")

    if n_changed == 0 and not args.rebuild:
        print("\n✅ 所有檔案皆無變動，Vector DB 已是最新狀態，無需重新 embedding。")
        print(f"\n⏱️  耗時 {time.time() - start:.1f} 秒")
        return 0

    print(f"\n[2/3] Embedding + 寫入 Vector DB（ChromaDB，persist 至 {CHROMA_PERSIST_DIR_DEFAULT}）")
    n_written = embed_and_upsert_step(result["to_index"], rebuild=args.rebuild, dry_run=args.dry_run)

    print(f"\n[3/3] 完成")
    print(f"   共處理 {n_written} 個 chunks")
    print(f"\n⏱️  耗時 {time.time() - start:.1f} 秒")

    if args.dry_run:
        print("\n🧪 此為 dry-run，未實際修改任何檔案或資料庫。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
