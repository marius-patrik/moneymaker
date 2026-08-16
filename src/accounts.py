"""
Account and credential management.

Credentials are never stored in plaintext by default. You register a
credential one of two ways:

  - by reference (recommended): store only the *name* of an environment
    variable, e.g. CredentialStore.set_ref("trading212_demo", "api_key",
    "T212_API_KEY") — the actual secret lives only in your shell
    environment and never touches disk.
  - by value: CredentialStore.set_value(...) writes the secret itself to
    a file locked to owner-only permissions (chmod 600 on POSIX). Treat
    that file like a password vault — it's still plaintext on disk.

Accounts are a separate, lighter-weight concept: a named (provider,
balance, currency) record you can have many of per provider — e.g. two
different simulated paper accounts with different starting balances, or
(once implemented) multiple real broker accounts. The simulated provider
has full parity with real ones here: same account model, same interface.
"""

from __future__ import annotations

import dataclasses
import json
import os
import stat
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AccountInfo:
    account_id: str
    name: str
    provider: str
    currency: str = "USD"
    balance: float = 0.0
    is_live: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class CredentialStore:
    """Per-provider credential storage under <home>/credentials/credentials.json."""

    def __init__(self, home: str):
        self.path = os.path.join(home, "credentials", "credentials.json")
        if not os.path.exists(self.path):
            self._write({})

    def _read(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path) as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)  # 600, owner read/write only
        except OSError:
            pass  # best-effort; not all filesystems support this (e.g. some Windows setups)

    def set_ref(self, provider: str, key: str, env_var: str) -> None:
        data = self._read()
        data.setdefault(provider, {})[key] = {"type": "env_ref", "env_var": env_var}
        self._write(data)

    def set_value(self, provider: str, key: str, value: str) -> None:
        data = self._read()
        data.setdefault(provider, {})[key] = {"type": "value", "value": value}
        self._write(data)

    def get(self, provider: str, key: str) -> Optional[str]:
        entry = self._read().get(provider, {}).get(key)
        if not entry:
            return None
        if entry["type"] == "env_ref":
            return os.environ.get(entry["env_var"])
        return entry.get("value")

    def has(self, provider: str, key: str) -> bool:
        return self.get(provider, key) is not None

    def list_masked(self) -> dict:
        """Provider -> {key: description}, without ever exposing secret values."""
        out: dict = {}
        for provider, keys in self._read().items():
            out[provider] = {}
            for k, entry in keys.items():
                if entry["type"] == "env_ref":
                    out[provider][k] = f"env:{entry['env_var']}"
                else:
                    out[provider][k] = "****** (stored on disk)"
        return out

    def clear(self, provider: str, key: Optional[str] = None) -> None:
        data = self._read()
        if provider not in data:
            return
        if key is None:
            del data[provider]
        else:
            data[provider].pop(key, None)
        self._write(data)


class AccountManager:
    """
    Multi-account registry, shared across all providers (filter by
    `provider` when listing). For simulated accounts this is the full
    source of truth for balance. For real providers, this is bookkeeping —
    which accounts you've registered and what to call them — while the
    live balance ultimately comes from the broker itself.
    """

    def __init__(self, home: str, ephemeral: bool = False):
        """
        ephemeral=True keeps every account in memory and never touches
        accounts.json. Backtests, grid search and fork-eval each need a
        throwaway account per run purely to hold a balance; persisting those
        buried the real accounts under hundreds of scratch entries.
        """
        self.ephemeral = ephemeral
        self._mem: dict = {}
        self.path = os.path.join(home, "accounts.json")
        if not ephemeral and not os.path.exists(self.path):
            self._write({})

    def _read(self) -> dict:
        if self.ephemeral:
            return self._mem
        if not os.path.exists(self.path):
            return {}
        with open(self.path) as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        if self.ephemeral:
            self._mem = data
            return
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def create(self, name: str, provider: str, currency: str = "USD",
               starting_balance: float = 10000.0, is_live: bool = False,
               metadata: Optional[dict] = None) -> AccountInfo:
        data = self._read()
        account_id = uuid.uuid4().hex[:10]
        info = {
            "account_id": account_id, "name": name, "provider": provider,
            "currency": currency, "balance": starting_balance, "is_live": is_live,
            "metadata": metadata or {},
        }
        data[account_id] = info
        self._write(data)
        return AccountInfo(**info)

    def get(self, account_id: str) -> Optional[AccountInfo]:
        info = self._read().get(account_id)
        return AccountInfo(**info) if info else None

    def list(self, provider: Optional[str] = None) -> list[AccountInfo]:
        out = [AccountInfo(**v) for v in self._read().values()]
        if provider:
            out = [a for a in out if a.provider == provider]
        return out

    def update_balance(self, account_id: str, balance: float) -> None:
        data = self._read()
        if account_id in data:
            data[account_id]["balance"] = balance
            self._write(data)

    def delete(self, account_id: str) -> None:
        data = self._read()
        data.pop(account_id, None)
        self._write(data)

    def prune(self, prefix: str = "mw_", dry_run: bool = True) -> list[AccountInfo]:
        """
        Remove accounts whose name starts with `prefix`.

        Multi-window backtests used to persist one account per window, which
        left hundreds of `mw_*` entries behind. Those runs are now ephemeral,
        so this only has to clean up what earlier versions wrote.

        Returns the accounts matched; with dry_run=True nothing is deleted.
        """
        data = self._read()
        matched = [AccountInfo(**v) for v in data.values()
                   if str(v.get("name", "")).startswith(prefix)]
        if not dry_run and matched:
            for acct in matched:
                data.pop(acct.account_id, None)
            self._write(data)
        return matched
