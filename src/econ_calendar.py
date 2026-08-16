"""Economic release calendar service (P008).

Provides release dates for macroeconomic data series so that strategies
can gate their activity to actual announcement days rather than trading
on every session.

Three implementations:
  - FREDCalendar: fetches vintage dates from the FRED API (free API key required)
  - BLSCalendar: stub — BLS does not offer a clean machine-readable vintage API
  - SimulatedCalendar: in-memory fixture for unit tests

Named aliases map human-readable release names to (provider, series_id) pairs,
so strategies can write `calendar_series="us_retail_sales"` without hardcoding
a FRED series ID.

Usage:
    # In a strategy:
    from src.econ_calendar import get_calendar
    from src.config import get_home
    cal = get_calendar("us_retail_sales", get_home())
    dates = cal.get_release_dates(start_date, end_date)
    if today not in dates:
        return  # not a release day

    # With a direct FRED series ID:
    cal = get_calendar("RSXFS", get_home())

    # Credentials:
    moneymaker credentials set --provider fred --key api_key --env-var FRED_API_KEY
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Optional

from src.accounts import CredentialStore

# ---------------------------------------------------------------------------
# Alias table: release name -> (provider, series_id)
# ---------------------------------------------------------------------------

RELEASE_ALIASES: dict[str, tuple[str, str]] = {
    "us_retail_sales":      ("fred", "RSXFS"),
    "us_retail_sales_core": ("fred", "RSFS"),
    "us_cpi":               ("fred", "CPIAUCSL"),
    "us_core_cpi":          ("fred", "CPILFESL"),
    "us_pce":               ("fred", "PCE"),
    "us_core_pce":          ("fred", "PCEPILFE"),
    "us_nfp":               ("fred", "PAYEMS"),
    "us_unemployment":      ("fred", "UNRATE"),
    "us_gdp":               ("fred", "GDP"),
    "us_ism_mfg":           ("fred", "NAPM"),
    "us_housing_starts":    ("fred", "HOUST"),
}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class EconCalendar(ABC):
    """Returns a list of dates on which an economic data series was released."""

    @abstractmethod
    def get_release_dates(
        self,
        start: dt.date,
        end: dt.date,
    ) -> list[dt.date]:
        """Return all release dates in [start, end] (inclusive)."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# FRED implementation
# ---------------------------------------------------------------------------

_FRED_BASE = "https://api.stlouisfed.org/fred"


class FREDCalendar(EconCalendar):
    """Release dates via FRED vintage dates API.

    FRED records the exact date each data revision was first published
    (vintage date). For monthly macro series like retail sales, each
    vintage corresponds to one monthly release.

    Requires a free FRED API key:
        moneymaker credentials set --provider fred --key api_key --env-var FRED_API_KEY
    """

    def __init__(self, series_id: str, home: str,
                 credentials: Optional[CredentialStore] = None,
                 cache_ttl_seconds: int = 86400):
        self.series_id = series_id
        self.home = home
        self.credentials = credentials or CredentialStore(home)
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache_dir = os.path.join(home, "calendars")
        os.makedirs(self._cache_dir, exist_ok=True)

    def _cache_path(self) -> str:
        return os.path.join(self._cache_dir, f"fred_{self.series_id}.json")

    def _load_cache(self) -> Optional[list[str]]:
        path = self._cache_path()
        if not os.path.exists(path):
            return None
        age = time.time() - os.path.getmtime(path)
        if age > self.cache_ttl_seconds:
            return None
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get("vintage_dates")
        except (json.JSONDecodeError, KeyError):
            return None

    def _save_cache(self, dates: list[str]) -> None:
        with open(self._cache_path(), "w") as f:
            json.dump({"series_id": self.series_id, "vintage_dates": dates,
                       "cached_at": dt.datetime.now().isoformat()}, f)

    def _fetch_from_fred(self) -> list[str]:
        try:
            import urllib.request
            import urllib.parse
        except ImportError:
            raise RuntimeError("urllib not available — cannot reach FRED API")

        api_key = self.credentials.get("fred", "api_key")
        if not api_key:
            raise RuntimeError(
                "FRED API key not configured. Run:\n"
                "  moneymaker credentials set --provider fred --key api_key --env-var FRED_API_KEY\n"
                "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
            )

        params = urllib.parse.urlencode({
            "series_id": self.series_id,
            "api_key": api_key,
            "file_type": "json",
            "realtime_start": "1990-01-01",
        })
        url = f"{_FRED_BASE}/series/vintagedates?{params}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return data.get("vintage_dates", [])

    def get_release_dates(self, start: dt.date, end: dt.date) -> list[dt.date]:
        all_dates = self._load_cache()
        if all_dates is None:
            all_dates = self._fetch_from_fred()
            self._save_cache(all_dates)
        return [
            dt.date.fromisoformat(d)
            for d in all_dates
            if start <= dt.date.fromisoformat(d) <= end
        ]


