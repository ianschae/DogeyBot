"""Tests for portfolio log record()."""
import csv
import json
from pathlib import Path

import src.portfolio_log as pl


def test_record_creates_state_and_csv(tmp_path):
    pl.STATE_FILE = tmp_path / "state.json"
    pl.LOG_FILE = tmp_path / "log.csv"
    try:
        pv, gain_usd, gain_pct = pl.record(100.0, 50.0, 0.5)
        assert pv == 50.0 + 100.0 * 0.5  # 100.0
        assert gain_usd == 0.0
        assert gain_pct == 0.0
        assert pl.STATE_FILE.exists()
        with open(pl.STATE_FILE) as f:
            state = json.load(f)
        assert "initial_portfolio_value_usd" in state
        assert state["initial_portfolio_value_usd"] == 100.0
        assert pl.LOG_FILE.exists()
        with open(pl.LOG_FILE) as f:
            rows = list(csv.reader(f))
        assert len(rows) >= 1
        assert rows[0][0] == "timestamp_utc" or len(rows[0]) == 7
        # Second call: portfolio 110 (50 doge * 0.5 + 60 usd = 85? no: 50 doge, 60 usd, price 0.5 -> 60+25=85)
        pv2, gain2, pct2 = pl.record(50.0, 60.0, 0.5)
        assert pv2 == 60.0 + 50.0 * 0.5  # 85.0
        assert gain2 == 85.0 - 100.0  # -15.0
        assert pct2 == 100.0 * (-15.0 / 100.0)  # -15.0
    finally:
        # Restore defaults so other tests or main aren't affected
        pl.STATE_FILE = Path(pl.__file__).resolve().parent.parent / "portfolio_state.json"
        pl.LOG_FILE = Path(pl.__file__).resolve().parent.parent / "portfolio_log.csv"


def test_record_zero_price_returns_zeros(tmp_path):
    pl.STATE_FILE = tmp_path / "state.json"
    pl.LOG_FILE = tmp_path / "log.csv"
    try:
        pv, gain_usd, gain_pct = pl.record(10.0, 5.0, 0.0)
        assert pv == 0.0
        assert gain_usd == 0.0
        assert gain_pct == 0.0
    finally:
        pl.STATE_FILE = Path(pl.__file__).resolve().parent.parent / "portfolio_state.json"
        pl.LOG_FILE = Path(pl.__file__).resolve().parent.parent / "portfolio_log.csv"
