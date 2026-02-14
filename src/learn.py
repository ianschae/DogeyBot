"""Learn RSI entry/exit by backtesting on recent DOGE-USD history. Writes learned_params.json."""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

from . import client
from . import config
from .strategies.rsi_mean_reversion import _rsi_wilder

PERIOD = 14
LEARN_DAYS = config.LEARN_DAYS
LEARN_INTERVAL_SECONDS = config.LEARN_INTERVAL_SECONDS
INITIAL_USD = 1000.0

# Expanding grid rounds: try until we find a profitable combo (entry < exit).
# Each round is (entry_values, exit_values). We stop at first round that has return > 0.
GRID_ROUNDS = [
    ([28, 30, 32], [48, 50, 52]),
    (list(range(24, 38, 2)), list(range(46, 58, 2))),   # round 2: wider
    (list(range(20, 42, 2)), list(range(44, 62, 2))),   # round 3: even wider
]


def run_backtest(candles: list[dict], entry: int, exit_: int, fee_pct: float = None) -> tuple[float, int]:
    """Simulate RSI strategy. Returns (return_pct, trade_count). Period fixed at 14.
    fee_pct: optional fee per trade side (e.g. 0.5 for 0.5%%); uses config.LEARN_FEE_PCT if None."""
    if len(candles) < PERIOD + 2:
        return 0.0, 0
    if fee_pct is None:
        fee_pct = config.LEARN_FEE_PCT
    usd = INITIAL_USD
    doge = 0.0
    trades = 0
    for i in range(PERIOD + 1, len(candles)):
        window = candles[: i + 1]
        closes = []
        for c in window:
            try:
                closes.append(float(c.get("close", 0)))
            except (TypeError, ValueError):
                continue
        if len(closes) < PERIOD + 2:
            continue
        rsi = _rsi_wilder(closes, PERIOD)
        if rsi is None:
            continue
        close_price = float(window[-1].get("close", 0))
        if close_price <= 0:
            continue
        in_position = doge > 0
        if not in_position and rsi < entry:
            usd_after_fee = usd * (1.0 - fee_pct / 100.0)
            doge = usd_after_fee / close_price
            usd = 0.0
            trades += 1
        elif in_position and rsi > exit_:
            usd = doge * close_price * (1.0 - fee_pct / 100.0)
            doge = 0.0
            trades += 1
    if doge > 0 and candles:
        last_close = float(candles[-1].get("close", 0))
        if last_close > 0:
            usd = doge * last_close
    if INITIAL_USD <= 0:
        return 0.0, trades
    return_pct = 100.0 * (usd - INITIAL_USD) / INITIAL_USD
    return return_pct, trades


def run_learn(days: int = LEARN_DAYS, logger=None) -> Optional[tuple[int, int, float, int]]:
    """Fetch history, run expanding grid backtest until a profitable combo is found.
    Writes learned_params.json and returns (entry, exit, return_pct, trades) or None."""
    end_ts = int(time.time())
    start_ts = end_ts - days * 86400
    if logger:
        logger.info("Looking at the last %s days of DOGE-USD prices...", days)
    candles = client.get_candles_range(start_ts, end_ts, "SIX_HOUR")
    if len(candles) < PERIOD + 2:
        if logger:
            logger.warning("Learning skipped: couldn't fetch enough history (%s candles, need %s+). Using default settings.", len(candles), PERIOD + 2)
        return None
    if logger:
        logger.info("Got %s candles. Searching for a profitable combo (expanding grid until one is found)...", len(candles))
    for round_num, (entry_grid, exit_grid) in enumerate(GRID_ROUNDS, start=1):
        if logger:
            logger.info("Round %s: trying entry %s, exit %s.", round_num, entry_grid, exit_grid)
        best_return = None
        best_trades = 0
        best_entry = None
        best_exit = None
        for entry in entry_grid:
            for exit_ in exit_grid:
                if exit_ <= entry:
                    continue
                ret, tr = run_backtest(candles, entry, exit_)
                if logger:
                    logger.info("  Buy when RSI < %s, sell when RSI > %s → %s%%, %s trades.", entry, exit_, f"{ret:.2f}", tr)
                if tr < 1:
                    continue
                if ret > 0 and (best_return is None or ret > best_return or (ret == best_return and tr > best_trades)):
                    best_return = ret
                    best_trades = tr
                    best_entry = entry
                    best_exit = exit_
        if best_entry is not None and best_return is not None and best_return > 0:
            out = {"RSI_PERIOD": PERIOD, "RSI_ENTRY": best_entry, "RSI_EXIT": best_exit}
            path = Path(__file__).resolve().parent.parent / "learned_params.json"
            with open(path, "w") as f:
                json.dump(out, f, indent=2)
            config.secure_file(path)
            if logger:
                logger.info("Found a profitable combo: buy when RSI < %s, sell when RSI > %s → %s%%, %s trades.", best_entry, best_exit, f"{best_return:.2f}", best_trades)
                logger.info("Saved settings to %s.", path)
            return (best_entry, best_exit, best_return, best_trades)
        if logger:
            logger.info("Round %s: no profitable combo, expanding search...", round_num)
    if logger:
        logger.warning("No profitable combo found after all rounds. Using default settings.")
    return None


def main():
    parser = argparse.ArgumentParser(description="Learn RSI params from backtest (standalone)")
    parser.add_argument("--days", type=int, default=LEARN_DAYS, help="Lookback days (default %s)" % LEARN_DAYS)
    args = parser.parse_args()
    days = max(1, args.days)
    result = run_learn(days=days, logger=None)
    if result is None:
        print("No profitable combo found after all grid rounds. Keeping defaults (no file written).")
        sys.exit(0)
    entry, exit_, return_pct, trades = result
    path = Path(__file__).resolve().parent.parent / "learned_params.json"
    print(f"Best: entry={entry}, exit={exit_} -> return={return_pct:.2f}%, trades={trades}")
    print(f"Wrote {path}")
    print("Restart the bot (python -m src.main) to use these params.")


if __name__ == "__main__":
    main()
