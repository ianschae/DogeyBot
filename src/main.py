"""Main loop: fetch candles and balance, run RSI strategy, run engine. One command to run."""
import logging
import signal
import sys
import time

from . import config
from . import client
from . import engine
from . import learn
from . import portfolio_log
from .strategies.rsi_mean_reversion import RSIMeanReversion

logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_shutdown = False


def _handle_sig(signum, frame):
    global _shutdown
    _shutdown = True
    logger.info("Shutting down (you pressed Ctrl+C).")


def _sleep_until_shutdown(seconds: int) -> None:
    """Sleep in 1s chunks so Ctrl+C is honored within ~1 second."""
    for _ in range(seconds):
        if _shutdown:
            break
        time.sleep(1)


def main():
    if not config.COINBASE_API_KEY or not config.COINBASE_API_SECRET:
        logger.error("Please set COINBASE_API_KEY and COINBASE_API_SECRET in your .env file.")
        sys.exit(1)
    signal.signal(signal.SIGINT, _handle_sig)
    signal.signal(signal.SIGTERM, _handle_sig)
    logger.info("Up and running — DOGE-USD, 6-hour candles. Quote currency: %s. Dry run: %s, allow live: %s.", config.QUOTE_CURRENCY, config.DRY_RUN, config.ALLOW_LIVE)
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
            doge, usd, usdc = client.get_doge_and_usd_balances()
            # In position only if we have a sellable amount of DOGE (avoids dust blocking buys when you DCA and have DOGE + USD)
            in_position = float(doge) >= config.MIN_BASE_SIZE_DOGE
            try:
                price = float(candles[-1].get("close", 0))
            except (TypeError, ValueError):
                price = 0.0
            try:
                portfolio_value, gain_usd, gain_pct = portfolio_log.record(doge, usd + usdc, price)
                logger.info("Balance: %s DOGE, %s USD, %s USDC. Holding DOGE: %s.", doge, usd, usdc, in_position)
                logger.info("Portfolio: $%.2f (total gain $%.2f / %s%% since tracking started).", portfolio_value, gain_usd, f"{gain_pct:.2f}")
            except Exception as e:
                logger.warning("Portfolio snapshot skipped: %s", e)
                logger.info("Balance: %s DOGE, %s USD, %s USDC. Holding DOGE: %s.", doge, usd, usdc, in_position)
            sig = strategy.get_signal(candles, in_position)
            logger.info("Decision: %s.", sig)
            engine.run(sig, doge, usd, usdc)
            logger.info("Next check in %s seconds.", config.POLL_INTERVAL_SECONDS)
        except Exception as e:
            logger.exception("Something went wrong: %s", e)
        _sleep_until_shutdown(config.POLL_INTERVAL_SECONDS)
    logger.info("Stopped.")


if __name__ == "__main__":
    main()
