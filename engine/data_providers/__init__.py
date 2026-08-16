"""Market data provider registry and factory.

Separate from execution providers (engine/providers/): data providers supply
price history and live quotes; execution providers handle order fills and
account management.

Usage:
    from engine.data_providers import make_data_provider, DATA_PROVIDERS
    provider = make_data_provider("yfinance", home)
    df = provider.get_historical("AAPL", "2026-01-01", "2026-02-01", interval="1d")
"""

from __future__ import annotations

from engine.data_providers.alpaca import AlpacaDataProvider
from engine.data_providers.csv_provider import CSVDataProvider
from engine.data_providers.simulated import SimulatedDataProvider
from engine.data_providers.yfinance_provider import YFinanceDataProvider

DATA_PROVIDERS: dict[str, type] = {
    "yfinance": YFinanceDataProvider,
    "alpaca": AlpacaDataProvider,
    "csv": CSVDataProvider,
    "simulated": SimulatedDataProvider,
}


def make_data_provider(name: str, home: str, **kwargs):
    """Instantiate a data provider by name."""
    cls = DATA_PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown data provider '{name}'. Available: {list(DATA_PROVIDERS)}")
    return cls(home=home, **kwargs)
