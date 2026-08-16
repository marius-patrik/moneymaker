"""Historical and live price data via yfinance, with disk caching."""

from __future__ import annotations

import datetime as dt
import os
import sys

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("Missing dependency. Run: pip install -r requirements.txt", file=sys.stderr)
    raise


class DataFeed:
    """Fetches historical or live price bars for any ticker via yfinance.
    Historical pulls are cached to disk (parquet) under <home>/data_cache/."""

    def __init__(self, home: str):
        self.home = home
        self.cache_dir = os.path.join(home, "data_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_path(self, ticker: str, start: str, end: str, interval: str) -> str:
        safe_ticker = ticker.replace("=", "_").replace("^", "").replace("/", "_")
        fname = f"{safe_ticker}_{start}_{end}_{interval}.parquet"
        return os.path.join(self.cache_dir, fname)

    def get_historical(self, ticker: str, start: str, end: str, interval: str = "5m",
                        use_cache: bool = True) -> pd.DataFrame:
        cache_path = self._cache_path(ticker, start, end, interval)
        if use_cache and os.path.exists(cache_path):
            try:
                return pd.read_parquet(cache_path)
            except Exception:
                pass  # cache corrupt, fall through and re-fetch

        df = yf.download(ticker, start=start, end=end, interval=interval, progress=False)
        if df.empty:
            raise ValueError(
                f"No data returned for {ticker} between {start} and {end} "
                f"(interval={interval}). Intraday intervals are only available "
                f"for roughly the last 60 days — use a daily interval for older ranges."
            )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)

        try:
            df.to_parquet(cache_path)
        except Exception as e:
            print(f"warning: could not write cache ({e})", file=sys.stderr)
        return df

    @staticmethod
    def get_last_price(ticker: str) -> tuple[float, dt.datetime]:
        t = yf.Ticker(ticker)
        fast = t.fast_info
        price = float(fast["last_price"])
        return price, dt.datetime.now()
