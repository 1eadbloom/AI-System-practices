```python
"""
CryptoTracker v1.0 - Data Models
定義核心資料結構，使用 dataclass 實現。
預留 metadata 欄位供未來版本擴充。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Favorite:
    """收藏幣種的資料模型。"""
    id: int
    coin_id: str
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化為字典，便於 JSON 儲存。"""
        return {
            "id": self.id,
            "coin_id": self.coin_id,
            "added_at": self.added_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Favorite":
        """從字典反序列化為 Favorite 物件。"""
        return cls(
            id=data["id"],
            coin_id=data["coin_id"],
            added_at=data.get("added_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PriceRecord:
    """價格查詢紀錄的資料模型。"""
    id: int
    coin_id: str
    price_usd: float
    queried_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化為字典，便於 JSON 儲存。"""
        return {
            "id": self.id,
            "coin_id": self.coin_id,
            "price_usd": self.price_usd,
            "queried_at": self.queried_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PriceRecord":
        """從字典反序列化為 PriceRecord 物件。"""
        return cls(
            id=data["id"],
            coin_id=data["coin_id"],
            price_usd=data["price_usd"],
            queried_at=data.get("queried_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CoinInfo:
    """幣種基本資訊（來自 API 回傳）。"""
    coin_id: str
    symbol: str
    name: str
    current_price: float
    market_cap: float
    market_cap_rank: int
    price_change_24h: float
    price_change_percentage_24h: float

    def to_dict(self) -> dict:
        """序列化為字典。"""
        return {
            "coin_id": self.coin_id,
            "symbol": self.symbol,
            "name": self.name,
            "current_price": self.current_price,
            "market_cap": self.market_cap,
            "market_cap_rank": self.market_cap_rank,
            "price_change_24h": self.price_change_24h,
            "price_change_percentage_24h": self.price_change_percentage_24h,
        }


@dataclass
class TrendResult:
    """趨勢分析結果。"""
    coin_id: str
    days: int
    current_price: float
    sma_short: float  # 短期移動平均
    sma_long: float   # 長期移動平均
    trend_direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    price_change_pct: float  # 期間內價格變動百分比
    volatility: float  # 價格波動率
    high: float
    low: float
    metadata: dict[str, Any] = field(default_factory=dict)