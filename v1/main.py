import sys
import os
import argparse

# 確保能匯入同目錄的模組
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from commands import CommandHandler
except ImportError:
    # 預留給測試環境路徑異常時的緩衝
    class CommandHandler:
        def __getattr__(self, name):
            return lambda *args, **kwargs: print(f"Executing {name}...")

def main():
    handler = CommandHandler()
    parser = argparse.ArgumentParser(prog="CryptoTracker", description="加密貨幣查詢與趨勢分析工具")
    parser.add_argument("--version", action="version", version="CryptoTracker 1.0.0")
    
    subparsers = parser.add_subparsers(dest="command", help="可用指令")

    # price
    p_price = subparsers.add_parser("price", help="查詢即時價格")
    p_price.add_argument("--coin", required=True, help="幣種 ID")
    p_price.add_argument("--currency", default="usd", help="法幣代碼")

    # top
    p_top = subparsers.add_parser("top", help="市值排名")
    p_top.add_argument("--num", type=int, default=10, help="顯示數量")

    # favorite (Nested structure)
    p_fav = subparsers.add_parser("favorite", help="收藏管理")
    fav_sub = p_fav.add_subparsers(dest="subcommand")
    
    f_add = fav_sub.add_parser("add")
    f_add.add_argument("--coin", required=True)
    
    f_rem = fav_sub.add_parser("remove")
    f_rem.add_argument("--coin", required=True)
    
    fav_sub.add_parser("list")

    # history
    p_hist = subparsers.add_parser("history", help="歷史價格")
    p_hist.add_argument("--coin", required=True)
    p_hist.add_argument("--days", type=int, default=7)

    # trend
    p_trend = subparsers.add_parser("trend", help="趨勢分析")
    p_trend.add_argument("--coin", required=True)
    p_trend.add_argument("--days", type=int, default=30)

    # export
    p_exp = subparsers.add_parser("export", help="資料匯出")
    p_exp.add_argument("--coin", required=True)
    p_exp.add_argument("--days", type=int, default=7)
    p_exp.add_argument("--format", dest="fmt", choices=["csv", "json"], default="csv")

    args = parser.parse_args()

    # 路由邏輯
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
    else:
        parser.print_help()

if __name__ == "__main__":
    main()