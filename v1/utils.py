"""
CryptoTracker v1.0 - Utility Functions
格式化輸出與趨勢分析演算法。
獨立於業務邏輯，可單獨測試與替換。
"""

import statistics
from typing import Optional

from models import TrendResult


def format_currency(value: float, currency: str = "usd") -> str:
    """
    格式化貨幣顯示。

    Args:
        value: 金額
        currency: 法幣代碼

    Returns:
        格式化後的字串
    """
    symbols = {
        "usd": "$",
        "twd": "NT$",
        "eur": "€",
        "jpy": "¥",
        "gbp": "£",
    }
    symbol = symbols.get(currency.lower(), currency.upper() + " ")

    if abs(value) >= 1_000_000_000:
        return f"{symbol}{value / 1_000_000_000:,.2f}B"
    elif abs(value) >= 1_000_000:
        return f"{symbol}{value / 1_000_000:,.2f}M"
    elif abs(value) >= 1:
        return f"{symbol}{value:,.2f}"
    else:
        return f"{symbol}{value:.6f}"


def format_percentage(value: float) -> str:
    """格式化百分比顯示，含正負號與顏色提示符號。"""
    if value > 0:
        return f"▲ +{value:.2f}%"
    elif value < 0:
        return f"▼ {value:.2f}%"
    else:
        return f"  {value:.2f}%"


def format_table(headers: list[str], rows: list[list[str]], min_widths: Optional[list[int]] = None) -> str:
    """
    格式化為對齊的文字表格。

    Args:
        headers: 標題列
        rows: 資料列
        min_widths: 各欄位的最小寬度

    Returns:
        格式化後的表格字串
    """
    if not rows:
        return "(No data)"

    col_count = len(headers)
    widths = [len(h) for h in headers]

    if min_widths:
        for i in range(min(len(min_widths), col_count)):
            widths[i] = max(widths[i], min_widths[i])

    for row in rows:
        for i in range(min(len(row), col_count)):
            widths[i] = max(widths[i], len(str(row[i])))

    # 建構表格
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * widths[i] for i in range(col_count))

    lines = [header_line, separator]
    for row in rows:
        line = " | ".join(str(row[i]).ljust(widths[i]) if i < len(row) else " " * widths[i]
                          for i in range(col_count))
        lines.append(line)

    return "\n".join(lines)


def calculate_sma(prices: list[float], window: int) -> Optional[float]:
    """
    計算簡單移動平均線（SMA）。

    Args:
        prices: 價格序列
        window: 窗口大小

    Returns:
        SMA 值，若資料不足則回傳 None
    """
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window


def calculate_volatility(prices: list[float]) -> float:
    """
    計算價格波動率（標準差 / 平均值）。

    Args:
        prices: 價格序列

    Returns:
        波動率百分比
    """
    if len(prices) < 2:
        return 0.0
    mean = statistics.mean(prices)
    if mean == 0:
        return 0.0
    stdev = statistics.stdev(prices)
    return (stdev / mean) * 100


def analyze_trend(coin_id: str, price_data: list[dict], days: int) -> TrendResult:
    """
    對價格資料進行趨勢分析。

    使用雙移動平均線交叉策略：
    - 短期 SMA（7 天或資料量的 1/4）
    - 長期 SMA（21 天或資料量的 3/4）
    - 短期 > 長期 → BULLISH（看漲）
    - 短期 < 長期 → BEARISH（看跌）
    - 差距 < 1% → NEUTRAL（中性）

    Args:
        coin_id: 幣種 ID
        price_data: 包含 date 和 price 的字典列表
        days: 分析天數

    Returns:
        TrendResult 物件
    """
    prices = [p["price"] for p in price_data]

    if not prices:
        return TrendResult(
            coin_id=coin_id, days=days, current_price=0,
            sma_short=0, sma_long=0, trend_direction="NEUTRAL",
            price_change_pct=0, volatility=0, high=0, low=0,
        )

    current_price = prices[-1]
    high = max(prices)
    low = min(prices)

    # 動態計算 SMA 窗口大小
    short_window = max(3, min(7, len(prices) // 4))
    long_window = max(7, min(21, len(prices) * 3 // 4))

    sma_short = calculate_sma(prices, short_window) or current_price
    sma_long = calculate_sma(prices, long_window) or current_price

    # 判斷趨勢方向
    if sma_long == 0:
        trend_direction = "NEUTRAL"
    else:
        diff_pct = ((sma_short - sma_long) / sma_long) * 100
        if diff_pct > 1:
            trend_direction = "BULLISH"
        elif diff_pct < -1:
            trend_direction = "BEARISH"
        else:
            trend_direction = "NEUTRAL"

    # 計算期間價格變動百分比
    if prices[0] != 0:
        price_change_pct = ((current_price - prices[0]) / prices[0]) * 100
    else:
        price_change_pct = 0

    volatility = calculate_volatility(prices)

    return TrendResult(
        coin_id=coin_id,
        days=days,
        current_price=current_price,
        sma_short=round(sma_short, 2),
        sma_long=round(sma_long, 2),
        trend_direction=trend_direction,
        price_change_pct=round(price_change_pct, 2),
        volatility=round(volatility, 2),
        high=high,
        low=low,
    )


def format_trend_report(result: TrendResult) -> str:
    """
    格式化趨勢分析報告。

    Args:
        result: TrendResult 物件

    Returns:
        格式化後的報告字串
    """
    direction_symbol = {
        "BULLISH": "📈 BULLISH (看漲)",
        "BEARISH": "📉 BEARISH (看跌)",
        "NEUTRAL": "➡️  NEUTRAL (中性)",
    }

    lines = [
        f"",
        f"═══ Trend Analysis: {result.coin_id.upper()} ({result.days} days) ═══",
        f"",
        f"  Current Price:  {format_currency(result.current_price)}",
        f"  Period High:    {format_currency(result.high)}",
        f"  Period Low:     {format_currency(result.low)}",
        f"  SMA (short):    {format_currency(result.sma_short)}",
        f"  SMA (long):     {format_currency(result.sma_long)}",
        f"  Price Change:   {format_percentage(result.price_change_pct)}",
        f"  Volatility:     {result.volatility:.2f}%",
        f"",
        f"  Trend: {direction_symbol.get(result.trend_direction, result.trend_direction)}",
        f"",
        f"{'═' * 50}",
    ]
    return "\n".join(lines)