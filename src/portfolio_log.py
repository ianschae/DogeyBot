"""Track portfolio value and total gains over time. Persists initial value, peak, and a CSV log."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config

STATE_FILE = Path(__file__).resolve().parent.parent / "portfolio_state.json"
LOG_FILE = Path(__file__).resolve().parent.parent / "portfolio_log.csv"
CSV_HEADER = (
    "timestamp_utc", "usd", "doge", "price", "portfolio_value_usd", "gain_usd", "gain_pct",
    "peak_usd", "drawdown_pct", "days_tracked", "avg_daily_gain_pct", "avg_daily_gain_usd",
)


def _load_state(portfolio_value_usd: float) -> tuple[float, float, str | None]:
    """Load state. Returns (initial, peak, started_at_iso). Creates new state if missing/invalid."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise TypeError("not a dict")
            initial = float(data.get("initial_portfolio_value_usd", portfolio_value_usd))
            if initial <= 0:
                raise ValueError("invalid initial")
            peak = float(data.get("peak_portfolio_value_usd", initial))
            if peak < initial:
                peak = initial
            started = data.get("started_at")
            return initial, peak, started
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    initial = peak = portfolio_value_usd
    started = datetime.now(timezone.utc).isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({
            "initial_portfolio_value_usd": initial,
            "peak_portfolio_value_usd": peak,
            "started_at": started,
        }, f, indent=2)
    config.secure_file(STATE_FILE)
    return initial, peak, started


def _save_peak(peak: float, started_at: str) -> None:
    """Update state file with new peak (keeps initial and started_at)."""
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
        data["peak_portfolio_value_usd"] = peak
        data["started_at"] = data.get("started_at") or started_at
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)
        config.secure_file(STATE_FILE)
    except (json.JSONDecodeError, OSError, TypeError):
        pass


def record(doge: float, usd: float, price: float) -> tuple[float, float, float, float, float, float, float, float]:
    """Record current portfolio snapshot. Price = DOGE-USD (use current market price for accurate value).
    Returns (portfolio_value_usd, gain_usd, gain_pct, peak_usd, drawdown_pct, days_tracked, avg_daily_gain_pct, avg_daily_gain_usd)."""
    doge = float(doge)
    usd = float(usd)
    if price <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    portfolio_value = usd + doge * price
    initial, peak, started_at = _load_state(portfolio_value)
    if portfolio_value > peak:
        peak = portfolio_value
        _save_peak(peak, started_at or datetime.now(timezone.utc).isoformat())
    gain_usd = portfolio_value - initial
    gain_pct = (100.0 * gain_usd / initial) if initial else 0.0
    drawdown_usd = peak - portfolio_value
    drawdown_pct = (100.0 * drawdown_usd / peak) if peak else 0.0
    days_tracked = 0  # full days only
    if started_at:
        try:
            then = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - then.replace(tzinfo=timezone.utc)
            days_tracked = max(0, int(delta.total_seconds() / 86400))
        except (ValueError, TypeError):
            pass
    avg_daily_gain_pct = (gain_pct / days_tracked) if days_tracked >= 1 else gain_pct
    avg_daily_gain_usd = (gain_usd / days_tracked) if days_tracked >= 1 else gain_usd
    now = datetime.now(timezone.utc).isoformat()
    write_header = not LOG_FILE.exists()
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(CSV_HEADER)
        w.writerow((
            now, f"{usd:.2f}", f"{doge:.8f}", f"{price:.6f}", f"{portfolio_value:.2f}",
            f"{gain_usd:.2f}", f"{gain_pct:.2f}", f"{peak:.2f}", f"{drawdown_pct:.2f}",
            f"{days_tracked:.1f}", f"{avg_daily_gain_pct:.2f}", f"{avg_daily_gain_usd:.2f}",
        ))
    config.secure_file(LOG_FILE)
    return portfolio_value, gain_usd, gain_pct, peak, drawdown_pct, days_tracked, avg_daily_gain_pct, avg_daily_gain_usd
