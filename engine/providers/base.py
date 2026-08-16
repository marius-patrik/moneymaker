"""
Abstracts where fills and account data come from. Every provider —
simulated or real — exposes the same account-aware surface, so the
engine, CLI, and API server never need to know which one is in use.

is_live must be True only for providers that can place real-money orders.
Those are never auto-constructed by make_provider(); wiring one up is
always a deliberate, explicit step done outside the normal helper.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from engine.accounts import AccountInfo, CredentialStore


@dataclass
class OrderResult:
    fill_price: float
    fill_time: dt.datetime
    raw: Optional[dict] = None


class ExecutionProvider(ABC):
    name: str = "base"
    is_live: bool = False

    def __init__(self, home: str, credentials: Optional[CredentialStore] = None):
        self.home = home
        self.credentials = credentials or CredentialStore(home)

    @abstractmethod
    def authenticate(self) -> None:
        """Validate/establish credentials. No-op for the simulated provider."""
        raise NotImplementedError

    @abstractmethod
    def list_accounts(self) -> list[AccountInfo]:
        raise NotImplementedError

    @abstractmethod
    def get_account(self, account_id: str) -> AccountInfo:
        raise NotImplementedError

    @abstractmethod
    def create_account(self, name: str, currency: str = "USD",
                        starting_balance: float = 10000.0) -> AccountInfo:
        raise NotImplementedError

    @abstractmethod
    def execute_order(self, account_id: str, ticker: str, direction: str, size: float,
                       reference_price: float, timestamp: dt.datetime, closing: bool) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def get_account_balance(self, account_id: str) -> float:
        raise NotImplementedError

    def on_trade_closed(self, account_id: str, pnl: float) -> None:
        """
        Optional hook the engine calls after a trade closes. Real
        providers can usually leave this as a no-op — their own balance
        already reflects the fill once the broker processes it. The
        simulated provider overrides this to keep its paper balance
        in sync in real time.
        """
        return None
