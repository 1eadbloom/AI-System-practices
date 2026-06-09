"""持久層：把記憶存成 JSON 檔，重啟後讀得回來，並用 id 去重。"""
from __future__ import annotations
import json
import os


class JsonStore:
    def __init__(self, path: str):
        self.path = path
        self.items: list[dict] = []
        self.load()

    def load(self) -> None:
        """從硬碟讀回 self.items。
        檔案不存在、解析失敗、或內容不是 list（例如 {}）都一律視為空 list。"""
        if not os.path.exists(self.path):
            self.items = []
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.items = data
            else:
                self.items = []
        except Exception:
            self.items = []

    def _persist(self) -> None:
        """把 self.items 寫回硬碟（JSON）。"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

    def add(self, obs: dict) -> bool:
        """新增一筆；id 已存在則跳過，回傳是否真的新增。新增後要 _persist()。"""
        if any(o["id"] == obs["id"] for o in self.items):
            return False
        self.items.append(obs)
        self._persist()
        return True

    def all(self) -> list[dict]:
        return list(self.items)

    def clear(self) -> None:
        self.items = []
        self._persist()
