
---

## 2. `v2/models.py`

```python
"""
CryptoTracker v2.0 - Data Models
定義核心資料結構，使用 dataclass 實現。
v2.0 新增 Alert 資料模型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Favorite:
    """收藏幣種的資料模型。（v1.0 保留，無變更）"""
    id: int
    coin_id: str
    added_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "coin_id": self.coin_id,
            "added_at": self.added_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Favorite":
        return cls(
            id=data["id"],
            coin_id=data["coin_id"],
            added_at=data.get("added_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PriceRecord:
    """價格查詢紀錄的資料模型。（v1.0 保留，無變更）"""
    id: int
    coin_id: str
    price_usd: float
    queried_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "coin_id": self.coin_id,
            "price_usd": self.price_usd,
            "queried_at": self.queried_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PriceRecord":
        return cls(
            id=data["id"],
            coin_id=data["coin_id"],
            price_usd=data["price_usd"],
            queried_at=data.get("queried_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CoinInfo:
    """幣種基本資訊（來自 API 回傳）。（v1.0 保留，無變更）"""
    coin_id: str
    symbol: str
    name: str
    current_price: float
    market_cap: float
    market_cap_rank: int
    price_change_24h: float
    price_change_percentage_24h: float

    def to_dict(self) -> dict:
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
    """趨勢分析結果。v2.0 新增 rsi 欄位。"""
    coin_id: str
    days: int
    current_price: float
    sma_short: float
    sma_long: float
    trend_direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    price_change_pct: float
    volatility: float
    high: float
    low: float
    rsi: float = 50.0  # v2.0 新增：RSI 指標，預設 50（中性）
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """價格警示規則。（v2.0 新增）"""
    id: int
    coin_id: str
    condition: str  # "above" 或 "below"
    threshold: float
    currency: str = "usd"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "coin_id": self.coin_id,
            "condition": self.condition,
            "threshold": self.threshold,
            "currency": self.currency,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        return cls(
            id=data["id"],
            coin_id=data["coin_id"],
            condition=data["condition"],
            threshold=data["threshold"],
            currency=data.get("currency", "usd"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )

    def describe(self) -> str:
        """人類可讀的警示描述。"""
        op = ">" if self.condition == "above" else "<"
        return f"{self.coin_id} {op} {self.threshold} {self.currency.upper()}"