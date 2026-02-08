"""Tests for RSI Wilder calculation."""
import pytest

from src.strategies.rsi_mean_reversion import _rsi_wilder


def test_rsi_wilder_not_enough_data_returns_none():
    # Need at least period+1 = 15 points for period=14
    assert _rsi_wilder([1.0] * 10, 14) is None
    assert _rsi_wilder([1.0] * 14, 14) is None


def test_rsi_wilder_constant_prices_returns_100():
    # No losses -> RSI = 100
    closes = [100.0] * 20
    assert _rsi_wilder(closes, 14) == 100.0


def test_rsi_wilder_all_losses_returns_0():
    # Strictly decreasing: all losses, no gains -> RSI = 0
    closes = [100.0 - i for i in range(20)]
    assert _rsi_wilder(closes, 14) == 0.0


def test_rsi_wilder_known_sequence():
    # 15 points: first 14 flat, then one up -> small positive RSI
    closes = [100.0] * 14 + [101.0]
    rsi = _rsi_wilder(closes, 14)
    assert rsi is not None
    assert 0 < rsi <= 100
