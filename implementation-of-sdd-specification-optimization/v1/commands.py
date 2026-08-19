"""
CryptoTracker v1.0 - Command Handlers
各 CLI 指令的業務邏輯處理。
純邏輯層，透過 storage 與 api 模組進行資料操作。
"""

import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from crypto_api import CryptoAPIClient
from models import PriceRecord
from storage import StorageBackend
from utils import (
    analyze_trend,
    format_currency,
    format_percentage,
    format_table,
    format_trend_report,
)


class CommandHandler:
    """
    CLI 指令處理器。
    集中管理所有指令的業務邏輯，依賴注入 storage 與 api 模組。
    """

    def __init__(
        self,
        storage: Optional[StorageBackend] = None,
        api_client: Optional[CryptoAPIClient] = None,
    ):
        """
        初始化指令處理器。

        Args:
            storage: 資料存取後端，預設建立新的 StorageBackend
            api_client: API 客戶端，預設建立新的 CryptoAPIClient
        """
        self.storage = storage or StorageBackend()
        self.api = api_client or CryptoAPIClient()

    def cmd_price(self, coin: str, currency: str = "usd") -> None:
        """
        查詢指定幣種的即時價格。

        Args:
            coin: 幣種 ID
            currency: 法幣代碼
        """
        try:
            data = self.api.get_price(coin, currency)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except (ConnectionError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        # 嘗試取得幣種名稱
        try:
            name = self.api.get_coin_name(coin)
        except Exception:
            name = coin.capitalize()

        price = data["price"]
        change = data.get("change_24h", 0)

        print(f"\n  {name} ({coin.upper()})")
        print(f"  Price: {format_currency(price, currency)}")
        if change:
            print(f"  24h Change: {format_percentage(change)}")
        print()

        # 儲存查詢紀錄
        record = PriceRecord(
            id=0,
            coin_id=coin.lower(),
            price_usd=price if currency == "usd" else 0,
            metadata={"currency": currency, "price": price},
        )
        try:
            self.storage.save_price_record(record)
        except Exception:
            pass  # 儲存失敗不影響主功能

    def cmd_top(self, num: int = 10) -> None:
        """
        列出市值前 N 名的加密貨幣。

        Args:
            num: 要顯示的幣種數量
        """
        try:
            coins = self.api.get_top_coins(num)
        except (ConnectionError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        headers = ["Rank", "Name", "Symbol", "Price (USD)", "Market Cap", "24h Change"]
        rows = []
        for c in coins:
            rows.append([
                str(c.market_cap_rank),
                c.name,
                c.symbol,
                format_currency(c.current_price),
                format_currency(c.market_cap),
                format_percentage(c.price_change_percentage_24h),
            ])

        print(f"\n  Top {num} Cryptocurrencies by Market Cap\n")
        print(format_table(headers, rows))
        print()

    def cmd_favorite_add(self, coin: str) -> None:
        """
        將幣種加入收藏清單。

        Args:
            coin: 幣種 ID
        """
        # 先驗證幣種是否存在
        try:
            self.api.get_price(coin)
        except ValueError:
            print(f"Error: Coin '{coin}' not found", file=sys.stderr)
            sys.exit(1)
        except (ConnectionError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        try:
            fav = self.storage.add_favorite(coin)
            print(f"Added: {fav.coin_id}")
        except ValueError:
            print(f"Warning: Coin '{coin}' already in favorites")

    def cmd_favorite_remove(self, coin: str) -> None:
        """
        從收藏清單移除幣種。

        Args:
            coin: 幣種 ID
        """
        try:
            fav = self.storage.remove_favorite(coin)
            print(f"Removed: {fav.coin_id}")
        except ValueError:
            print(f"Error: Coin '{coin}' not in favorites", file=sys.stderr)
            sys.exit(1)

    def cmd_favorite_list(self) -> None:
        """列出所有收藏幣種及其即時價格。"""
        favorites = self.storage.get_all_favorites()
        if not favorites:
            print("\n  No favorites yet. Use 'favorite add --coin <name>' to add one.\n")
            return

        headers = ["ID", "Coin", "Price (USD)", "24h Change", "Added"]
        rows = []
        for fav in favorites:
            try:
                data = self.api.get_price(fav.coin_id)
                price_str = format_currency(data["price"])
                change_str = format_percentage(data.get("change_24h", 0))
            except Exception:
                price_str = "N/A"
                change_str = "N/A"

            rows.append([
                str(fav.id),
                fav.coin_id,
                price_str,
                change_str,
                fav.added_at[:10],
            ])

        print(f"\n  Your Favorites\n")
        print(format_table(headers, rows))
        print()

    def cmd_history(self, coin: str, days: int = 7) -> None:
        """
        查詢指定幣種過去 N 天的價格歷史。

        Args:
            coin: 幣種 ID
            days: 天數
        """
        if days <= 0:
            print("Error: Days must be a positive integer", file=sys.stderr)
            sys.exit(2)

        try:
            price_data = self.api.get_price_history(coin, days)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except (ConnectionError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        if not price_data:
            print(f"\n  No price history available for {coin}.\n")
            return

        headers = ["Date", "Price (USD)"]
        rows = [[p["date"], format_currency(p["price"])] for p in price_data]

        print(f"\n  Price History: {coin.upper()} (last {days} days)\n")
        print(format_table(headers, rows))
        print()

    def cmd_trend(self, coin: str, days: int = 30) -> None:
        """
        對指定幣種進行趨勢分析。

        Args:
            coin: 幣種 ID
            days: 分析天數
        """
        if days <= 0:
            print("Error: Days must be a positive integer", file=sys.stderr)
            sys.exit(2)

        try:
            price_data = self.api.get_price_history(coin, days)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except (ConnectionError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        if not price_data:
            print(f"\n  No price data available for {coin}.\n")
            return

        result = analyze_trend(coin, price_data, days)
        report = format_trend_report(result)
        print(report)

    def cmd_export(self, coin: str, days: int = 7, fmt: str = "csv") -> None:
        """
        匯出歷史資料為 CSV 或 JSON 檔案。

        Args:
            coin: 幣種 ID
            days: 天數
            fmt: 匯出格式（csv / json）
        """
        fmt = fmt.lower()
        if fmt not in ("csv", "json"):
            print(f"Error: Unsupported format '{fmt}'. Use csv or json", file=sys.stderr)
            sys.exit(2)

        if days <= 0:
            print("Error: Days must be a positive integer", file=sys.stderr)
            sys.exit(2)

        try:
            price_data = self.api.get_price_history(coin, days)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except (ConnectionError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        if not price_data:
            print(f"\n  No data to export for {coin}.\n")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{coin}_{days}d_{timestamp}.{fmt}"

        if fmt == "csv":
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["date", "price"])
                writer.writeheader()
                writer.writerows(price_data)
        elif fmt == "json":
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(price_data, f, indent=2, ensure_ascii=False)

        print(f"Exported: {filename} ({len(price_data)} records)")