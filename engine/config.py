"""Filesystem-first configuration: resolves the data home directory.

Everything the engine persists (strategies, sessions, cached price data,
accounts, credentials) lives under one directory, default ~/.moneymaker.
Override with --data-dir on the CLI or the MONEYMAKER_HOME env var.
"""

from __future__ import annotations

import os
from typing import Optional


def get_home(cli_override: Optional[str] = None) -> str:
    home = cli_override or os.environ.get("MONEYMAKER_HOME") or os.path.expanduser("~/.moneymaker")
    for sub in ("strategies", "sessions", "data_cache", "credentials"):
        os.makedirs(os.path.join(home, sub), exist_ok=True)
    from engine.installer import check_version
    check_version(home)
    return home
