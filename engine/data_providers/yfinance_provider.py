"""yfinance data provider — wraps engine.data.DataFeed with the DataProvider interface."""

from __future__ import annotations

import datetime as dt
from typing import Optional

import pandas as pd

from engine.accounts import CredentialStore
from engine.data import DataFeed
from engine.data_providers.base import DataProvider


class YFinanceDataProvider(DataProvider):
    """Historical and live market data via yfinance (free, no API key).

    Caches historical pulls to disk under <home>/data_cache/ (parquet).
    Supports intraday intervals for approximately the last 60 days;
    use interval='1d' for older date ranges.
    """

    name = "yfinance"
    is_live = True

    def __init__(self, home: str, credentials: Optional[CredentialStore] = None,
                 cache_ttl_seconds: int = 3600):
        super().__init__(home, credentials)
        self._feed = DataFeed(home)
        self.cache_ttl_seconds = cache_ttl_seconds

    def get_historical(self, ticker: str, start: str, end: str,
                       interval: str = "1d") -> pd.DataFrame:
        return self._feed.get_historical(
            ticker, start, end, interval=interval,
            use_cache=True, cache_ttl_seconds=self.cache_ttl_seconds,
        )

    def get_last_price(self, ticker: str) -> tuple[float, dt.datetime]:
        return DataFeed.get_last_price(ticker)
