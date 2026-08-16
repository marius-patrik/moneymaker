"""
Default provider — no broker involved anywhere. Simulates fills against
the reference price with configurable slippage, and has full parity with
real providers on the account surface: multiple named paper accounts,
each with its own tracked balance, creatable/listable the same way a real
provider's accounts would be.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from src.accounts import AccountInfo, AccountManager, CredentialStore
from src.providers.base import ExecutionProvider, OrderResult


class SimulatedExecutionProvider(ExecutionProvider):
    """
    Default provider — no broker involved anywhere. Simulates fills against
    the reference price with configurable slippage, and has full parity with
    real providers on the account surface: multiple named paper accounts,
    each with its own tracked balance, creatable/listable the same way a
    real provider's accounts would be.
    """
    name = "simulated"
    is_live = False

    def __init__(self, home: str, credentials: Optional[CredentialStore] = None,
                 slippage_pct: float = 0.0005, ephemeral: bool = False):
        super().__init__(home, credentials)
        self.slippage_pct = slippage_pct
        # ephemeral=True: scratch accounts stay in memory (see AccountManager).
        self.accounts = AccountManager(home, ephemeral=ephemeral)

    def authenticate(self) -> None:
        return None  # nothing to authenticate — there's no broker here

    def list_accounts(self) -> list[AccountInfo]:
        accts = self.accounts.list(provider=self.name)
        if not accts:
            # first-run convenience: auto-create one default paper account
            accts = [self.create_account("default")]
        return accts

    def get_account(self, account_id: str) -> AccountInfo:
        info = self.accounts.get(account_id)
        if not info or info.provider != self.name:
            raise ValueError(f"No simulated account with id {account_id}")
        return info

    def create_account(self, name: str, currency: str = "USD",
                        starting_balance: float = 10000.0) -> AccountInfo:
        return self.accounts.create(name, self.name, currency=currency,
                                     starting_balance=starting_balance, is_live=False)

    def execute_order(self, account_id: str, ticker: str, direction: str, size: float,
                       reference_price: float, timestamp: dt.datetime, closing: bool) -> OrderResult:
        self.get_account(account_id)  # raises if the account doesn't exist
        adverse = self.slippage_pct
        if (direction == "long" and not closing) or (direction == "short" and closing):
            fill = reference_price * (1 + adverse)
        else:
            fill = reference_price * (1 - adverse)
        return OrderResult(fill_price=fill, fill_time=timestamp)

    def get_account_balance(self, account_id: str) -> float:
        return self.get_account(account_id).balance

    def on_trade_closed(self, account_id: str, pnl: float) -> None:
        info = self.get_account(account_id)
        self.accounts.update_balance(account_id, info.balance + pnl)
