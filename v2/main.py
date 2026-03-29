"""
CryptoTracker v2.0 - CLI Entry Point
加密貨幣即時查詢與趨勢分析工具。

v2.0 新增指令：config, alert, compare
保持 Lazy Import 架構，確保 --help 在無依賴環境下可正常運作。

Usage:
    python main.py price --coin bitcoin
    python main.py top --num 10
    python main.py favorite add --coin bitcoin
    python main.py favorite list
    python main.py history --coin bitcoin --days 7
    python main.py trend --coin bitcoin --days 30
    python main.py export --coin bitcoin --days 7 --format csv
    python main.py config get
    python main.py config set --currency twd
    python main.py config reset
    python main.py alert add --coin bitcoin --above 100000
    python main.py alert list
    python main.py alert remove --id 1
    python main.py compare --coins bitcoin,ethereum,solana --days 7
"""

import sys
import os
import argparse

# 確保路徑正確
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

VERSION = "2.0.0"


def main():
    parser = argparse.ArgumentParser(
        prog="CryptoTracker",
        description="CryptoTracker — CLI 加密貨幣查詢與趨勢分析工具 (v2.0)",
    )
    parser.add_argument("--version", action="version", version=f"CryptoTracker {VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="可用指令")

    # === v1.0 保留指令 ===

    # price
    p_price = subparsers.add_parser("price", help="查詢指定幣種的即時價格")
    p_price.add_argument("--coin", required=True, help="幣種 ID（如 bitcoin）")
    p_price.add_argument("--currency", default=None, help="法幣代碼（預設讀取設定檔）")

    # top
    p_top = subparsers.add_parser("top", help="列出市值前 N 名的加密貨幣")
    p_top.add_argument("--num", type=int, default=None, help="顯示筆數（預設讀取設定檔）")

    # favorite
    p_fav = subparsers.add_parser("favorite", help="收藏清單管  ")
    fav_sub = p_fav.add_subparsers(dest="subcommand")
    f_add = fav_sub.add_parser("add", help="加入收藏")
    f_add.add_argument("--coin", required=True, help="幣種 ID")
    f_rem = fav_sub.add_parser("remove", help="移除收藏")
    f_rem.add_argument("--coin", required=True, help="幣種 ID")
    fav_sub.add_parser("list", help="列出收藏清單")

    # history
    p_hist = subparsers.add_parser("history", help="查詢歷史價  ")
    p_hist.add_argument("--coin", required=True, help="幣種 ID")
    p_hist.add_argument("--days", type=int, default=7, help="天數（預設 7）")

    # trend
    p_trend = subparsers.add_parser("trend", help="趨勢分析")
    p_trend.add_argument("--coin", required=True, help="幣種 ID")
    p_trend.add_argument("--days", type=int, default=30, help="天數（預設 30）")

    # export
    p_exp = subparsers.add_parser("export", help="匯出歷史資料")
    p_exp.add_argument("--coin", required=True, help="幣種 ID")
    p_exp.add_argument("--days", type=int, default=7, help="天數（預設 7）")
    p_exp.add_argument("--format", dest="fmt", default="csv", help="格式（csv/json）")

    # === v2.0 新增指令 ===

    # config
    p_config = subparsers.add_parser("config", help="個人設定管理")
    config_sub = p_config.add_subparsers(dest="subcommand")
    config_sub.add_parser("get", help="顯示目前設定")
    c_set = config_sub.add_parser("set", help="修改設定")
    c_set.add_argument("--currency", default=None, help="預設法幣")
    c_set.add_argument("--top-num", type=int, default=None, help="top 指令預設筆數")
    config_sub.add_parser("reset", help="重設為預設值")

    # alert
    p_alert = subparsers.add_parser("alert", help="價格警示管理")
    alert_sub = p_alert.add_subparsers(dest="subcommand")
    a_add = alert_sub.add_parser("add", help="新增警示")
    a_add.add_argument("--coin", required=True, help="幣種 ID")
    a_add.add_argument("--above", type=float, default=None, help="價格高於此值時警示")
    a_add.add_argument("--below", type=float, default=None, help="價格低於此值時警示")
    a_rem = alert_sub.add_parser("remove", help="移除警示")
    a_rem.add_argument("--id", type=int, required=True, dest="alert_id", help="警示 ID")
    alert_sub.add_parser("list", help="列出所有警示")

    # compare
    p_compare = subparsers.add_parser("compare", help="多幣種比較")
    p_compare.add_argument("--coins", required=True, help="幣種 ID（逗號分隔）")
    p_compare.add_argument("--days", type=int, default=7, help="比較天數（預設 7）")

    # 處理無參數或 help 的情況
    if len(sys.argv) <= 1:
        parser.print_help()
        return

    args = parser.parse_args()

    # 處理子指令的 help
    if args.command in ("favorite", "config", "alert") and not hasattr(args, "subcommand"):
        parser.parse_args([args.command, "--help"])
        return

    if args.command in ("favorite", "config", "alert") and args.subcommand is None:
        parser.parse_args([args.command, "--help"])
        return

    # Lazy Import：只有真正執行指令時才載入依賴
    try:
        from commands import CommandHandler
        handler = CommandHandler()
    except ImportError as e:
        print(f"Error: Missing dependencies. Please run 'pip install -r requirements.txt'")
        print(f"Detail: {e}")
        sys.exit(2)

    # === 指令派發 ===

    if args.command == "price":
        handler.cmd_price(args.coin, args.currency)

    elif args.command == "top":
        handler.cmd_top(args.num)

    elif args.command == "favorite":
        if args.subcommand == "add":
            handler.cmd_favorite_add(args.coin)
        elif args.subcommand == "remove":
            handler.cmd_favorite_remove(args.coin)
        elif args.subcommand == "list":
            handler.cmd_favorite_list()

    elif args.command == "history":
        handler.cmd_history(args.coin, args.days)

    elif args.command == "trend":
        handler.cmd_trend(args.coin, args.days)

    elif args.command == "export":
        handler.cmd_export(args.coin, args.days, args.fmt)

    # v2.0 新增指令
    elif args.command == "config":
        if args.subcommand == "get":
            handler.cmd_config_get()
        elif args.subcommand == "set":
            handler.cmd_config_set(currency=args.currency, top_num=args.top_num)
        elif args.subcommand == "reset":
            handler.cmd_config_reset()

    elif args.command == "alert":
        if args.subcommand == "add":
            handler.cmd_alert_add(args.coin, above=args.above, below=args.below)
        elif args.subcommand == "remove":
            handler.cmd_alert_remove(args.alert_id)
        elif args.subcommand == "list":
            handler.cmd_alert_list()

    elif args.command == "compare":
        handler.cmd_compare(args.coins, args.days)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()