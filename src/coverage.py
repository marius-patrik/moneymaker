"""Data provenance and coverage.

A backtest is only as honest as the prices it ran on. Provider bars are
revised after the fact, arrive delayed, and are aggregated by someone else —
so a fill "at the low of the bar" may be a price that never traded when we
were watching. Recorded ticks are what we actually observed.

This module answers one question: for a given instrument and window, do we
have our own ticks, and how much of it do they cover? The engine refuses to
report a result as trustworthy without them.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

# Below this, a window has so little of its own data that a backtest over it
# is provider fiction with a few real prices sprinkled in.
TRUSTWORTHY_COVERAGE = 0.95


class Provenance:
    """Where a backtest's prices came from, and whether to believe it."""

    TICKS = "ticks"          # our own recording — trustworthy
    PROVIDER = "provider"    # someone else's aggregated bars
    MIXED = "mixed"          # ticks where we have them, bars elsewhere


def _day_span(start: dt.date, end: dt.date) -> list[dt.date]:
    days, cur = [], start
    while cur <= end:
        days.append(cur)
        cur += dt.timedelta(days=1)
    return days


def tick_coverage(store, ticker: str, start: str, end: str) -> dict:
    """
    How much of [start, end] we hold our own ticks for.

    Coverage is measured in days with any recording rather than in seconds,
    because a market is closed most of the time and demanding continuous
    ticks would report every weekend as a gap.
    """
    try:
        s = dt.date.fromisoformat(start[:10])
        e = dt.date.fromisoformat(end[:10])
    except ValueError:
        return {"covered": 0, "expected": 0, "ratio": 0.0, "days": [], "missing": []}

    recorded = set(store.days(ticker))
    # Weekends are not gaps — no market, no ticks, nothing missing.
    wanted = [d for d in _day_span(s, e) if d.weekday() < 5]
    have = [d.isoformat() for d in wanted if d.isoformat() in recorded]
    missing = [d.isoformat() for d in wanted if d.isoformat() not in recorded]

    return {
        "covered": len(have),
        "expected": len(wanted),
        "ratio": round(len(have) / len(wanted), 4) if wanted else 0.0,
        "days": have,
        "missing": missing[:30],       # enough to see the shape of the gap
    }


def assess(store, ticker: str, start: str, end: str,
           requested: str = "ticks") -> dict:
    """
    Whether a backtest over this window can be trusted, and why not.

    `requested` is what the caller asked to run on. Asking for ticks and not
    having them is a refusal, not a silent downgrade — a result quietly
    computed from provider bars is worse than no result, because it looks
    identical to a real one.
    """
    cov = tick_coverage(store, ticker, start, end)
    enough = cov["ratio"] >= TRUSTWORTHY_COVERAGE

    if requested == "provider":
        return {
            "source": Provenance.PROVIDER,
            "trustworthy": False,
            "coverage": cov,
            "reason": ("Provider bars are aggregated elsewhere, revised after the "
                       "fact, and delayed. Results are indicative only."),
        }

    if enough:
        return {
            "source": Provenance.TICKS,
            "trustworthy": True,
            "coverage": cov,
            "reason": "",
        }

    if cov["covered"] == 0:
        reason = (f"No ticks recorded for {ticker} in this window. Recording starts "
                  f"when an instrument is charted, traded or backtested — so this "
                  f"window predates it.")
    else:
        reason = (f"Only {cov['covered']} of {cov['expected']} trading days have "
                  f"ticks ({cov['ratio']:.0%}). Below {TRUSTWORTHY_COVERAGE:.0%} the "
                  f"gaps would be filled with provider bars, which is what this "
                  f"check exists to prevent.")

    return {
        "source": Provenance.MIXED if cov["covered"] else Provenance.PROVIDER,
        "trustworthy": False,
        "coverage": cov,
        "reason": reason,
    }
