"""
CryptoTracker v1.0 - Data Access Layer
封裝所有資料存取邏輯，使用 JSON 檔案作為儲存後端。
設計為可替換的抽象層，未來可替換為 SQLite 或其他資料庫。
"""

import json
import os
from pathlib import Path
from typing import Optional

from models import Favorite, PriceRecord


class StorageBackend:
    """
    資料存取抽象層。
    v1.0 使用 JSON 檔案儲存，但介面設計為可替換。
    所有讀寫操作透過此類進行，業務邏輯層不直接碰檔案系統。
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化儲存後端。

        Args:
            data_dir: 資料目錄路徑，預設為 ~/.cryptotracker/
        """
        if data_dir is None:
            self.data_dir = Path.home() / ".cryptotracker"
        else:
            self.data_dir = Path(data_dir)

        self._ensure_data_dir()

        self.favorites_file = self.data_dir / "favorites.json"
        self.history_file = self.data_dir / "price_history.json"
        self.config_file = self.data_dir / "config.json"

    def _ensure_data_dir(self) -> None:
        """確保資料目錄存在，若不存在則建立。"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Cannot create data directory: {e}")

    def _read_json(self, filepath: Path) -> list[dict]:
        """讀取 JSON 檔案，若不存在則回傳空列表。"""
        if not filepath.exists():
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []

    def _write_json(self, filepath: Path, data: list[dict]) -> None:
        """寫入 JSON 檔案。"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_next_id(self, items: list[dict]) -> int:
        """取得下一個自動遞增 ID。"""
        if not items:
            return 1
        return max(item.get("id", 0) for item in items) + 1

    # === Favorite 操作 ===

    def get_all_favorites(self) -> list[Favorite]:
        """取得所有收藏幣種。"""
        raw = self._read_json(self.favorites_file)
        return [Favorite.from_dict(item) for item in raw]

    def get_favorite_by_coin(self, coin_id: str) -> Optional[Favorite]:
        """根據幣種 ID 查詢收藏。"""
        favorites = self.get_all_favorites()
        for fav in favorites:
            if fav.coin_id == coin_id.lower():
                return fav
        return None

    def add_favorite(self, coin_id: str) -> Favorite:
        """
        新增收藏幣種。

        Args:
            coin_id: 幣種 ID

        Returns:
            新建立的 Favorite 物件

        Raises:
            ValueError: 若幣種已在收藏清單中
        """
        existing = self.get_favorite_by_coin(coin_id)
        if existing:
            raise ValueError(f"Coin '{coin_id}' already in favorites")

        raw = self._read_json(self.favorites_file)
        new_id = self._get_next_id(raw)
        favorite = Favorite(id=new_id, coin_id=coin_id.lower())
        raw.append(favorite.to_dict())
        self._write_json(self.favorites_file, raw)
        return favorite

    def remove_favorite(self, coin_id: str) -> Favorite:
        """
        移除收藏幣種。

        Args:
            coin_id: 幣種 ID

        Returns:
            被移除的 Favorite 物件

        Raises:
            ValueError: 若幣種不在收藏清單中
        """
        raw = self._read_json(self.favorites_file)
        target = None
        new_raw = []
        for item in raw:
            if item["coin_id"] == coin_id.lower():
                target = Favorite.from_dict(item)
            else:
                new_raw.append(item)

        if target is None:
            raise ValueError(f"Coin '{coin_id}' not in favorites")

        self._write_json(self.favorites_file, new_raw)
        return target

    # === PriceRecord 操作 ===

    def save_price_record(self, record: PriceRecord) -> PriceRecord:
        """儲存價格查詢紀錄。"""
        raw = self._read_json(self.history_file)
        if record.id == 0:
            record.id = self._get_next_id(raw)
        raw.append(record.to_dict())
        self._write_json(self.history_file, raw)
        return record

    def get_price_history(self, coin_id: str, limit: int = 100) -> list[PriceRecord]:
        """取得指定幣種的價格歷史紀錄。"""
        raw = self._read_json(self.history_file)
        records = [
            PriceRecord.from_dict(item)
            for item in raw
            if item["coin_id"] == coin_id.lower()
        ]
        return records[-limit:]

    # === 設定操作 ===

    def get_config(self) -> dict:
        """取得設定。"""
        if not self.config_file.exists():
            return {"default_currency": "usd", "version": "1.0"}
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"default_currency": "usd", "version": "1.0"}

    def save_config(self, config: dict) -> None:
        """儲存設定。"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)