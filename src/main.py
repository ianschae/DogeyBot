"""Main loop: fetch candles and balance, run RSI strategy, run engine. One command to run."""
import json
import logging
import signal
import sys
import threading
import time
from datetime import datetime, timezone

from . import config
from . import client
from . import engine
from . import learn
from . import portfolio_log
from . import ui
from .strategies.rsi_mean_reversion import RSIMeanReversion, _rsi_wilder

logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_shutdown = False
_ui_shutdown_ref: threading.Event | None = None  # set when GUI is used, so Ctrl+C can close it


def _handle_sig(signum, frame):
    global _shutdown
    _shutdown = True
    if _ui_shutdown_ref is not None:
        _ui_shutdown_ref.set()
    logger.info("Shutting down (you pressed Ctrl+C).")


def _sleep_until_shutdown(seconds: int) -> None:
    """Sleep in 1s chunks so Ctrl+C is honored within ~1 second."""
    for _ in range(seconds):
        if _shutdown:
            break
        time.sleep(1)


def _write_status(
    doge: float,
    usd: float,
    in_position: bool,
    signal: str,
    portfolio_value: float,
    gain_usd: float,
    gain_pct: float,
    peak: float,
    drawdown_pct: float,
    days_tracked: float,
    avg_daily_gain_pct: float,
    avg_daily_gain_usd: float,
    price: float,
    candles: list,
    strategy_period: int,
    rsi_entry: int,
    rsi_exit: int,
    last_learn_time: float,
    change_24h_pct: float | None = None,
    volume_24h: float | None = None,
) -> None:
    """Write status.json for the UI (only when UI_ENABLED)."""
    if not config.UI_ENABLED:
        return
    closes = []
    for c in candles:
        try:
            closes.append(float(c.get("close", 0)))
        except (TypeError, ValueError):
            continue
    rsi = _rsi_wilder(closes, strategy_period) if len(closes) >= strategy_period + 1 else None
    try:
        config.STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(config.STATUS_FILE, "w") as f:
            payload = {
                "doge": round(doge, 8),
                "usd": round(usd, 2),
                "in_position": in_position,
                "signal": signal,
                "portfolio_value": round(portfolio_value, 2),
                "gain_usd": round(gain_usd, 2),
                "gain_pct": round(gain_pct, 2),
                "peak_usd": round(peak, 2),
                "drawdown_pct": round(drawdown_pct, 2),
                "days_tracked": round(days_tracked, 1),
                "avg_daily_gain_pct": round(avg_daily_gain_pct, 2),
                "avg_daily_gain_usd": round(avg_daily_gain_usd, 2),
                "price": round(price, 6),
                "rsi": round(rsi, 1) if rsi is not None else None,
                "rsi_entry": rsi_entry,
                "rsi_exit": rsi_exit,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "next_check_seconds": config.POLL_INTERVAL_SECONDS,
                "last_learn_timestamp_utc": datetime.fromtimestamp(last_learn_time, tz=timezone.utc).isoformat(),
                "learn_interval_seconds": config.LEARN_INTERVAL_SECONDS,
                "dry_run": config.DRY_RUN,
                "allow_live": config.ALLOW_LIVE,
            }
            if change_24h_pct is not None:
                payload["change_24h_pct"] = round(change_24h_pct, 2)
            if volume_24h is not None:
                payload["volume_24h"] = round(volume_24h, 0)
            json.dump(payload, f, indent=2)
        config.secure_file(config.STATUS_FILE)
    except OSError as e:
        logger.debug("Could not write status file: %s", e)


