"""Test Coinbase API connections (read-only: accounts and candles). Optional: place small real orders with --test-buy / --test-sell / --test-order."""
import argparse
import sys
import time
from decimal import Decimal

from . import config
from . import client


def main():
    parser = argparse.ArgumentParser(description="Test API connections")
    parser.add_argument("--test-order", action="store_true", help="Place one small order: buy if you have USD, else sell if you have DOGE")
    parser.add_argument("--test-buy", action="store_true", help="Place one small post-only limit buy (min USD)")
    parser.add_argument("--test-sell", action="store_true", help="Place one small post-only limit sell (min DOGE)")
    args = parser.parse_args()

    print("Testing API connections (read-only)...")
    if not config.COINBASE_API_KEY or not config.COINBASE_API_SECRET:
        print("FAIL: COINBASE_API_KEY and COINBASE_API_SECRET must be set in .env")
        sys.exit(1)
    ok = True

    # 1. Accounts (balances)
    print("\n1. Accounts (get_accounts)...")
    try:
        doge, usd = client.get_doge_and_usd_balances()
        print(f"   OK — DOGE: {doge}, USD: {usd}")
    except Exception as e:
        print(f"   FAIL — {e}")
        ok = False

    # 2. Closed candles (trading loop)
    print("\n2. Closed candles (get_closed_candles)...")
    try:
        candles = client.get_closed_candles(config.CANDLES_COUNT)
        if not candles:
            print("   WARN — no candles returned")
        else:
            last = candles[-1]
            print(f"   OK — {len(candles)} candles, last close: {last.get('close')}")
    except Exception as e:
        print(f"   FAIL — {e}")
        ok = False

    # 3. Candles range (learning)
    print("\n3. Candles range (get_candles_range, last 7 days)...")
    try:
        end_ts = int(time.time())
        start_ts = end_ts - 7 * 86400
        candles = client.get_candles_range(start_ts, end_ts, "SIX_HOUR")
        if not candles:
            print("   WARN — no candles returned")
        else:
            print(f"   OK — {len(candles)} candles")
    except Exception as e:
        print(f"   FAIL — {e}")
        ok = False

    # 4. Optional: place small real order(s)
    do_order = args.test_order or args.test_buy or args.test_sell
    if do_order and ok:
        print("\n4. Order API...")
        doge, usd = client.get_doge_and_usd_balances()
        try:
            if args.test_buy:
                if float(usd) >= config.MIN_QUOTE_SIZE_USD:
                    print(f"   Placing post-only limit buy for {config.MIN_QUOTE_SIZE_USD} USD...")
                    client.limit_buy_usd_post_only(Decimal(str(config.MIN_QUOTE_SIZE_USD)))
                    print("   OK — limit buy order placed.")
                else:
                    print(f"   SKIP — you have {float(usd):.2f} USD. Need at least {config.MIN_QUOTE_SIZE_USD} USD.")
            if args.test_sell:
                if float(doge) >= config.MIN_BASE_SIZE_DOGE:
                    print(f"   Placing post-only limit sell for {config.MIN_BASE_SIZE_DOGE} DOGE...")
                    client.limit_sell_doge_post_only(Decimal(str(int(config.MIN_BASE_SIZE_DOGE))))
                    print("   OK — limit sell order placed.")
                else:
                    print(f"   SKIP — you have {float(doge):.2f} DOGE. Need at least {config.MIN_BASE_SIZE_DOGE} DOGE.")
            if args.test_order and not args.test_buy and not args.test_sell:
                if float(usd) >= config.MIN_QUOTE_SIZE_USD:
                    print(f"   Placing post-only limit buy for {config.MIN_QUOTE_SIZE_USD} USD...")
                    client.limit_buy_usd_post_only(Decimal(str(config.MIN_QUOTE_SIZE_USD)))
                    print("   OK — limit buy order placed.")
                elif float(doge) >= config.MIN_BASE_SIZE_DOGE:
                    print(f"   Placing post-only limit sell for {config.MIN_BASE_SIZE_DOGE} DOGE...")
                    client.limit_sell_doge_post_only(Decimal(str(int(config.MIN_BASE_SIZE_DOGE))))
                    print("   OK — limit sell order placed.")
                else:
                    print(f"   SKIP — need at least {config.MIN_QUOTE_SIZE_USD} USD or {config.MIN_BASE_SIZE_DOGE} DOGE to place a test order.")
        except Exception as e:
            print(f"   FAIL — {e}")
            ok = False

    print()
    if ok:
        print("All API connections OK." + (" (Including order.)" if do_order else ""))
        sys.exit(0)
    else:
        print("Some checks failed. Fix errors above and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
