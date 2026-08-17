"""Tests for chart indicators (src/indicators.py)."""

import pytest

from src.indicators import compute, ema, rsi, sma, vwap


def test_sma_is_none_until_the_window_fills():
    out = sma([1, 2, 3, 4, 5], 3)
    assert out[:2] == [None, None]
    assert out[2] == pytest.approx(2.0)      # (1+2+3)/3
    assert out[-1] == pytest.approx(4.0)     # (3+4+5)/3


def test_sma_of_a_flat_series_is_the_value():
    assert sma([7.0] * 6, 3)[-1] == pytest.approx(7.0)


def test_ema_seeds_on_the_first_full_sma():
    values = [1, 2, 3, 4, 5]
    out = ema(values, 3)
    assert out[:2] == [None, None]
    # Seed is the SMA of the first three, not the first value.
    assert out[2] == pytest.approx(2.0)


def test_ema_tracks_a_rising_series_below_price():
    values = list(range(1, 30))
    out = ema(values, 10)
    assert out[-1] is not None
    assert out[-1] < values[-1]              # lags a rising series


def test_series_shorter_than_the_period_yields_all_none():
    assert ema([1, 2], 5) == [None, None]
    assert rsi([1, 2], 5) == [None, None]


def test_rsi_is_100_when_every_change_is_a_gain():
    out = rsi(list(range(1, 20)), 14)
    assert out[-1] == pytest.approx(100.0)


def test_rsi_is_0_when_every_change_is_a_loss():
    out = rsi(list(range(20, 1, -1)), 14)
    assert out[-1] == pytest.approx(0.0)


def test_rsi_of_a_balanced_series_sits_mid_range():
    values = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11]
    out = rsi(values, 14)
    assert out[-1] is not None
    assert 30 < out[-1] < 70


def test_vwap_weights_by_volume():
    # Two bars: a cheap one with heavy volume, a dear one with light volume.
    out = vwap([10, 20], [10, 20], [10, 20], [90, 10])
    assert out[-1] == pytest.approx((10 * 90 + 20 * 10) / 100)


def test_vwap_falls_back_to_an_unweighted_mean_without_volume():
    """Futures feeds often report no volume; the line should still be drawn."""
    out = vwap([10, 20], [10, 20], [10, 20], [0, 0])
    assert out[-1] == pytest.approx(15.0)


def test_compute_dispatches_and_rejects_unknown_names():
    candles = [{"high": 2, "low": 1, "close": 1.5, "volume": 5} for _ in range(20)]
    assert len(compute("sma", candles, 5)) == 20
    assert len(compute("vwap", candles)) == 20
    with pytest.raises(ValueError):
        compute("nope", candles)


def test_a_non_positive_period_is_rejected():
    with pytest.raises(ValueError):
        sma([1, 2, 3], 0)
