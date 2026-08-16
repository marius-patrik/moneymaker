"""Filesystem-first configuration: resolves the data home directory.

Everything the engine persists (strategies, sessions, cached price data,
accounts, credentials) lives under one directory.

Resolution order, first match wins:
  1. --data-dir on the CLI
  2. MONEYMAKER_HOME in the environment
  3. `home` in the user preference file (settable from the web UI)
  4. .data/ beside the repository root

~/.moneymaker is not a fallback — point one of the above at it if you want a
data directory shared across clones.
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Optional

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_DEFAULT_HOME = str(_REPO_ROOT / ".data")

# Kept outside the data directory on purpose: it records *where* that
# directory is, so storing it inside would be circular.
PREFS_PATH = pathlib.Path.home() / ".config" / "moneymaker" / "config.json"

SUBDIRS = ("strategies", "sessions", "data_cache", "credentials",
           "evaluations", "calendars")


def read_prefs() -> dict:
    try:
        return json.loads(PREFS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_prefs(prefs: dict) -> None:
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(prefs, indent=2))


def set_home_preference(home: str) -> str:
    """
    Persist the data directory the app should use on next start.

    Returns the expanded path. The running process keeps its current home —
    swapping it live would leave open handles and half-read state pointing at
    the old location — so callers should tell the user to restart.
    """
    expanded = str(pathlib.Path(home).expanduser())
    prefs = read_prefs()
    prefs["home"] = expanded
    write_prefs(prefs)
    return expanded


def resolve_home(cli_override: Optional[str] = None) -> str:
    """Where the data directory is, without creating anything."""
    return (cli_override
            or os.environ.get("MONEYMAKER_HOME")
            or read_prefs().get("home")
            or _DEFAULT_HOME)


def home_source(cli_override: Optional[str] = None) -> str:
    """Which of the four sources supplied the current home — for the UI."""
    if cli_override:
        return "--data-dir"
    if os.environ.get("MONEYMAKER_HOME"):
        return "MONEYMAKER_HOME"
    if read_prefs().get("home"):
        return "preference"
    return "default"


def get_home(cli_override: Optional[str] = None) -> str:
    home = resolve_home(cli_override)
    for sub in SUBDIRS:
        os.makedirs(os.path.join(home, sub), exist_ok=True)
    from src.installer import check_version
    check_version(home)
    return home
