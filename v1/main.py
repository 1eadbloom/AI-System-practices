import sys
import os
import argparse

# 確保路徑正確
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(prog="CryptoTracker", description="加密貨幣查詢工具")
    parser.add_argument("--version", action="version", version="1.0.0")
    
    subparsers = parser.add_subparsers(dest="command", help="可用指令")

    # 1. price
    p_price = subparsers.add_parser("price")
    p_price.add_argument("--coin", required=True)
    p_price.add_argument("--currency", default="usd")

    # 2. top
    p_top = subparsers.add_parser("top")
    p_top.add_argument("--num", type=int, default=10)

    # 3. favorite
    p_fav = subparsers.add_parser("favorite")
    fav_sub = p_fav.add_subparsers(dest="subcommand")
    f_add = fav_sub.add_parser("add")
    f_add.add_argument("--coin", required=True)
    f_rem = fav_sub.add_parser("remove")
    f_rem.add_argument("--coin", required=True)
    fav_sub.add_parser("list")

    # 4. history / trend / export
    p_hist = subparsers.add_parser("history")
    p_hist.add_argument("--coin", required=True)
    p_hist.add_argument("--days", type=int, default=7)

    p_trend = subparsers.add_parser("trend")
    p_trend.add_argument("--coin", required=True)
    p_trend.add_argument("--days", type=int, default=30)

    p_exp = subparsers.add_parser("export")
    p_exp.add_argument("--coin", required=True)
    p_exp.add_argument("--days", type=int, default=7)
    p_exp.add_argument("--format", dest="fmt", default="csv")

    # 如果只是 python v1/main.py --help，到此為止都不會 import 任何第三方庫
    if len(sys.argv) <= 1 or "--help" in sys.argv or "-h" in sys.argv:
        parser.print_help()
        return

    args = parser.parse_args()

    # 只有真的要執行指令時，才匯入邏輯層（避免 CI 因為沒裝 requests 而在載入時報錯）
    try:
        from commands import CommandHandler
        handler = CommandHandler()
    except ImportError as e:
        print(f"Error: Missing dependencies. Please run 'pip install -r requirements.txt'")
        print(f"Detail: {e}")
        sys.exit(2)

    # 指令派發... (其餘邏輯與前述相同)
    if args.command == "price":
        handler.cmd_price(args.coin, args.currency)
    elif args.command == "top":
        handler.cmd_top(args.num)
    elif args.command == "favorite":
        if args.subcommand == "add": handler.cmd_favorite_add(args.coin)
        elif args.subcommand == "remove": handler.cmd_favorite_remove(args.coin)
        elif args.subcommand == "list": handler.cmd_favorite_list()
    elif args.command == "history":
        handler.cmd_history(args.coin, args.days)
    elif args.command == "trend":
        handler.cmd_trend(args.coin, args.days)
    elif args.command == "export":
        handler.cmd_export(args.coin, args.days, args.fmt)

if __name__ == "__main__":
    main()