"""
CryptoTracker v1.0 - API Client
封裝 CoinGecko Free API 呼叫邏輯。
設計為可替換的抽象介面，未來可替換為其他資料來源。
"""

import time
from typing import Optional

import requests

from models import CoinInfo


class CryptoAPIClient:
    """
    加密貨幣 API 客戶端。
    v1.0 使用 CoinGecko Free API 作為資料來源。
    介面設計為可替換，未來可替換為 CoinMarketCap、Binance 等。
    """

    BASE_URL = "https://api.coingecko.com/api/v3"
    REQUEST_TIMEOUT = 15
    RATE_LIMIT_DELAY = 1.5  # CoinGecko free API rate limit

    def __init__(self):
        """初始化 API 客戶端。"""
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "CryptoTracker/1.0",
        })
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """簡易 rate limiting，避免被 API 封鎖。"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        """
        發送 GET 請求至 CoinGecko API。

        Args:
            endpoint: API 端點路徑
            params: 查詢參數

        Returns:
            API 回傳的 JSON 資料

        Raises:
            ConnectionError: 網路連線失敗
            RuntimeError: API 回傳錯誤
        """
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
        """
        查詢指定幣種的即時價格。

        Args:
            coin_id: 幣種 ID（如 'bitcoin'）
            currency: 法幣代碼（如 'usd', 'twd'）

        Returns:
            包含價格資訊的字典

        Raises:
            ValueError: 幣種不存在
        """
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
        """
        取得市值前 N 名的加密貨幣。

        Args:
            num: 要取得的幣種數量
            currency: 法幣代碼

        Returns:
            CoinInfo 物件列表
        """
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
        """
        取得指定幣種的歷史價格。

        Args:
            coin_id: 幣種 ID
            days: 天數
            currency: 法幣代碼

        Returns:
            包含日期與價格的字典列表

        Raises:
            ValueError: 幣種不存在
        """
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
        """
        取得幣種的顯示名稱。

        Args:
            coin_id: 幣種 ID

        Returns:
            幣種名稱（如 'Bitcoin'）
        """
        data = self._get(f"/coins/{coin_id.lower()}", params={
            "localization": "false",
            "tickers": "false",
            "market_data": "false",
            "community_data": "false",
            "developer_data": "false",
        })
        return data.get("name", coin_id)