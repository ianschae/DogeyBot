"""Execution engine: apply signal with min-size check and cooldown; dry_run logs only."""
import logging
import time
from decimal import Decimal

from . import config
from . import client

logger = logging.getLogger(__name__)

_last_order_time: float = 0.0


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
            logger.info("Buying with %s USD.", usd_available)
            client.market_buy_usd(usd_available)
            _last_order_time = now
        except Exception as e:
            logger.exception("Buy failed: %s", e)
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
            logger.info("Selling %s DOGE.", doge_available)
            client.market_sell_doge(doge_available)
            _last_order_time = now
        except Exception as e:
            logger.exception("Sell failed: %s", e)
