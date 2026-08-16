"""Simulated data provider — synthetic bar generation and hardcoded fixtures.

Two modes:
  1. Brownian motion (default): generates synthetic OHLCV bars with a random
     walk. Good for unit tests and dry-run validation of strategy logic without
     requiring real market data.
  2. Fixture mode: replay a hardcoded list of (timestamp, price, volume) tuples.
     Good for deterministic unit tests that assert specific P&L outcomes.

Neither mode requires an API key or network access.

Usage:
    # Random walk
    provider = SimulatedDataProvider(home, seed=42)
    df = provider.get_historical("TEST", "2026-01-01", "2026-02-01", interval="1d")

    # Fixture
    import datetime as dt
    bars = [
        (dt.datetime(2026, 1, 2, 9, 30), 100.0, 1000),
        (dt.datetime(2026, 1, 2, 9, 35), 100.5, 1200),
    ]
    provider = SimulatedDataProvider(home, fixtures={"TEST": bars})
    df = provider.get_historical("TEST", "2026-01-01", "2026-02-01")
"""

from __future__ import annotations

import datetime as dt
import random
from typing import Optional

import pandas as pd

from src.accounts import CredentialStore
from src.data_providers.base import DataProvider


class SimulatedDataProvider(DataProvider):
    """Generates synthetic market data for testing. No network access required."""

    name = "simulated"
    is_live = True  # supports get_last_price via synthetic tick

    def __init__(
        self,
        home: str,
        credentials: Optional[CredentialStore] = None,
        seed: Optional[int] = None,
        fixtures: Optional[dict[str, list[tuple]]] = None,
        start_price: float = 100.0,
        daily_vol: float = 0.01,
    ):
        super().__init__(home, credentials)
        self.rng = random.Random(seed)
        self.fixtures = fixtures or {}
        self.start_price = start_price
        self.daily_vol = daily_vol
        self._last_prices: dict[str, float] = {}

    def get_historical(self, ticker: str, start: str, end: str,
                       interval: str = "1d") -> pd.DataFrame:
        if ticker in self.fixtures:
            return self._from_fixtures(ticker, start, end)
        return self._brownian(ticker, start, end, interval)

    def get_last_price(self, ticker: str) -> tuple[float, dt.datetime]:
        last = self._last_prices.get(ticker, self.start_price)
        last *= 1 + self.rng.gauss(0, self.daily_vol / 100)
        self._last_prices[ticker] = last
        return last, dt.datetime.now()

    def _from_fixtures(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        bars = self.fixtures[ticker]
        rows = []
        start_dt = pd.Timestamp(start)
        end_dt = pd.Timestamp(end)
        for ts, price, vol in bars:
            t = pd.Timestamp(ts)
            if start_dt <= t < end_dt:
                rows.append({"Close": float(price), "Open": float(price),
                             "High": float(price), "Low": float(price),
                             "Volume": float(vol)})
        if not rows:
            raise ValueError(f"No fixture data for {ticker} between {start} and {end}.")
        index = [pd.Timestamp(ts) for ts, _, _ in self.fixtures[ticker]
                 if pd.Timestamp(start) <= pd.Timestamp(ts) < pd.Timestamp(end)]
        return pd.DataFrame(rows, index=index)

    def _brownian(self, ticker: str, start: str, end: str, interval: str) -> pd.DataFrame:
        freq_map = {
            "1m": dt.timedelta(minutes=1),
            "5m": dt.timedelta(minutes=5),
            "15m": dt.timedelta(minutes=15),
            "1h": dt.timedelta(hours=1),
            "1d": dt.timedelta(days=1),
        }
        step = freq_map.get(interval, dt.timedelta(days=1))
        is_intraday = step < dt.timedelta(days=1)

        timestamps = []
        prices = []
        price = self._last_prices.get(ticker, self.start_price)
        vol_per_bar = self.daily_vol * (step.total_seconds() / 86400) ** 0.5

        cursor = dt.datetime.fromisoformat(start)
        end_dt = dt.datetime.fromisoformat(end)

        while cursor < end_dt:
            if is_intraday:
                # Skip weekends and non-trading hours (9:30–16:00 ET approximate)
                if cursor.weekday() >= 5:
                    cursor += dt.timedelta(days=1)
                    cursor = cursor.replace(hour=9, minute=30, second=0, microsecond=0)
                    continue
                if cursor.time() < dt.time(9, 30) or cursor.time() >= dt.time(16, 0):
                    cursor += step
                    continue
            else:
                if cursor.weekday() >= 5:
                    cursor += dt.timedelta(days=1)
                    continue

            price *= 1 + self.rng.gauss(0, vol_per_bar)
            timestamps.append(pd.Timestamp(cursor))
            prices.append(price)
            cursor += step

        self._last_prices[ticker] = price

        if not timestamps:
            raise ValueError(f"No simulated bars generated for {ticker} between {start} and {end}.")

        return pd.DataFrame({
            "Open": prices,
            "High": [p * (1 + abs(self.rng.gauss(0, vol_per_bar / 2))) for p in prices],
            "Low": [p * (1 - abs(self.rng.gauss(0, vol_per_bar / 2))) for p in prices],
            "Close": prices,
            "Volume": [float(abs(int(self.rng.gauss(1_000_000, 200_000)))) for _ in prices],
        }, index=timestamps)
