"""Test Coinbase API connections (read-only: accounts and candles). Optional: place one small real order with --test-order."""
import argparse
import sys
import time
from decimal import Decimal

from . import config
from . import client


def main():
    parser = argparse.ArgumentParser(description="Test API connections")
    parser.add_argument("--test-order", action="store_true", help="Place one small real order ($1 buy or 1 DOGE sell) to verify order API")
    parser.add_argument("--test-buy", action="store_true", help="Place one small real buy ($1 USD) to verify buy API")
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

    # 4. Optional: place one small real order
    do_order = args.test_order or args.test_buy
    if do_order and ok:
        print("\n4. Order API...")
        doge, usd = client.get_doge_and_usd_balances()
        try:
            if args.test_buy:
                if float(usd) >= config.MIN_QUOTE_SIZE_USD:
                    print(f"   Placing market buy for {config.MIN_QUOTE_SIZE_USD} USD...")
                    client.market_buy_usd(Decimal(str(config.MIN_QUOTE_SIZE_USD)))
                    print("   OK — buy order placed.")
                else:
                    print(f"   SKIP — you have {float(usd):.2f} USD. Need at least {config.MIN_QUOTE_SIZE_USD} USD.")
            else:
                # --test-order: buy with USD, else sell if DOGE
                if float(usd) >= config.MIN_QUOTE_SIZE_USD:
                    print(f"   Placing market buy for {config.MIN_QUOTE_SIZE_USD} USD...")
                    client.market_buy_usd(Decimal(str(config.MIN_QUOTE_SIZE_USD)))
                    print("   OK — buy order placed.")
                elif float(doge) >= config.MIN_BASE_SIZE_DOGE:
                    print(f"   Placing market sell for {config.MIN_BASE_SIZE_DOGE} DOGE...")
                    client.market_sell_doge(Decimal(str(int(config.MIN_BASE_SIZE_DOGE))))
                    print("   OK — sell order placed.")
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
