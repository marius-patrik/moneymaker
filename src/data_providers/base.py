"""DataProvider abstract base class.

A DataProvider supplies price history (and optionally live quotes) for a
given ticker symbol. It is deliberately separate from ExecutionProvider
(which handles order fills) so that data sourcing and trade execution can
be mixed and matched independently.

Implementing a new provider:
  1. Subclass DataProvider.
  2. Set `name` and `is_live` (True if the provider can stream real-time
     quotes via get_last_price).
  3. Implement get_historical(). Optionally override get_last_price().
  4. Register in engine/data_providers/__init__.py.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from src.accounts import CredentialStore


class DataProvider(ABC):
    """Abstract base for all market data providers."""

    name: str = "base"
    is_live: bool = False  # True if get_last_price() is implemented

    def __init__(self, home: str, credentials: Optional[CredentialStore] = None):
        self.home = home
        self.credentials = credentials or CredentialStore(home)

    @abstractmethod
    def get_historical(
        self,
        ticker: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Return an OHLCV DataFrame indexed by timezone-aware datetime.

        Columns must include at least 'Close' and optionally 'Open', 'High',
        'Low', 'Volume'. The engine only requires 'Close' and 'Volume'.
        """
        raise NotImplementedError

    def get_last_price(self, ticker: str) -> tuple[float, dt.datetime]:
        """Return (price, timestamp) for live polling.

        Only required for live-mode providers (is_live = True). Raises
        NotImplementedError for batch-only providers like CSV.
        """
        raise NotImplementedError(
            f"Data provider '{self.name}' does not support live price feeds. "
            f"Use a provider with is_live=True for live mode."
        )
