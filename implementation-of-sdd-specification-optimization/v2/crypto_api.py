"""
CryptoTracker v2.0 - API Client
封裝 CoinGecko Free API 呼叫邏輯。
v2.0 無介面變更，完全複用 v1.0 邏輯。
"""

import time
from typing import Optional

import requests

from models import CoinInfo


class CryptoAPIClient:
    """
    加密貨幣 API 客戶端。
    v1.0 使用 CoinGecko Free API 作為資料來源。
    v2.0 無變更。
    """

    BASE_URL = "https://api.coingecko.com/api/v3"
    REQUEST_TIMEOUT = 15
    RATE_LIMIT_DELAY = 1.5

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "CryptoTracker/2.0",
        })
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=self.REQUEST_TIMEOUT)
        except requests.ConnectionError as e:
            raise ConnectionError(f"Network error - {e}")
        except requests.Timeout:
            raise ConnectionError("Network error - Request timed out")
        except requests.RequestException as e:
            raise ConnectionError(f"Network error - {e}")

        if response.status_code == 429:
            raise RuntimeError("API error - Rate limit exceeded. Please wait and try again.")
        if response.status_code != 200:
            raise RuntimeError(f"API error - HTTP {response.status_code}: {response.text[:200]}")

        try:
            return response.json()
        except ValueError:
            raise RuntimeError("API error - Invalid JSON response")

    def get_price(self, coin_id: str, currency: str = "usd") -> dict:
        currency = currency.lower()
        data = self._get("/simple/price", params={
            "ids": coin_id.lower(),
            "vs_currencies": currency,
            "include_24hr_change": "true",
            "include_market_cap": "true",
        })

        if coin_id.lower() not in data or not data[coin_id.lower()]:
            raise ValueError(f"Coin '{coin_id}' not found")

        coin_data = data[coin_id.lower()]
        return {
            "coin_id": coin_id.lower(),
            "currency": currency,
            "price": coin_data.get(currency, 0),
            "market_cap": coin_data.get(f"{currency}_market_cap", 0),
            "change_24h": coin_data.get(f"{currency}_24h_change", 0),
        }

    def get_top_coins(self, num: int = 10, currency: str = "usd") -> list[CoinInfo]:
        data = self._get("/coins/markets", params={
            "vs_currency": currency.lower(),
            "order": "market_cap_desc",
            "per_page": min(num, 250),
            "page": 1,
            "sparkline": "false",
        })

        coins = []
        for item in data[:num]:
            coins.append(CoinInfo(
                coin_id=item["id"],
                symbol=item["symbol"].upper(),
                name=item["name"],
                current_price=item.get("current_price", 0) or 0,
                market_cap=item.get("market_cap", 0) or 0,
                market_cap_rank=item.get("market_cap_rank", 0) or 0,
                price_change_24h=item.get("price_change_24h", 0) or 0,
                price_change_percentage_24h=item.get("price_change_percentage_24h", 0) or 0,
            ))
        return coins

    def get_price_history(self, coin_id: str, days: int, currency: str = "usd") -> list[dict]:
        try:
            data = self._get(f"/coins/{coin_id.lower()}/market_chart", params={
                "vs_currency": currency.lower(),
                "days": str(days),
                "interval": "daily",
            })
        except RuntimeError as e:
            if "404" in str(e):
                raise ValueError(f"Coin '{coin_id}' not found")
            raise

        prices = data.get("prices", [])
        result = []
        for timestamp_ms, price in prices:
            date_str = time.strftime("%Y-%m-%d", time.gmtime(timestamp_ms / 1000))
            result.append({
                "date": date_str,
                "price": round(price, 2),
            })
        return result

    def get_coin_name(self, coin_id: str) -> str:
        data = self._get(f"/coins/{coin_id.lower()}", params={
            "localization": "false",
            "tickers": "false",
            "market_data": "false",
            "community_data": "false",
            "developer_data": "false",
        })
        return data.get("name", coin_id)