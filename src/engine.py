"""Execution engine: apply signal with min-size check and cooldown; dry_run logs only."""
import json
import logging
import time
from decimal import Decimal

from . import config
from . import client

logger = logging.getLogger(__name__)

_last_order_time: float = 0.0


def _increment_trades_made() -> None:
    """Increment and persist the number of real orders placed (for UI tracker)."""
    path = config.TRADES_COUNT_FILE
    try:
        count = 0
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, dict) and "trades_made" in data:
                count = int(data["trades_made"])
        count += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"trades_made": count}, f, indent=2)
        config.secure_file(path)
    except (OSError, json.JSONDecodeError, TypeError) as e:
        logger.debug("Could not update trades count: %s", e)


def _round_down_usd(amount: Decimal) -> Decimal:
    """Round to 2 decimal places for USD."""
    return amount.quantize(Decimal("0.01"))

def _round_down_doge(amount: Decimal) -> Decimal:
    """Round to 0 decimal places for DOGE (exchange often uses whole DOGE min)."""
    return amount.quantize(Decimal("1"))

def run(
    signal: str,
    doge_balance: Decimal,
    usd_balance: Decimal,
) -> None:
    """Execute signal: buy (use all USD), sell (use all DOGE), or hold.
    Respects min order size (skip and log if below), cooldown, and dry_run.
    """
    global _last_order_time
    now = time.time()
    if signal == "hold":
        logger.info("Doing nothing (holding).")
        return
    if now - _last_order_time < config.ORDER_COOLDOWN_SECONDS:
        wait = int(config.ORDER_COOLDOWN_SECONDS - (now - _last_order_time))
        logger.info("Waiting out the cooldown (%s seconds left).", wait)
        return
    if signal == "buy":
        usd_available = _round_down_usd(usd_balance)
        if usd_available < Decimal(str(config.MIN_QUOTE_SIZE_USD)):
            logger.info("Skipping buy — only %.2f USD (need at least %.2f).", float(usd_available), config.MIN_QUOTE_SIZE_USD)
            return
        if config.DRY_RUN:
            logger.info("Would buy with %s USD (dry run, no order placed).", usd_available)
            return
        if not config.ALLOW_LIVE:
            logger.info("Live trading is disabled. Set DRY_RUN=false and ALLOW_LIVE=true to place real orders.")
            return
        try:
            logger.info("Placing post-only limit buy for %s USD.", usd_available)
            client.limit_buy_usd_post_only(usd_available)
            _last_order_time = now
            _increment_trades_made()
        except Exception as e:
            logger.exception("Buy failed: %s", e)
            _last_order_time = now  # cooldown before retry to avoid hammering API
        return
    if signal == "sell":
        doge_available = _round_down_doge(doge_balance)
        if doge_available < Decimal(str(config.MIN_BASE_SIZE_DOGE)):
            logger.info("Skipping sell — only %s DOGE (need at least %s).", doge_available, config.MIN_BASE_SIZE_DOGE)
            return
        if config.DRY_RUN:
            logger.info("Would sell %s DOGE (dry run, no order placed).", doge_available)
            return
        if not config.ALLOW_LIVE:
            logger.info("Live trading is disabled. Set DRY_RUN=false and ALLOW_LIVE=true to place real orders.")
            return
        try:
            logger.info("Placing post-only limit sell for %s DOGE.", doge_available)
            client.limit_sell_doge_post_only(doge_available)
            _last_order_time = now
            _increment_trades_made()
        except Exception as e:
            logger.exception("Sell failed: %s", e)
            _last_order_time = now  # cooldown before retry to avoid hammering API
