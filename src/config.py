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

# RSI params: load from learned_params.json if present, else defaults
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
        if isinstance(learned.get("RSI_PERIOD"), int):
            RSI_PERIOD = learned["RSI_PERIOD"]
        if isinstance(learned.get("RSI_ENTRY"), int):
            RSI_ENTRY = learned["RSI_ENTRY"]
        if isinstance(learned.get("RSI_EXIT"), int):
            RSI_EXIT = learned["RSI_EXIT"]
        RSI_PARAMS_SOURCE = "learned_params.json"
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
