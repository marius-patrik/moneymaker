"""Filesystem-first configuration: resolves the data home directory.

Everything the engine persists (strategies, sessions, cached price data,
accounts, credentials) lives under one directory.

Default: .data/ next to the repository root (i.e., sibling of src/).
Override with --data-dir on the CLI or the MONEYMAKER_HOME env var.
~/.moneymaker is no longer a fallback — set MONEYMAKER_HOME explicitly if
you want a shared data directory across clones.
"""

from __future__ import annotations

import os
import pathlib
from typing import Optional

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_DEFAULT_HOME = str(_REPO_ROOT / ".data")


def get_home(cli_override: Optional[str] = None) -> str:
    home = cli_override or os.environ.get("MONEYMAKER_HOME") or _DEFAULT_HOME
    for sub in ("strategies", "sessions", "data_cache", "credentials", "evaluations", "calendars"):
        os.makedirs(os.path.join(home, sub), exist_ok=True)
    from src.installer import check_version
    check_version(home)
    return home
