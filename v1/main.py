"""
CryptoTracker v1.0 - CLI Entry Point
加密貨幣即時查詢與趨勢分析工具。

使用 click library 建構 CLI 介面，支援子指令群組。
所有業務邏輯委託給 CommandHandler 處理。

Usage:
    python main.py price --coin bitcoin
    python main.py top --num 10
    python main.py favorite add --coin bitcoin
    python main.py favorite list
    python main.py history --coin bitcoin --days 7
    python main.py trend --coin bitcoin --days 30
    python main.py export --coin bitcoin --days 7 --format csv
"""

import click

from commands import CommandHandler

# 版本號常數
VERSION = "1.0.0"

# 建立全域 CommandHandler 實例
handler = CommandHandler()


@click.group()
@click.version_option(version=VERSION, prog_name="CryptoTracker")
def cli():
    """CryptoTracker — CLI 加密貨幣查詢與趨勢分析工具。"""
    pass


@cli.command()
@click.option("--coin", required=True, type=str, help="幣種 ID（如 bitcoin, ethereum）")
@click.option("--currency", default="usd", type=str, help="法幣代碼（預設 usd）")
def price(coin: str, currency: str):
    """查詢指定幣種的即時價格。"""
    handler.cmd_price(coin, currency)


@cli.command()
@click.option("--num", default=10, type=int, help="顯示的幣種數量（預設 10）")
def top(num: int):
    """列出市值前 N 名的加密貨幣。"""
    handler.cmd_top(num)


@cli.group()
def favorite():
    """收藏清單管理。"""
    pass


@favorite.command("add")
@click.option("--coin", required=True, type=str, help="要收藏的幣種 ID")
def favorite_add(coin: str):
    """將幣種加入收藏清單。"""
    handler.cmd_favorite_add(coin)


@favorite.command("remove")
@click.option("--coin", required=True, type=str, help="要移除的幣種 ID")
def favorite_remove(coin: str):
    """從收藏清單移除幣種。"""
    handler.cmd_favorite_remove(coin)


@favorite.command("list")
def favorite_list():
    """列出所有收藏幣種及其即時價格。"""
    handler.cmd_favorite_list()


@cli.command()
@click.option("--coin", required=True, type=str, help="幣種 ID")
@click.option("--days", default=7, type=int, help="查詢天數（預設 7）")
def history(coin: str, days: int):
    """查詢指定幣種的歷史價格。"""
    handler.cmd_history(coin, days)


@cli.command()
@click.option("--coin", required=True, type=str, help="幣種 ID")
@click.option("--days", default=30, type=int, help="分析天數（預設 30）")
def trend(coin: str, days: int):
    """對指定幣種進行趨勢分析。"""
    handler.cmd_trend(coin, days)


@cli.command()
@click.option("--coin", required=True, type=str, help="幣種 ID")
@click.option("--days", default=7, type=int, help="匯出天數（預設 7）")
@click.option("--format", "fmt", default="csv", type=str, help="匯出格式（csv / json）")
def export(coin: str, days: int, fmt: str):
    """匯出歷史資料為 CSV 或 JSON 檔案。"""
    handler.cmd_export(coin, days, fmt)


if __name__ == "__main__":
    cli()