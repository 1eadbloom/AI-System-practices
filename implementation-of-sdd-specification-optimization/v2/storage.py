"""
CryptoTracker v2.0 - Data Access Layer
封裝所有資料存取邏輯，使用 JSON 檔案作為儲存後端。
v2.0 新增：Alert CRUD、Config 啟用讀寫。
"""

import json
from pathlib import Path
from typing import Optional

from models import Favorite, PriceRecord, Alert


DEFAULT_CONFIG = {
    "default_currency": "usd",
    "default_top_num": 10,
    "version": "2.0",
}


class StorageBackend:
    """
    資料存取抽象層。
    v1.0 使用 JSON 檔案儲存，v2.0 新增 Alert 與 Config 操作。
    """

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            self.data_dir = Path.home() / ".cryptotracker"
        else:
            self.data_dir = Path(data_dir)

        self._ensure_data_dir()

        self.favorites_file = self.data_dir / "favorites.json"
        self.history_file = self.data_dir / "price_history.json"
        self.config_file = self.data_dir / "config.json"
        self.alerts_file = self.data_dir / "alerts.json"  # v2.0 新增

    def _ensure_data_dir(self) -> None:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Cannot create data directory: {e}")

    def _read_json(self, filepath: Path) -> list[dict]:
        if not filepath.exists():
            return []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            return []

    def _write_json(self, filepath: Path, data: list[dict]) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_next_id(self, items: list[dict]) -> int:
        if not items:
            return 1
        return max(item.get("id", 0) for item in items) + 1

    # === Favorite 操作（v1.0 保留，無變更） ===

    def get_all_favorites(self) -> list[Favorite]:
        raw = self._read_json(self.favorites_file)
        return [Favorite.from_dict(item) for item in raw]

    def get_favorite_by_coin(self, coin_id: str) -> Optional[Favorite]:
        favorites = self.get_all_favorites()
        for fav in favorites:
            if fav.coin_id == coin_id.lower():
                return fav
        return None

    def add_favorite(self, coin_id: str) -> Favorite:
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

    # === PriceRecord 操作（v1.0 保留，無變更） ===

    def save_price_record(self, record: PriceRecord) -> PriceRecord:
        raw = self._read_json(self.history_file)
        if record.id == 0:
            record.id = self._get_next_id(raw)
        raw.append(record.to_dict())
        self._write_json(self.history_file, raw)
        return record

    def get_price_history(self, coin_id: str, limit: int = 100) -> list[PriceRecord]:
        raw = self._read_json(self.history_file)
        records = [
            PriceRecord.from_dict(item)
            for item in raw
            if item["coin_id"] == coin_id.lower()
        ]
        return records[-limit:]

    # === Config 操作（v2.0 啟用） ===

    def get_config(self) -> dict:
        """取得設定，若不存在則回傳預設值。"""
        if not self.config_file.exists():
            return dict(DEFAULT_CONFIG)
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                # 合併預設值，確保新增的設定項有預設值
                config = dict(DEFAULT_CONFIG)
                config.update(saved)
                return config
        except (json.JSONDecodeError, IOError):
            return dict(DEFAULT_CONFIG)

    def save_config(self, config: dict) -> None:
        """儲存設定。"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def reset_config(self) -> dict:
        """重設設定為預設值。"""
        config = dict(DEFAULT_CONFIG)
        self.save_config(config)
        return config

    # === Alert 操作（v2.0 新增） ===

    def get_all_alerts(self) -> list[Alert]:
        """取得所有警示規則。"""
        raw = self._read_json(self.alerts_file)
        return [Alert.from_dict(item) for item in raw]

    def get_alert_by_id(self, alert_id: int) -> Optional[Alert]:
        """根據 ID 查詢警示。"""
        alerts = self.get_all_alerts()
        for alert in alerts:
            if alert.id == alert_id:
                return alert
        return None

    def add_alert(self, coin_id: str, condition: str, threshold: float,
                  currency: str = "usd") -> Alert:
        """新增警示規則。"""
        raw = self._read_json(self.alerts_file)
        new_id = self._get_next_id(raw)
        alert = Alert(
            id=new_id,
            coin_id=coin_id.lower(),
            condition=condition,
            threshold=threshold,
            currency=currency.lower(),
        )
        raw.append(alert.to_dict())
        self._write_json(self.alerts_file, raw)
        return alert

    def remove_alert(self, alert_id: int) -> Alert:
        """移除指定 ID 的警示。"""
        raw = self._read_json(self.alerts_file)
        target = None
        new_raw = []
        for item in raw:
            if item["id"] == alert_id:
                target = Alert.from_dict(item)
            else:
                new_raw.append(item)

        if target is None:
            raise ValueError(f"Alert ID {alert_id} not found")

        self._write_json(self.alerts_file, new_raw)
        return target