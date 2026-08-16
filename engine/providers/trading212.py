"""
STUB — order execution and account listing are not implemented.

Trading 212's official Public API only covers Invest/ISA (equity)
accounts, not CFD accounts (confirmed Aug 2026) — so this can only ever
place equity/ETF orders on T212's demo environment, not a CFD, and can't
reach a live CFD account through this API at all.

To implement:
  1. Generate an API key in the T212 app (Settings > API).
  2. Register it: CredentialStore.set_ref("trading212_demo", "api_key", "T212_API_KEY")
     then `export T212_API_KEY=...` — or set_value() to store it directly.
  3. Implement list_accounts()/get_account() as a GET to
     https://demo.trading212.com/api/v0/equity/account/info + /cash.
  4. Implement execute_order() as a POST to
     https://demo.trading212.com/api/v0/equity/orders/market
     (quantity positive to buy, negative to sell).
  5. Implement get_account_balance() from the /cash endpoint's
     availableToTrade field.
"""

from __future__ import annotations

import datetime as dt

from engine.accounts import AccountInfo
from engine.providers.base import ExecutionProvider, OrderResult

REQUIRED_CREDENTIALS = ["api_key"]


class Trading212DemoProvider(ExecutionProvider):
    """
    STUB — order execution and account listing are not implemented.
    Trading 212's official Public API only covers Invest/ISA (equity)
    accounts, not CFD accounts. See module docstring for what's needed
    to wire this up.
    """
    name = "trading212_demo"
    is_live = False

    def authenticate(self) -> None:
        missing = [k for k in REQUIRED_CREDENTIALS if not self.credentials.has(self.name, k)]
        if missing:
            raise RuntimeError(
                f"Missing credentials for {self.name}: {missing}. "
                f"Register with CredentialStore.set_ref/set_value first. See module docstring."
            )
        # Credentials are present. Actually validating them against T212's
        # API is not implemented — see module docstring.
        raise NotImplementedError(f"{self.name} is a stub — see module docstring for what's left to wire up.")

    def list_accounts(self) -> list[AccountInfo]:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def get_account(self, account_id: str) -> AccountInfo:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def create_account(self, name: str, currency: str = "USD",
                        starting_balance: float = 10000.0) -> AccountInfo:
        raise NotImplementedError(
            f"{self.name} can't create broker accounts via API — create the demo "
            "account in the T212 app, then register it manually. See module docstring."
        )

    def execute_order(self, account_id: str, ticker: str, direction: str, size: float,
                       reference_price: float, timestamp: dt.datetime, closing: bool) -> OrderResult:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def get_account_balance(self, account_id: str) -> float:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")
