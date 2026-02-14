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

# Require at least one trade so we don't pick "no trades" as best.
MIN_TRADES = 1
# Backtest for learning assumes zero fees and zero slippage (find best raw strategy).
LEARN_FEE_PCT = 0.0
LEARN_SLIPPAGE_PCT = 0.0

# Grid: search these (entry, exit) combos. Pick the one with highest full-period return > 0.
# Single wide grid so we find the best profitable combo.
GRID_ENTRY = list(range(18, 44, 2))   # 18–42
GRID_EXIT = list(range(46, 66, 2))   # 46–64, exit > entry


def _compute_rsi_series(candles: list[dict]) -> list[float | None]:
    """Precompute RSI for each candle index. rsi_series[i] is RSI at candle i, or None if not enough data."""
    out = [None] * len(candles)
    closes = []
    for c in candles:
        try:
            closes.append(float(c.get("close", 0)))
        except (TypeError, ValueError):
            closes.append(0.0)
    for i in range(PERIOD + 1, len(closes)):
        rsi = _rsi_wilder(closes[: i + 1], PERIOD)
        out[i] = rsi
    return out


def run_backtest(
    candles: list[dict],
    entry: int,
    exit_: int,
    fee_pct: float | None = None,
    slippage_pct: float = 0.0,
    rsi_series: list[float | None] | None = None,
    start_index: int = 0,
    initial_usd: float | None = None,
    initial_doge: float | None = None,
) -> tuple[float, int, float, float]:
    """Simulate RSI strategy. Returns (return_pct, trade_count, final_usd, final_doge).
    If rsi_series is provided it must match candles; otherwise RSI is computed per bar.
    start_index/initial_*: when set, simulation starts at that candle with that state (for holdout)."""
    if len(candles) < PERIOD + 2:
        return 0.0, 0, INITIAL_USD, 0.0
    if fee_pct is None:
        fee_pct = config.LEARN_FEE_PCT
    if rsi_series is None:
        rsi_series = _compute_rsi_series(candles)
    usd = initial_usd if initial_usd is not None else INITIAL_USD
    doge = initial_doge if initial_doge is not None else 0.0
    trades = 0
    for i in range(max(PERIOD + 1, start_index), len(candles)):
        rsi = rsi_series[i] if i < len(rsi_series) else None
        if rsi is None:
            continue
        close_price = float(candles[i].get("close", 0))
        if close_price <= 0:
            continue
        in_position = doge > 0
        if not in_position and rsi < entry:
            usd_after_fee = usd * (1.0 - fee_pct / 100.0)
            fill_buy = close_price * (1.0 + slippage_pct / 100.0)
            doge = usd_after_fee / fill_buy
            usd = 0.0
            trades += 1
        elif in_position and rsi > exit_:
            fill_sell = close_price * (1.0 - slippage_pct / 100.0)
            usd = doge * fill_sell * (1.0 - fee_pct / 100.0)
            doge = 0.0
            trades += 1
    if doge > 0 and candles:
        last_close = float(candles[-1].get("close", 0))
        if last_close > 0:
            usd = doge * last_close
            doge = 0.0
    value_end = usd
    if start_index > 0 and initial_usd is not None:
        initial_value = initial_usd + (initial_doge or 0.0) * float(candles[start_index].get("close", 0))
    else:
        initial_value = INITIAL_USD
    if initial_value <= 0:
        return 0.0, trades, usd, doge
    return_pct = 100.0 * (value_end - initial_value) / initial_value
    return return_pct, trades, usd, doge


def run_learn(days: int = LEARN_DAYS, logger=None) -> Optional[tuple[int | None, int | None, float, int]]:
    """Fetch history, run full-period backtest for each (entry, exit). Pick the combo with
    highest return > 0 and at least MIN_TRADES. Write learned_params.json and return it.
    If no profitable combo, return (None, None, default_ret, default_tr) for UI only."""
    end_ts = int(time.time())
    start_ts = end_ts - days * 86400
    if logger:
        logger.info("Looking at the last %s days of DOGE-USD prices...", days)
    candles = client.get_candles_range(start_ts, end_ts, "SIX_HOUR")
    if len(candles) < PERIOD + 2:
        if logger:
            logger.warning("Learning skipped: not enough history (%s candles).", len(candles))
        return None
    rsi_series = _compute_rsi_series(candles)
    if logger:
        logger.info("Got %s candles. Searching for profitable (entry, exit) on full period (0%% fees, 0%% slippage)...",
            len(candles))
    best_ret = None
    best_tr = 0
    best_entry = None
    best_exit = None
    for entry in GRID_ENTRY:
        for exit_ in GRID_EXIT:
            if exit_ <= entry:
                continue
            full_ret, full_tr, _, _ = run_backtest(
                candles, entry, exit_, LEARN_FEE_PCT, LEARN_SLIPPAGE_PCT, rsi_series
            )
            if full_ret <= 0 or full_tr < MIN_TRADES:
                continue
            better = (
                best_ret is None
                or full_ret > best_ret
                or (full_ret == best_ret and full_tr > best_tr)
            )
            if better:
                best_ret = full_ret
                best_tr = full_tr
                best_entry = entry
                best_exit = exit_
    if best_entry is not None:
        out = {"RSI_PERIOD": PERIOD, "RSI_ENTRY": best_entry, "RSI_EXIT": best_exit}
        path = Path(__file__).resolve().parent.parent / "learned_params.json"
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        config.secure_file(path)
        if logger:
            logger.info("Profitable combo: RSI < %s, RSI > %s → %s%%, %s trades. Saved to %s.",
                best_entry, best_exit, f"{best_ret:.2f}", best_tr, path)
        return (best_entry, best_exit, best_ret, best_tr)
    if logger:
        logger.warning("No profitable combo in grid. Using default params for display.")
    try:
        from . import config as cfg
        default_entry = getattr(cfg, "RSI_ENTRY", 30)
        default_exit = getattr(cfg, "RSI_EXIT", 50)
        if default_exit <= default_entry:
            default_entry, default_exit = 30, 50
        full_ret, full_tr, _, _ = run_backtest(
            candles, default_entry, default_exit, LEARN_FEE_PCT, LEARN_SLIPPAGE_PCT, rsi_series
        )
        return (None, None, full_ret, full_tr)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Learn RSI params from backtest (standalone)")
    parser.add_argument("--days", type=int, default=LEARN_DAYS, help="Lookback days (default %s)" % LEARN_DAYS)
    args = parser.parse_args()
    days = max(1, args.days)
    result = run_learn(days=days, logger=None)
    if result is None:
        print("No profitable combo found (and could not run defaults backtest). Keeping defaults.")
        sys.exit(0)
    entry, exit_, return_pct, trades = result
    if entry is not None and exit_ is not None:
        path = Path(__file__).resolve().parent.parent / "learned_params.json"
        print(f"Best: entry={entry}, exit={exit_} -> backtest {return_pct:.2f}%, {trades} trades")
        print(f"Wrote {path}")
        print("Restart the bot (python -m src.main) to use these params.")
    else:
        print(f"No profitable combo found. Defaults backtest: {return_pct:.2f}%, {trades} trades. No file written.")


if __name__ == "__main__":
    main()