def _bot_loop(strategy: RSIMeanReversion) -> None:
    """Run the trading loop until _shutdown is set. Used in a thread when GUI is on main thread."""
    last_learn_time = time.time()
    while not _shutdown:
        try:
            if time.time() - last_learn_time >= config.LEARN_INTERVAL_SECONDS:
                logger.info("Time to re-check the best settings (running the backtest again)...")
                learned = learn.run_learn(days=config.LEARN_DAYS, logger=logger)
                last_learn_time = time.time()
                if learned is not None:
                    entry, exit_, return_pct, trades = learned
                    period = learn.PERIOD
                    strategy.period = period
                    strategy.entry = entry
                    strategy.exit = exit_
                    logger.info("Updated settings: buy when RSI < %s, sell when RSI > %s. Backtest: %s%% (%s trades).", entry, exit_, f"{return_pct:.2f}", trades)
            logger.info("---")
            logger.info("Checking the market and your balance...")
            candles = client.get_closed_candles(config.CANDLES_COUNT)
            if len(candles) < strategy.period + 2:
                logger.warning("Not enough price history yet (%s candles, need at least %s). Skipping this round.", len(candles), strategy.period + 2)
                _sleep_until_shutdown(config.POLL_INTERVAL_SECONDS)
                continue
            doge, usd = client.get_doge_and_usd_balances()
            in_position = float(doge) >= config.MIN_BASE_SIZE_DOGE
            portfolio_value = gain_usd = gain_pct = 0.0
            peak = drawdown_pct = days_tracked = avg_daily_gain_pct = avg_daily_gain_usd = 0.0
            try:
                candle_price = float(candles[-1].get("close", 0))
            except (TypeError, ValueError):
                candle_price = 0.0
            if candle_price <= 0:
                logger.warning("Invalid or missing close price; skipping this round.")
                _sleep_until_shutdown(config.POLL_INTERVAL_SECONDS)
                continue
            # Use current product price and market data for display; fall back to candle close if API fails
            market = client.get_product_market_data()
            display_price = market.get("price")
            if display_price is None or display_price <= 0:
                display_price = candle_price
            change_24h_pct = market.get("change_24h_pct")
            volume_24h = market.get("volume_24h")
            try:
                (portfolio_value, gain_usd, gain_pct, peak, drawdown_pct,
                 days_tracked, avg_daily_gain_pct, avg_daily_gain_usd) = portfolio_log.record(doge, usd, candle_price)
                logger.info("Balance: %s DOGE, %s USD. Holding DOGE: %s.", doge, usd, in_position)
                logger.info("Portfolio: $%.2f (gain $%.2f / %s%%); peak $%.2f; %s days; avg daily %s%% / $%.2f.",
                    portfolio_value, gain_usd, f"{gain_pct:.2f}", peak, f"{days_tracked:.1f}", f"{avg_daily_gain_pct:.2f}", avg_daily_gain_usd)
            except Exception as e:
                logger.warning("Portfolio snapshot skipped: %s", e)
                logger.info("Balance: %s DOGE, %s USD. Holding DOGE: %s.", doge, usd, in_position)
            sig = strategy.get_signal(candles, in_position)
            logger.info("Decision: %s.", sig)
            engine.run(sig, doge, usd)
            _write_status(
                float(doge), float(usd), in_position, sig,
                portfolio_value, gain_usd, gain_pct, peak, drawdown_pct, days_tracked, avg_daily_gain_pct, avg_daily_gain_usd,
                display_price, candles, strategy.period,
                strategy.entry, strategy.exit, last_learn_time,
                change_24h_pct=change_24h_pct,
                volume_24h=volume_24h,
            )
            logger.info("Next check in %s seconds.", config.POLL_INTERVAL_SECONDS)
        except Exception as e:
            logger.exception("Something went wrong: %s", e)
        _sleep_until_shutdown(config.POLL_INTERVAL_SECONDS)
    logger.info("Stopped.")


def main():
    global _shutdown
    if not config.COINBASE_API_KEY or not config.COINBASE_API_SECRET:
        logger.error("Please set COINBASE_API_KEY and COINBASE_API_SECRET in your .env file.")
        sys.exit(1)
    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)
    logger.info("Up and running — DOGE-USD, 6-hour candles. Dry run: %s, allow live: %s.", config.DRY_RUN, config.ALLOW_LIVE)
    if config.DRY_RUN:
        logger.info("No orders will be placed (dry run). Set DRY_RUN=false and ALLOW_LIVE=true in .env to trade live.")
    elif not config.ALLOW_LIVE:
        logger.info("No orders will be placed (ALLOW_LIVE not set). Set ALLOW_LIVE=true in .env to trade live.")
    learned = learn.run_learn(days=config.LEARN_DAYS, logger=logger)
    if learned is not None:
        entry, exit_, return_pct, trades = learned
        period = learn.PERIOD
        strategy = RSIMeanReversion(period=period, entry=entry, exit=exit_)
        logger.info("Using the best settings from the backtest: buy when RSI < %s, sell when RSI > %s. That would have been %s%% over the last 60 days (%s trades).", entry, exit_, f"{return_pct:.2f}", trades)
    else:
        strategy = RSIMeanReversion(
            period=config.RSI_PERIOD,
            entry=config.RSI_ENTRY,
            exit=config.RSI_EXIT,
        )
        logger.info("Using saved settings: buy when RSI < %s, sell when RSI > %s.", config.RSI_ENTRY, config.RSI_EXIT)

    if config.UI_ENABLED:
        # macOS (and Cocoa) require the GUI to run on the main thread. So we run the bot in a
        # background thread and the GUI on the main thread.
        global _ui_shutdown_ref
        _ui_shutdown_ref = threading.Event()
        ui_shutdown = _ui_shutdown_ref
        bot_thread = threading.Thread(target=_bot_loop, args=(strategy,), daemon=False)
        bot_thread.start()
        logger.info("GUI opened.")
        ui.run_gui(ui_shutdown)
        _shutdown = True
        bot_thread.join(timeout=5)
        if bot_thread.is_alive():
            logger.debug("Bot thread did not stop in time.")
        logger.info("UI stopped.")
    else:
        _bot_loop(strategy)


if __name__ == "__main__":
    main()
