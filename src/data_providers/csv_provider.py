"""CSV/Parquet file data provider — load price history from local files.

Use this to import data from a broker export, Norgate, Quandl CSV, or any
other source. The file must have a datetime index and at least a 'Close'
column; 'Open', 'High', 'Low', 'Volume' are optional but passed through
if present.

Usage (CLI):
    moneymaker backtest --data-provider csv \\
        --data-provider-path /path/to/ES_F_2026.csv \\
        --ticker ES=F ...

Usage (Python):
    provider = CSVDataProvider(home, path="/path/to/data.csv")
    df = provider.get_historical("ES=F", "2026-01-01", "2026-03-01")
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Optional

import pandas as pd

from src.accounts import CredentialStore
from src.data_providers.base import DataProvider


class CSVDataProvider(DataProvider):
    """Load OHLCV data from a local CSV or Parquet file.

    The file path can be supplied at construction time (for programmatic use)
    or via the --data-provider-path CLI flag (stored in self.path).
    """

    name = "csv"
    is_live = False

    def __init__(self, home: str, credentials: Optional[CredentialStore] = None,
                 path: Optional[str] = None):
        super().__init__(home, credentials)
        self.path = path

    def get_historical(self, ticker: str, start: str, end: str,
                       interval: str = "1d") -> pd.DataFrame:
        if not self.path:
            raise ValueError(
                "CSVDataProvider requires a file path. "
                "Pass path= at construction or --data-provider-path on the CLI."
            )
        if not os.path.exists(self.path):
            raise FileNotFoundError(f"Data file not found: {self.path}")

        if self.path.endswith(".parquet"):
            df = pd.read_parquet(self.path)
        else:
            df = pd.read_csv(self.path, index_col=0, parse_dates=True)

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        if "Close" not in df.columns:
            raise ValueError(
                f"CSV file must have a 'Close' column. Found: {list(df.columns)}"
            )

        start_dt = pd.Timestamp(start)
        end_dt = pd.Timestamp(end)
        mask = (df.index >= start_dt) & (df.index < end_dt)
        result = df.loc[mask].copy()

        if result.empty:
            raise ValueError(
                f"No data in {self.path} for {ticker} between {start} and {end}."
            )
        return result
