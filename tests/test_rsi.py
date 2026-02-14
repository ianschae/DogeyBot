"""Tests for RSI Wilder calculation and signal logic."""
import pytest

from src.strategies.rsi_mean_reversion import _rsi_wilder, signal_from_rsi


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


def test_signal_from_rsi_buy_when_flat_and_oversold():
    assert signal_from_rsi(25, 30, 50, False) == "buy"
    assert signal_from_rsi(29, 30, 50, False) == "buy"


def test_signal_from_rsi_no_buy_when_in_position():
    assert signal_from_rsi(25, 30, 50, True) == "hold"


def test_signal_from_rsi_sell_when_in_position_and_over_exit():
    assert signal_from_rsi(55, 30, 50, True) == "sell"
    assert signal_from_rsi(51, 30, 50, True) == "sell"


def test_signal_from_rsi_hold():
    assert signal_from_rsi(40, 30, 50, False) == "hold"
    assert signal_from_rsi(40, 30, 50, True) == "hold"
    assert signal_from_rsi(30, 30, 50, False) == "hold"  # need strictly < entry to buy
    assert signal_from_rsi(50, 30, 50, True) == "hold"  # need strictly > exit to sell
