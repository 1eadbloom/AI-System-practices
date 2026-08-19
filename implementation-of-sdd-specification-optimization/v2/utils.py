"""
CryptoTracker v2.0 - Utility Functions
格式化輸出與趨勢分析演算法。
v2.0 新增：RSI 計算、自然語言趨勢摘要生成、警示格式化。
"""

import statistics
from typing import Optional

from models import TrendResult, Alert


# ============================================================
# v1.0 保留函式（無變更）
# ============================================================

def format_currency(value: float, currency: str = "usd") -> str:
    """格式化貨幣顯示。"""
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


def format_table(headers: list[str], rows: list[list[str]],
                 min_widths: Optional[list[int]] = None) -> str:
    """格式化為對齊的文字表格。"""
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

    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    separator = "-+-".join("-" * widths[i] for i in range(col_count))

    lines = [header_line, separator]
    for row in rows:
        line = " | ".join(
            str(row[i]).ljust(widths[i]) if i < len(row) else " " * widths[i]
            for i in range(col_count)
        )
        lines.append(line)

    return "\n".join(lines)


def calculate_sma(prices: list[float], window: int) -> Optional[float]:
    """計算簡單移動平均線（SMA）。"""
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window


def calculate_volatility(prices: list[float]) -> float:
    """計算價格波動率（標準差 / 平均值）。"""
    if len(prices) < 2:
        return 0.0
    mean = statistics.mean(prices)
    if mean == 0:
        return 0.0
    stdev = statistics.stdev(prices)
    return (stdev / mean) * 100


# ============================================================
# v2.0 新增函式
# ============================================================

def calculate_rsi(prices: list[float], period: int = 14) -> float:
    """
    計算相對強弱指標（RSI）。

    RSI = 100 - (100 / (1 + RS))
    RS = 平均漲幅 / 平均跌幅

    Args:
        prices: 價格序列
        period: RSI 計算週期（預設 14）

    Returns:
        RSI 值（0-100），若資料不足則回傳 50.0（中性）
    """
    if len(prices) < period + 1:
        return 50.0

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent_changes = changes[-(period):]

    gains = [c for c in recent_changes if c > 0]
    losses = [-c for c in recent_changes if c < 0]

    avg_gain = sum(gains) / period if gains else 0.0
    avg_loss = sum(losses) / period if losses else 0.0

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def generate_trend_summary(result: TrendResult) -> str:
    """
    根據趨勢分析結果生成自然語言文字摘要。

    此函式為純邏輯函式，不涉及任何 I/O，可單獨測試。

    Args:
        result: TrendResult 物件

    Returns:
        自然語言摘要字串
    """
    coin = result.coin_id.upper()
    days = result.days
    parts = []

    # 整體趨勢描述
    if result.trend_direction == "BULLISH":
        parts.append(f"{coin} 近 {days} 天呈現上升趨勢，短期均線位於長期均線上方。")
    elif result.trend_direction == "BEARISH":
        parts.append(f"{coin} 近 {days} 天呈現下降趨勢，短期均線位於長期均線下方。")
    else:
        parts.append(f"{coin} 近 {days} 天呈現震盪整理，短期與長期均線接近。")

    # 價格變動描述
    pct = result.price_change_pct
    if abs(pct) < 1:
        parts.append(f"期間內價格變動幅度極小（{pct:+.2f}%），市場處於盤整狀態。")
    elif pct > 10:
        parts.append(f"期間內價格大幅上漲 {pct:+.2f}%，顯示強勁的多頭動能。")
    elif pct > 0:
        parts.append(f"期間內價格小幅上漲 {pct:+.2f}%。")
    elif pct < -10:
        parts.append(f"期間內價格大幅下跌 {pct:+.2f}%，顯示強勁的空頭壓力。")
    else:
        parts.append(f"期間內價格小幅下跌 {pct:+.2f}%。")

    # 波動率描述
    vol = result.volatility
    if vol > 10:
        parts.append(f"價格波動率為 {vol:.2f}%，波動劇烈，風險較高。")
    elif vol > 5:
        parts.append(f"價格波動率為 {vol:.2f}%，波動適中。")
    else:
        parts.append(f"價格波動率為 {vol:.2f}%，走勢相對穩定。")

    # RSI 描述
    rsi = result.rsi
    if rsi > 70:
        parts.append(f"RSI 為 {rsi:.1f}，已進入超買區間，短期內可能面臨回調壓力。")
    elif rsi < 30:
        parts.append(f"RSI 為 {rsi:.1f}，已進入超賣區間，短期內可能出現反彈。")
    elif rsi > 55:
        parts.append(f"RSI 為 {rsi:.1f}，偏向多方，買方力量略強。")
    elif rsi < 45:
        parts.append(f"RSI 為 {rsi:.1f}，偏向空方，賣方力量略強。")
    else:
        parts.append(f"RSI 為 {rsi:.1f}，處於中性區間，多空力量均衡。")

    return " ".join(parts)


