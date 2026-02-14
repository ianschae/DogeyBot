"""Load config from environment. Only API key, secret, and dry_run for v1."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Required
COINBASE_API_KEY = os.environ.get("COINBASE_API_KEY", "").strip()
COINBASE_API_SECRET = os.environ.get("COINBASE_API_SECRET", "").strip()

# Optional: default true = dry-run (log only, no real orders)
DRY_RUN = os.environ.get("DRY_RUN", "true").strip().lower() in ("true", "1", "yes")
# Optional: must be true alongside DRY_RUN=false to allow live orders
ALLOW_LIVE = os.environ.get("ALLOW_LIVE", "false").strip().lower() in ("true", "1", "yes")

# Hardcoded for v1
PRODUCT_ID = "DOGE-USD"
CANDLE_GRANULARITY = "SIX_HOUR"
_VALID_GRANULARITIES = frozenset((
    "ONE_MINUTE", "FIVE_MINUTE", "FIFTEEN_MINUTE", "THIRTY_MINUTE",
    "ONE_HOUR", "TWO_HOUR", "FOUR_HOUR", "SIX_HOUR", "ONE_DAY",
))

# RSI params (and optional CANDLE_GRANULARITY) from learned_params.json if present
_LEARNED_PARAMS_PATH = Path(__file__).resolve().parent.parent / "learned_params.json"
_default_period, _default_entry, _default_exit = 14, 30, 50
RSI_PERIOD = _default_period
RSI_ENTRY = _default_entry
RSI_EXIT = _default_exit
RSI_PARAMS_SOURCE = "defaults"
if _LEARNED_PARAMS_PATH.exists():
    try:
        with open(_LEARNED_PARAMS_PATH) as f:
            learned = json.load(f)
        p = learned.get("RSI_PERIOD")
        e = learned.get("RSI_ENTRY")
        x = learned.get("RSI_EXIT")
        if isinstance(p, int) and 1 <= p <= 100:
            RSI_PERIOD = p
        if isinstance(e, int) and isinstance(x, int) and 1 <= e < x <= 100:
            RSI_ENTRY = e
            RSI_EXIT = x
            RSI_PARAMS_SOURCE = "learned_params.json"
        g = learned.get("CANDLE_GRANULARITY")
        if isinstance(g, str) and g.strip() in _VALID_GRANULARITIES:
            CANDLE_GRANULARITY = g.strip()
    except (json.JSONDecodeError, OSError):
        pass


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except (ValueError, TypeError):
        return default


ORDER_COOLDOWN_SECONDS = _int_env("ORDER_COOLDOWN_SECONDS", 300)
CANDLES_COUNT = 36  # fetch 36, use last 35 closed
POLL_INTERVAL_SECONDS = _int_env("POLL_INTERVAL_SECONDS", 60)
STATUS_REFRESH_SECONDS = _int_env("STATUS_REFRESH_SECONDS", 15)  # refresh price/market data in status for UI
LEARN_DAYS = _int_env("LEARN_DAYS", 60)
LEARN_INTERVAL_SECONDS = _int_env("LEARN_INTERVAL_SECONDS", 24 * 3600)

_log_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
LOG_LEVEL = getattr(__import__("logging"), _log_level, None) or 20  # INFO

# Min order sizes (Coinbase DOGE-USD; fallback if product endpoint not used)
MIN_QUOTE_SIZE_USD = 1.0
MIN_BASE_SIZE_DOGE = 1.0


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)).strip())
    except (ValueError, TypeError):
        return default


# Optional: fee % per trade side for backtest realism (default 0)
LEARN_FEE_PCT = _float_env("LEARN_FEE_PCT", 0.0)

# Optional: GUI (doge-game window; tkinter)
UI_ENABLED = os.environ.get("UI_ENABLED", "true").strip().lower() in ("true", "1", "yes")
STATUS_FILE = Path(__file__).resolve().parent.parent / "status.json"


def secure_file(path: Path) -> None:
    """Restrict file to owner read/write only (0o600). No-op on failure (e.g. Windows)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
