"""Tests for backtest and learn logic."""
import pytest

from src.learn import run_backtest, PERIOD, INITIAL_USD


def test_run_backtest_not_enough_candles_returns_zero():
    candles = [{"close": "100.0"}] * 10
    ret, trades, _, _ = run_backtest(candles, 30, 50)
    assert ret == 0.0
    assert trades == 0


def test_run_backtest_returns_tuple():
    # Enough candles, no trades triggered (flat prices -> RSI 100, never < 30)
    candles = [{"close": "100.0", "start": i} for i in range(PERIOD + 10)]
    ret, trades, _, _ = run_backtest(candles, 30, 50)
    assert isinstance(ret, float)
    assert isinstance(trades, int)
    assert trades == 0
    assert ret == 0.0


def test_run_backtest_with_fee_reduces_return():
    # Long-enough candle list that might trigger trades; with 0 fee vs 1% fee
    candles = [{"close": str(100.0 - i * 0.5), "start": i} for i in range(50)]
    ret0, tr0, _, _ = run_backtest(candles, 35, 55, fee_pct=0.0)
    ret1, tr1, _, _ = run_backtest(candles, 35, 55, fee_pct=1.0)
    # Same number of trades; with fee return should be lower (or equal if no trades)
    assert tr0 == tr1
    assert ret1 <= ret0