def check_alerts(alerts: list[Alert], prices: dict[str, float]) -> list[tuple[Alert, float]]:
    """
    檢查哪些警示已被觸發。

    此函式為純邏輯函式，不涉及任何 I/O，可單獨測試。

    Args:
        alerts: 警示規則列表
        prices: 幣種 ID → 當前價格 的對應字典

    Returns:
        已觸發的 (Alert, 當前價格) 列表
    """
    triggered = []
    for alert in alerts:
        current_price = prices.get(alert.coin_id)
        if current_price is None:
            continue
        if alert.condition == "above" and current_price > alert.threshold:
            triggered.append((alert, current_price))
        elif alert.condition == "below" and current_price < alert.threshold:
            triggered.append((alert, current_price))
    return triggered


def format_alert_warnings(triggered: list[tuple[Alert, float]]) -> str:
    """
    格式化已觸發的警示為醒目的警告訊息。

    Args:
        triggered: (Alert, 當前價格) 的列表

    Returns:
        格式化的警告字串
    """
    if not triggered:
        return ""

    lines = [
        "",
        "┌─────────────────────────────────────────────┐",
        "│  ⚠️  PRICE ALERTS TRIGGERED                  │",
        "├─────────────────────────────────────────────┤",
    ]
    for alert, current_price in triggered:
        if alert.condition == "above":
            msg = f"  {alert.coin_id.upper()} = ${current_price:,.2f} > ${alert.threshold:,.2f}"
        else:
            msg = f"  {alert.coin_id.upper()} = ${current_price:,.2f} < ${alert.threshold:,.2f}"
        lines.append(f"│ 🚨 {msg.ljust(40)}│")
    lines.append("└─────────────────────────────────────────────┘")

    return "\n".join(lines)


# ============================================================
# 趨勢分析（v2.0 強化：新增 RSI）
# ============================================================

def analyze_trend(coin_id: str, price_data: list[dict], days: int) -> TrendResult:
    """
    對價格資料進行趨勢分析。
    v2.0 新增 RSI 計算。

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
            price_change_pct=0, volatility=0, high=0, low=0, rsi=50.0,
        )

    current_price = prices[-1]
    high = max(prices)
    low = min(prices)

    short_window = max(3, min(7, len(prices) // 4))
    long_window = max(7, min(21, len(prices) * 3 // 4))

    sma_short = calculate_sma(prices, short_window) or current_price
    sma_long = calculate_sma(prices, long_window) or current_price

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

    if prices[0] != 0:
        price_change_pct = ((current_price - prices[0]) / prices[0]) * 100
    else:
        price_change_pct = 0

    volatility = calculate_volatility(prices)

    # v2.0: 計算 RSI
    rsi_period = min(14, max(3, len(prices) // 2))
    rsi = calculate_rsi(prices, rsi_period)

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
        rsi=rsi,
    )


def format_trend_report(result: TrendResult, summary: str = "") -> str:
    """
    格式化趨勢分析報告。
    v2.0 新增 RSI 行與文字摘要。

    Args:
        result: TrendResult 物件
        summary: 自然語言趨勢摘要（v2.0 新增）

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
        f"  RSI:            {result.rsi:.1f}",  # v2.0 新增
        f"  Price Change:   {format_percentage(result.price_change_pct)}",
        f"  Volatility:     {result.volatility:.2f}%",
        f"",
        f"  Trend: {direction_symbol.get(result.trend_direction, result.trend_direction)}",
    ]

    # v2.0: 加入文字摘要
    if summary:
        lines.append(f"")
        lines.append(f"  ── Summary ──")
        # 每行最多 60 字元
        words = summary.split()
        current_line = "  "
        for word in words:
            if len(current_line) + len(word) + 1 > 62:
                lines.append(current_line)
                current_line = "  " + word
            else:
                current_line += (" " if current_line.strip() else "") + word
        if current_line.strip():
            lines.append(current_line)

    lines.append(f"")
    lines.append(f"{'═' * 50}")

    return "\n".join(lines)