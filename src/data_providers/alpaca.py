"""Alpaca Markets data provider (free tier available, API key required).

Alpaca provides free historical market data via their Data API v2.
Requires a free Alpaca account (https://alpaca.markets/).

Setup:
    moneymaker credentials set --provider alpaca --key api_key --env-var ALPACA_API_KEY
    moneymaker credentials set --provider alpaca --key api_secret --env-var ALPACA_API_SECRET

Alpaca's free tier provides:
  - 15-minute delayed US equity data
  - Unlimited historical daily bars
  - Limited intraday history (varies by subscription)

For futures (ES=F, GC=F) you need a separate futures data subscription.
Alpaca is best suited for US equity strategies (SPY, AAPL, etc.).

Dependencies:
    pip install alpaca-trade-api   # or alpaca-py (newer SDK)
"""

from __future__ import annotations

import datetime as dt
import os
import sys
import time
from typing import Optional

import pandas as pd

from src.accounts import CredentialStore
from src.data_providers.base import DataProvider


_ALPACA_INTERVAL_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "1h": "1Hour",
    "1d": "1Day",
}


class AlpacaDataProvider(DataProvider):
    """Historical and live US equity data via Alpaca Markets Data API v2.

    Caches results to disk under <home>/data_cache/ (parquet, same format
    as YFinanceDataProvider so the rest of the engine is unaffected).
    """

    name = "alpaca"
    is_live = True

    def __init__(self, home: str, credentials: Optional[CredentialStore] = None,
                 cache_ttl_seconds: int = 3600):
        super().__init__(home, credentials)
        self.cache_dir = os.path.join(home, "data_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_ttl_seconds = cache_ttl_seconds
        self._client = None  # lazy-initialised on first use

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from alpaca.data.historical import StockHistoricalDataClient
        except ImportError:
            print(
                "alpaca-py not installed. Run: pip install alpaca-py",
                file=sys.stderr,
            )
            raise
        api_key = self.credentials.get("alpaca", "api_key")
        api_secret = self.credentials.get("alpaca", "api_secret")
        if not api_key or not api_secret:
            raise RuntimeError(
                "Alpaca credentials not configured. Run:\n"
                "  moneymaker credentials set --provider alpaca --key api_key --env-var ALPACA_API_KEY\n"
                "  moneymaker credentials set --provider alpaca --key api_secret --env-var ALPACA_API_SECRET"
            )
        self._client = StockHistoricalDataClient(api_key, api_secret)
        return self._client

    def _cache_path(self, ticker: str, start: str, end: str, interval: str) -> str:
        safe = ticker.replace("=", "_").replace("^", "").replace("/", "_")
        return os.path.join(self.cache_dir, f"alpaca_{safe}_{start}_{end}_{interval}.parquet")

    def get_historical(self, ticker: str, start: str, end: str,
                       interval: str = "1d") -> pd.DataFrame:
        cache_path = self._cache_path(ticker, start, end, interval)
        if os.path.exists(cache_path):
            today = dt.date.today()
            end_date = dt.date.fromisoformat(end)
            cache_age = time.time() - os.path.getmtime(cache_path)
            if end_date < today or cache_age < self.cache_ttl_seconds:
                return pd.read_parquet(cache_path)

        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        alpaca_interval = _ALPACA_INTERVAL_MAP.get(interval)
        if not alpaca_interval:
            raise ValueError(
                f"Unsupported interval '{interval}' for Alpaca. "
                f"Supported: {list(_ALPACA_INTERVAL_MAP)}"
            )

        tf_map = {
            "1Min": TimeFrame(1, TimeFrameUnit.Minute),
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
            "1Day": TimeFrame(1, TimeFrameUnit.Day),
        }
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=tf_map[alpaca_interval],
            start=start,
            end=end,
        )
        client = self._get_client()
        bars = client.get_stock_bars(request).df
        if bars.empty:
            raise ValueError(f"No data returned from Alpaca for {ticker} between {start} and {end}.")

        # Normalise to the same column names as yfinance
        bars = bars.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        })
        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.xs(ticker, level="symbol")
        bars.index = pd.to_datetime(bars.index)

        try:
            bars.to_parquet(cache_path)
        except Exception as e:
            print(f"warning: could not write Alpaca cache ({e})", file=sys.stderr)
        return bars

    def get_last_price(self, ticker: str) -> tuple[float, dt.datetime]:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        client = self._get_client()
        req = StockLatestQuoteRequest(symbol_or_symbols=ticker)
        quote = client.get_stock_latest_quote(req)[ticker]
        price = float((quote.ask_price + quote.bid_price) / 2)
        return price, dt.datetime.now()
