"""Chart indicators, computed from the same candles the chart draws.

Strategies already reason about moving averages, VWAP and RSI, but the chart
could not show any of them — so you could see a system's trades without
seeing what it was reacting to. These run server-side so the overlay and the
strategy read the same numbers rather than two implementations that drift.
"""

from __future__ import annotations

from typing import Optional, Sequence


def sma(values: Sequence[float], period: int) -> list[Optional[float]]:
    """Simple moving average. Leading positions are None until the window fills."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[Optional[float]] = []
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        out.append(running / period if i >= period - 1 else None)
    return out


def ema(values: Sequence[float], period: int) -> list[Optional[float]]:
    """
    Exponential moving average, seeded with the first full SMA.

    Seeding on the SMA rather than the first value keeps the early output
    from being dragged around by a single bar.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out

    k = 2.0 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def vwap(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
         volumes: Sequence[float]) -> list[Optional[float]]:
    """
    Volume-weighted average price, cumulative over the series.

    Falls back to an unweighted running mean when the feed carries no volume
    (common for futures via yfinance) so the line still means something
    rather than vanishing.
    """
    out: list[Optional[float]] = []
    cum_pv = cum_v = 0.0
    have_volume = any(v > 0 for v in volumes)
    for i, c in enumerate(closes):
        typical = (highs[i] + lows[i] + c) / 3.0
        weight = volumes[i] if have_volume else 1.0
        cum_pv += typical * weight
        cum_v += weight
        out.append(cum_pv / cum_v if cum_v else None)
    return out


def rsi(values: Sequence[float], period: int = 14) -> list[Optional[float]]:
    """Wilder's RSI. Returns None until `period` changes are available."""
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return out

    gains = losses = 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)

    for i in range(period + 1, len(values)):
        change = values[i] - values[i - 1]
        avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


# What the UI may request, and how each is drawn.
CATALOG = {
    "sma":  {"label": "SMA",  "pane": "price", "params": {"period": 20}},
    "ema":  {"label": "EMA",  "pane": "price", "params": {"period": 20}},
    "vwap": {"label": "VWAP", "pane": "price", "params": {}},
    "rsi":  {"label": "RSI",  "pane": "lower", "params": {"period": 14}},
}


def compute(kind: str, candles: list[dict], period: int = 20) -> list[Optional[float]]:
    """Dispatch by name over a list of OHLCV dicts."""
    closes = [c["close"] for c in candles]
    if kind == "sma":
        return sma(closes, period)
    if kind == "ema":
        return ema(closes, period)
    if kind == "rsi":
        return rsi(closes, period)
    if kind == "vwap":
        return vwap([c["high"] for c in candles], [c["low"] for c in candles],
                    closes, [c.get("volume", 0.0) for c in candles])
    raise ValueError(f"unknown indicator: {kind}")
