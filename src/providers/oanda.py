"""
STUB — order execution and account listing are not implemented.

OANDA has a clean REST API and a real practice (paper) environment for
forex/CFDs.

To implement:
  1. Create an OANDA practice account + API token at
     https://www.oanda.com/demo-account/tpa/personal_token
  2. Register it: CredentialStore.set_ref("oanda_practice", "api_token", "OANDA_API_TOKEN")
     then `export OANDA_API_TOKEN=...`.
  3. Implement list_accounts()/get_account() as a GET to
     https://api-fxpractice.oanda.com/v3/accounts.
  4. Implement execute_order() as a POST to
     https://api-fxpractice.oanda.com/v3/accounts/{id}/orders.
  5. Implement get_account_balance() from GET /v3/accounts/{id}/summary,
     the "balance" field.
"""

from __future__ import annotations

import datetime as dt

from src.accounts import AccountInfo
from src.providers.base import ExecutionProvider, OrderResult

REQUIRED_CREDENTIALS = ["api_token"]


class OANDAPracticeProvider(ExecutionProvider):
    """
    STUB — order execution and account listing are not implemented.
    OANDA has a clean REST API and a real practice (paper) environment
    for forex/CFDs. See module docstring for what's needed to wire
    this up.
    """
    name = "oanda_practice"
    is_live = False

    def authenticate(self) -> None:
        missing = [k for k in REQUIRED_CREDENTIALS if not self.credentials.has(self.name, k)]
        if missing:
            raise RuntimeError(
                f"Missing credentials for {self.name}: {missing}. "
                f"Register with CredentialStore.set_ref/set_value first. See module docstring."
            )
        raise NotImplementedError(f"{self.name} is a stub — see module docstring for what's left to wire up.")

    def list_accounts(self) -> list[AccountInfo]:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def get_account(self, account_id: str) -> AccountInfo:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def create_account(self, name: str, currency: str = "USD",
                        starting_balance: float = 10000.0) -> AccountInfo:
        raise NotImplementedError(
            f"{self.name} can't create broker accounts via API — create the practice "
            "account on OANDA's site, then register it manually. See module docstring."
        )

    def execute_order(self, account_id: str, ticker: str, direction: str, size: float,
                       reference_price: float, timestamp: dt.datetime, closing: bool) -> OrderResult:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def get_account_balance(self, account_id: str) -> float:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")
