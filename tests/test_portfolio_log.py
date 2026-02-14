"""Tests for portfolio log record()."""
import csv
import json
from pathlib import Path

import src.portfolio_log as pl


def test_record_creates_state_and_csv(tmp_path):
    pl.STATE_FILE = tmp_path / "state.json"
    pl.LOG_FILE = tmp_path / "log.csv"
    try:
        pv, gain_usd, gain_pct, peak, drawdown_pct, days_tracked, avg_daily_pct, avg_daily_usd = pl.record(100.0, 50.0, 0.5)
        assert pv == 50.0 + 100.0 * 0.5  # 100.0
        assert gain_usd == 0.0
        assert gain_pct == 0.0
        assert peak == 100.0
        assert drawdown_pct == 0.0
        assert pl.STATE_FILE.exists()
        with open(pl.STATE_FILE) as f:
            state = json.load(f)
        assert state["initial_portfolio_value_usd"] == 100.0
        assert state.get("peak_portfolio_value_usd") == 100.0
        assert "started_at" in state
        with open(pl.LOG_FILE) as f:
            rows = list(csv.reader(f))
        assert len(rows) >= 1
        assert rows[0][0] == "timestamp_utc" or len(rows[0]) >= 7
        # Second call: portfolio 85 (50 doge * 0.5 + 60 usd)
        pv2, gain2, pct2, peak2, dd_pct, days2, avg2_pct, avg2_usd = pl.record(50.0, 60.0, 0.5)
        assert pv2 == 85.0
        assert gain2 == -15.0
        assert pct2 == -15.0
        assert peak2 == 100.0
        assert dd_pct == 15.0  # (100 - 85) / 100 * 100
    finally:
        # Restore defaults so other tests or main aren't affected
        pl.STATE_FILE = Path(pl.__file__).resolve().parent.parent / "portfolio_state.json"
        pl.LOG_FILE = Path(pl.__file__).resolve().parent.parent / "portfolio_log.csv"


def test_record_zero_price_returns_zeros(tmp_path):
    pl.STATE_FILE = tmp_path / "state.json"
    pl.LOG_FILE = tmp_path / "log.csv"
    try:
        pv, gain_usd, gain_pct, peak, dd_pct, days, avg_pct, avg_usd = pl.record(10.0, 5.0, 0.0)
        assert pv == 0.0
        assert gain_usd == 0.0
        assert gain_pct == 0.0
        assert peak == 0.0
        assert dd_pct == 0.0
        assert avg_usd == 0.0
    finally:
        pl.STATE_FILE = Path(pl.__file__).resolve().parent.parent / "portfolio_state.json"
        pl.LOG_FILE = Path(pl.__file__).resolve().parent.parent / "portfolio_log.csv"
