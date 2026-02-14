"""RSI(14) mean reversion: buy when RSI < 30, sell when in_position and RSI > 50."""
import logging
from decimal import Decimal

from .base import BaseStrategy

logger = logging.getLogger(__name__)


def _rsi_wilder(closes: list[float], period: int = 14) -> float | None:
    """RSI using Wilder smoothing. closes ascending. Returns None if not enough data."""
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(ch if ch > 0 else 0.0)
        losses.append(-ch if ch < 0 else 0.0)
    # Wilder: first avg = SMA of first `period` values; then smoothed
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def signal_from_rsi(rsi: float, entry: int, exit_threshold: int, in_position: bool) -> str:
    """Single source of truth for buy/sell/hold. Used by both live strategy and backtest."""
    if not in_position and rsi < entry:
        return "buy"
    if in_position and rsi > exit_threshold:
        return "sell"
    return "hold"


class RSIMeanReversion(BaseStrategy):
    def __init__(self, period: int = 14, entry: int = 30, exit: int = 50):
        self.period = period
        self.entry = entry
        self.exit = exit

    def get_signal(self, candles: list[dict], in_position: bool) -> str:
        if len(candles) < self.period + 2:
            return "hold"
        closes = []
        for c in candles:
            try:
                closes.append(float(c.get("close", 0)))
            except (TypeError, ValueError):
                continue
        if len(closes) < self.period + 2:
            return "hold"
        rsi = _rsi_wilder(closes, self.period)
        if rsi is None:
            return "hold"
        logger.info("RSI is %.1f. (We buy when it's under %d, sell when it's over %d. Holding DOGE: %s.)", rsi, self.entry, self.exit, in_position)
        sig = signal_from_rsi(rsi, self.entry, self.exit, in_position)
        if sig == "buy":
            logger.info("RSI is oversold — deciding to buy.")
        elif sig == "sell":
            logger.info("RSI has recovered — deciding to sell.")
        else:
            logger.info("Staying put (holding).")
        return sig
