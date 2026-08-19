"""
CryptoTracker v2.0 - Command Handlers
各 CLI 指令的業務邏輯處理。
v2.0 新增：config、alert、compare 指令處理；
所有涉及價格的指令加入警示檢查。
"""

import csv
import json
import sys
from datetime import datetime
from typing import Optional

from crypto_api import CryptoAPIClient
from models import PriceRecord
from storage import StorageBackend
from utils import (
    analyze_trend,
    calculate_rsi,
    check_alerts,
    format_alert_warnings,
    format_currency,
    format_percentage,
    format_table,
    format_trend_report,
    generate_trend_summary,
)


class CommandHandler:
    """
    CLI 指令處理器。
    v2.0：新增 config / alert / compare 指令處理，
    所有涉及價格查詢的指令在輸出後自動檢查警示。
    """

    def __init__(
        self,
        storage: Optional[StorageBackend] = None,
        api_client: Optional[CryptoAPIClient] = None,
    ):
        self.storage = storage or StorageBackend()
        self.api = api_client or CryptoAPIClient()

    def _get_effective_currency(self, cli_currency: Optional[str] = None) -> str:
        """
        取得有效的法幣代碼（v2.0：設定優先順序）。
        指令列參數 > config 設定 > 預設值 "usd"
        """
        if cli_currency is not None:
            return cli_currency.lower()
        config = self.storage.get_config()
        return config.get("default_currency", "usd").lower()

    def _get_effective_top_num(self, cli_num: Optional[int] = None) -> int:
        """
        取得有效的 top 筆數（v2.0：設定優先順序）。
        """
        if cli_num is not None:
            return cli_num
        config = self.storage.get_config()
        return config.get("default_top_num", 10)

    def _check_and_display_alerts(self, known_prices: Optional[dict] = None) -> None:
        """
        檢查並顯示已觸發的價格警示（v2.0 新增）。
        此方法在每個涉及價格的指令結尾呼叫。
        若檢查過程中發生任何錯誤，靜默忽略，不影響主指令。
        """
        try:
            alerts = self.storage.get_all_alerts()
            if not alerts:
                return

            prices = dict(known_prices) if known_prices else {}

            # 對尚未取得價格的幣種進行查詢
            missing_coins = set()
            for alert in alerts:
                if alert.coin_id not in prices:
                    missing_coins.add(alert.coin_id)

            for coin_id in missing_coins:
                try:
                    data = self.api.get_price(coin_id, alert.currency if alerts else "usd")
                    prices[coin_id] = data["price"]
                except Exception:
                    pass

            triggered = check_alerts(alerts, prices)
            if triggered:
                warning = format_alert_warnings(triggered)
                print(warning)
        except Exception:
            pass  # 警示檢查失敗不影響主功能

    # ============================================================
    # v1.0 保留指令（含 v2.0 增強）
    # ============================================================

    def cmd_price(self, coin: str, currency: str = None) -> None:
        """查詢指定幣種的即時價格。v2.0：支援設定檔預設法幣 + 警示檢查。"""
        effective_currency = self._get_effective_currency(currency)

        try:
            data = self.api.get_price(coin, effective_currency)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except (ConnectionError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        try:
            name = self.api.get_coin_name(coin)
        except Exception:
            name = coin.capitalize()

        price = data["price"]
        change = data.get("change_24h", 0)

        print(f"\n  {name} ({coin.upper()})")
        print(f"  Price: {format_currency(price, effective_currency)}")
        if change:
            print(f"  24h Change: {format_percentage(change)}")
        print()

        # 儲存查詢紀錄
        record = PriceRecord(
            id=0,
            coin_id=coin.lower(),
            price_usd=price if effective_currency == "usd" else 0,
            metadata={"currency": effective_currency, "price": price},
        )
        try:
            self.storage.save_price_record(record)
        except Exception:
            pass

        # v2.0: 檢查警示
        self._check_and_display_alerts({coin.lower(): price})

    def cmd_top(self, num: int = None) -> None:
        """列出市值前 N 名的加密貨幣。v2.0：支援設定檔預設筆數。"""
        effective_num = self._get_effective_top_num(num)

        try:
            coins = self.api.get_top_coins(effective_num)
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

        print(f"\n  Top {effective_num} Cryptocurrencies by Market Cap\n")
        print(format_table(headers, rows))
        print()

        # v2.0: 檢查警示
        known = {c.coin_id: c.current_price for c in coins}
        self._check_and_display_alerts(known)

    def cmd_favorite_add(self, coin: str) -> None:
        """將幣種加入收藏清單。（v1.0 行為不變）"""
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
        """從收藏清單移除幣種。（v1.0 行為不變）"""
        try:
            fav = self.storage.remove_favorite(coin)
            print(f"Removed: {fav.coin_id}")
        except ValueError:
            print(f"Error: Coin '{coin}' not in favorites", file=sys.stderr)
            sys.exit(1)

    def cmd_favorite_list(self) -> None:
        """列出所有收藏幣種及其即時價格。v2.0：結尾加入警示檢查。"""
        favorites = self.storage.get_all_favorites()
        if not favorites:
            print("\n  No favorites yet. Use 'favorite add --coin <name>' to add one.\n")
            return

        effective_currency = self._get_effective_currency()

        headers = ["ID", "Coin", f"Price ({effective_currency.upper()})", "24h Change", "Added"]
        rows = []
        known_prices = {}
        for fav in favorites:
            try:
                data = self.api.get_price(fav.coin_id, effective_currency)
                price_str = format_currency(data["price"], effective_currency)
                change_str = format_percentage(data.get("change_24h", 0))
                known_prices[fav.coin_id] = data["price"]
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

        # v2.0: 檢查警示
        self._check_and_display_alerts(known_prices)

    def cmd_history(self, coin: str, days: int = 7) -> None:
        """查詢指定幣種過去 N 天的價格歷史。（v1.0 行為不變）"""
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

        # v2.0: 檢查警示
        if price_data:
            self._check_and_display_alerts({coin.lower(): price_data[-1]["price"]})

    def cmd_trend(self, coin: str, days: int = 30) -> None:
        """趨勢分析。v2.0：新增 RSI + 自然語言摘要。"""
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
        # v2.0: 生成自然語言摘要
        summary = generate_trend_summary(result)
        report = format_trend_report(result, summary)
        print(report)

        # v2.0: 檢查警示
        self._check_and_display_alerts({coin.lower(): result.current_price})

    def cmd_export(self, coin: str, days: int = 7, fmt: str = "csv") -> None:
        """匯出歷史資料。（v1.0 行為不變）"""
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

    # ============================================================
    # v2.0 新增指令
    # ============================================================

    def cmd_config_get(self) -> None:
        """顯示目前所有設定值。"""
        config = self.storage.get_config()
        print(f"\n  CryptoTracker Configuration\n")
        headers = ["Setting", "Value"]
        rows = []
        for key, value in sorted(config.items()):
            display_key = key.replace("_", " ").title()
            rows.append([display_key, str(value)])
        print(format_table(headers, rows))
        print()

    def cmd_config_set(self, currency: Optional[str] = None,
                       top_num: Optional[int] = None) -> None:
        """設定個人偏好。"""
        config = self.storage.get_config()
        changed = False

        if currency is not None:
            config["default_currency"] = currency.lower()
            changed = True
        if top_num is not None:
            config["default_top_num"] = top_num
            changed = True

        if not changed:
            print("Error: No valid config option provided", file=sys.stderr)
            sys.exit(2)

        self.storage.save_config(config)
        print(f"\n  Configuration updated:")
        if currency is not None:
            print(f"    default_currency = {currency.lower()}")
        if top_num is not None:
            print(f"    default_top_num = {top_num}")
        print()

    def cmd_config_reset(self) -> None:
        """重設所有設定為預設值。"""
        config = self.storage.reset_config()
        print(f"\n  Configuration reset to defaults:")
        for key, value in sorted(config.items()):
            print(f"    {key} = {value}")
        print()

    def cmd_alert_add(self, coin: str, above: Optional[float] = None,
                      below: Optional[float] = None) -> None:
        """新增價格警示。"""
        if above is None and below is None:
            print("Error: Must specify --above or --below threshold", file=sys.stderr)
            sys.exit(2)

        # 驗證幣種存在
        try:
            self.api.get_price(coin)
        except ValueError:
            print(f"Error: Coin '{coin}' not found", file=sys.stderr)
            sys.exit(1)
        except (ConnectionError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)

        effective_currency = self._get_effective_currency()

        if above is not None:
            alert = self.storage.add_alert(coin, "above", above, effective_currency)
            print(f"Alert added: [{alert.id}] {alert.coin_id} price > "
                  f"{format_currency(above, effective_currency)}")
        if below is not None:
            alert = self.storage.add_alert(coin, "below", below, effective_currency)
            print(f"Alert added: [{alert.id}] {alert.coin_id} price < "
                  f"{format_currency(below, effective_currency)}")

    def cmd_alert_remove(self, alert_id: int) -> None:
        """移除指定 ID 的警示。"""
        try:
            alert = self.storage.remove_alert(alert_id)
            print(f"Removed alert [{alert.id}]: {alert.describe()}")
        except ValueError:
            print(f"Error: Alert ID {alert_id} not found", file=sys.stderr)
            sys.exit(1)

    def cmd_alert_list(self) -> None:
        """列出所有警示規則。"""
        alerts = self.storage.get_all_alerts()
        if not alerts:
            print("\n  No alerts set. Use 'alert add --coin <name> --above/--below <price>' to add one.\n")
            return

        headers = ["ID", "Coin", "Condition", "Threshold", "Currency", "Created"]
        rows = []
        for a in alerts:
            rows.append([
                str(a.id),
                a.coin_id,
                a.condition.upper(),
                format_currency(a.threshold, a.currency),
                a.currency.upper(),
                a.created_at[:10],
            ])

        print(f"\n  Price Alerts\n")
        print(format_table(headers, rows))
        print()

    def cmd_compare(self, coins_str: str, days: int = 7) -> None:
        """多幣種橫向比較。"""
        coins = [c.strip().lower() for c in coins_str.split(",") if c.strip()]
        if not coins:
            print("Error: Must specify at least one coin", file=sys.stderr)
            sys.exit(2)

        effective_currency = self._get_effective_currency()

        headers = ["Coin", f"Price ({effective_currency.upper()})",
                    f"Change ({days}d)", "24h Change"]
        rows = []
        known_prices = {}

        for coin_id in coins:
            # 取得即時價格
            try:
                price_data = self.api.get_price(coin_id, effective_currency)
                current_price = price_data["price"]
                change_24h = price_data.get("change_24h", 0)
                known_prices[coin_id] = current_price
            except ValueError:
                rows.append([coin_id, "Not Found", "N/A", "N/A"])
                continue
            except (ConnectionError, RuntimeError) as e:
                rows.append([coin_id, "API Error", "N/A", "N/A"])
                continue

            # 取得歷史價格以計算漲跌幅
            try:
                history = self.api.get_price_history(coin_id, days, effective_currency)
                if history and history[0]["price"] != 0:
                    period_change = ((current_price - history[0]["price"])
                                     / history[0]["price"]) * 100
                    period_change_str = format_percentage(period_change)
                else:
                    period_change_str = "N/A"
            except Exception:
                period_change_str = "N/A"

            rows.append([
                coin_id,
                format_currency(current_price, effective_currency),
                period_change_str,
                format_percentage(change_24h) if change_24h else "N/A",
            ])

        print(f"\n  Coin Comparison ({days}-day period)\n")
        print(format_table(headers, rows))
        print()

        # v2.0: 檢查警示
        self._check_and_display_alerts(known_prices)