# ---------------------------------------------------------------------------
# BLS stub
# ---------------------------------------------------------------------------

class BLSCalendar(EconCalendar):
    """BLS release calendar — stub.

    BLS does not provide a machine-readable vintage date API comparable to
    FRED. A full implementation would scrape https://www.bls.gov/schedule/
    or use a third-party calendar source. For now, this stub raises a
    NotImplementedError to make the missing implementation visible.

    Workaround: use FREDCalendar for BLS-tracked series (many are mirrored
    on FRED with the same vintage dates), or use SimulatedCalendar with a
    manually curated list.
    """

    def __init__(self, series_id: str, home: str, **kwargs):
        self.series_id = series_id

    def get_release_dates(self, start: dt.date, end: dt.date) -> list[dt.date]:
        raise NotImplementedError(
            f"BLSCalendar is not yet implemented for series '{self.series_id}'. "
            f"Use FREDCalendar with an equivalent FRED series ID, or "
            f"SimulatedCalendar with a manually curated date list."
        )


# ---------------------------------------------------------------------------
# Simulated (fixture) implementation
# ---------------------------------------------------------------------------

class SimulatedCalendar(EconCalendar):
    """In-memory calendar for unit tests.

    Pass a list of date objects or ISO strings as the fixture.

    Example:
        import datetime as dt
        cal = SimulatedCalendar(["2026-01-17", "2026-02-21", "2026-03-14"])
        dates = cal.get_release_dates(dt.date(2026, 1, 1), dt.date(2026, 4, 1))
        # -> [date(2026, 1, 17), date(2026, 2, 21), date(2026, 3, 14)]
    """

    def __init__(self, dates: list, **kwargs):
        self._dates = [
            dt.date.fromisoformat(d) if isinstance(d, str) else d
            for d in dates
        ]

    def get_release_dates(self, start: dt.date, end: dt.date) -> list[dt.date]:
        return [d for d in self._dates if start <= d <= end]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_PROVIDER_MAP: dict[str, type] = {
    "fred": FREDCalendar,
    "bls": BLSCalendar,
    "simulated": SimulatedCalendar,
}


def get_calendar(
    series_or_alias: str,
    home: str,
    credentials: Optional[CredentialStore] = None,
) -> EconCalendar:
    """Return an EconCalendar for the given series ID or named alias.

    Aliases (e.g. "us_retail_sales") are resolved via RELEASE_ALIASES.
    Direct FRED series IDs (e.g. "RSXFS") default to FREDCalendar.
    Prefix with "bls:" or "simulated:" to force a specific provider.

    Examples:
        get_calendar("us_retail_sales", home)      # alias → FRED RSXFS
        get_calendar("RSXFS", home)                # direct FRED series
        get_calendar("bls:CES0000000001", home)    # explicit BLS
    """
    if ":" in series_or_alias:
        provider_name, series_id = series_or_alias.split(":", 1)
    elif series_or_alias in RELEASE_ALIASES:
        provider_name, series_id = RELEASE_ALIASES[series_or_alias]
    else:
        # Assume it's a raw FRED series ID
        provider_name, series_id = "fred", series_or_alias

    cls = _PROVIDER_MAP.get(provider_name)
    if not cls:
        raise ValueError(
            f"Unknown calendar provider '{provider_name}'. "
            f"Available: {list(_PROVIDER_MAP)}"
        )
    return cls(series_id=series_id, home=home, credentials=credentials)
