"""
STUB — order execution and account listing are not implemented.

Interactive Brokers supports CFDs and has a real paper-trading environment
via TWS/IB Gateway.

To implement:
  1. Run TWS or IB Gateway locally in paper-trading mode.
  2. `pip install ib_insync` and connect: `ib_insync.IB().connect('127.0.0.1', 7497, clientId=1)`
     (7497 is TWS paper port, 4002 is IB Gateway paper port — no API secret
     needed since auth happens through the running desktop app, but note
     host/port as "credentials" so multiple installs/accounts are configurable).
  3. Implement list_accounts()/get_account() via `ib.managedAccounts()` +
     `ib.accountSummary()`.
  4. Implement execute_order() as `ib.placeOrder(contract, MarketOrder(...))`,
     using ib_insync's qualifyContracts() to resolve the ticker first.
  5. Implement get_account_balance() from the NetLiquidation value in
     accountSummary().
"""

from __future__ import annotations

import datetime as dt

from moneymaker.accounts import AccountInfo
from moneymaker.providers.base import ExecutionProvider, OrderResult

REQUIRED_CREDENTIALS = ["host", "port"]


class IBKRPaperProvider(ExecutionProvider):
    """
    STUB — order execution and account listing are not implemented.
    Interactive Brokers supports CFDs and has a real paper-trading
    environment via TWS/IB Gateway. See module docstring for what's
    needed to wire this up.
    """
    name = "ibkr_paper"
    is_live = False

    def authenticate(self) -> None:
        missing = [k for k in REQUIRED_CREDENTIALS if not self.credentials.has(self.name, k)]
        if missing:
            raise RuntimeError(
                f"Missing config for {self.name}: {missing} (host/port of your running "
                f"TWS or IB Gateway paper instance). See module docstring."
            )
        raise NotImplementedError(f"{self.name} is a stub — see module docstring for what's left to wire up.")

    def list_accounts(self) -> list[AccountInfo]:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def get_account(self, account_id: str) -> AccountInfo:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def create_account(self, name: str, currency: str = "USD",
                        starting_balance: float = 10000.0) -> AccountInfo:
        raise NotImplementedError(
            f"{self.name} can't create broker accounts via API — set up the paper "
            "account through IBKR directly, then register it manually. See module docstring."
        )

    def execute_order(self, account_id: str, ticker: str, direction: str, size: float,
                       reference_price: float, timestamp: dt.datetime, closing: bool) -> OrderResult:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")

    def get_account_balance(self, account_id: str) -> float:
        raise NotImplementedError(f"{self.name} is a stub — see module docstring.")
