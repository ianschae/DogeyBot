"""Track portfolio value and total gains over time. Persists initial value and a CSV log."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config

STATE_FILE = Path(__file__).resolve().parent.parent / "portfolio_state.json"
LOG_FILE = Path(__file__).resolve().parent.parent / "portfolio_log.csv"
CSV_HEADER = ("timestamp_utc", "usd", "doge", "price", "portfolio_value_usd", "gain_usd", "gain_pct")


def _ensure_state(portfolio_value_usd: float) -> float:
    """Load or create state. Returns initial_portfolio_value_usd (sets it to current if new)."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            initial = float(data.get("initial_portfolio_value_usd", portfolio_value_usd))
            if initial > 0:
                return initial
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    initial = portfolio_value_usd
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({
            "initial_portfolio_value_usd": initial,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)
    config.secure_file(STATE_FILE)
    return initial


def record(doge: float, usd: float, price: float) -> tuple[float, float, float]:
    """Record current portfolio snapshot. Price = DOGE-USD (e.g. last candle close).
    Returns (portfolio_value_usd, gain_usd, gain_pct). Creates state and appends CSV row."""
    doge = float(doge)
    usd = float(usd)
    if price <= 0:
        return 0.0, 0.0, 0.0
    portfolio_value = usd + doge * price
    initial = _ensure_state(portfolio_value)
    gain_usd = portfolio_value - initial
    gain_pct = (100.0 * gain_usd / initial) if initial else 0.0
    # Append to CSV
    now = datetime.now(timezone.utc).isoformat()
    write_header = not LOG_FILE.exists()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(CSV_HEADER)
        w.writerow((now, f"{usd:.2f}", f"{doge:.8f}", f"{price:.6f}", f"{portfolio_value:.2f}", f"{gain_usd:.2f}", f"{gain_pct:.2f}"))
    config.secure_file(LOG_FILE)
    return portfolio_value, gain_usd, gain_pct
