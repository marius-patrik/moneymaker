"""yfinance data provider — wraps engine.data.DataFeed with the DataProvider interface."""

from __future__ import annotations

import datetime as dt
from typing import Optional

import pandas as pd

from src.accounts import CredentialStore
from src.data import DataFeed
from src.data_providers.base import DataProvider


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

    def get_last_prices(self, tickers: list[str]) -> dict[str, float]:
        """
        Last price for many instruments in one request.

        Polling each separately costs one HTTP round trip per instrument,
        which caps how many can be recorded; batched, twenty cost about the
        same as one.
        """
        if not tickers:
            return {}
        import yfinance as yf

        out: dict[str, float] = {}
        try:
            data = yf.download(tickers=" ".join(tickers), period="1d",
                               interval="1m", progress=False,
                               group_by="ticker", threads=True)
        except Exception:
            return out

        for tk in tickers:
            try:
                frame = data[tk] if len(tickers) > 1 else data
                closes = frame["Close"].dropna()
                if len(closes):
                    out[tk] = float(closes.iloc[-1])
            except Exception:
                continue    # a delisted or misspelled symbol must not break the batch
        return out
