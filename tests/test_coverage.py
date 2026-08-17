"""Tests for data provenance (src/coverage.py)."""

import datetime as dt

import pytest

from src.coverage import TRUSTWORTHY_COVERAGE, Provenance, assess, tick_coverage
from src.ticks import TickStore


@pytest.fixture
def store(tmp_path):
    return TickStore(str(tmp_path))


def record_days(store, ticker, days):
    for d in days:
        store.record(ticker, 100.0 + days.index(d),
                     at=dt.datetime.combine(d, dt.time(12, 0)))


def weekdays(start: dt.date, count: int) -> list[dt.date]:
    out, cur = [], start
    while len(out) < count:
        if cur.weekday() < 5:
            out.append(cur)
        cur += dt.timedelta(days=1)
    return out


def test_weekends_are_not_counted_as_gaps(store):
    """A closed market is not missing data."""
    monday = dt.date(2026, 1, 5)          # a Monday
    sunday = monday + dt.timedelta(days=6)
    cov = tick_coverage(store, "GC=F", monday.isoformat(), sunday.isoformat())
    assert cov["expected"] == 5           # Mon–Fri, not 7


def test_full_coverage_is_trustworthy(store):
    days = weekdays(dt.date(2026, 1, 5), 5)
    record_days(store, "GC=F", days)
    v = assess(store, "GC=F", days[0].isoformat(), days[-1].isoformat())
    assert v["trustworthy"] is True
    assert v["source"] == Provenance.TICKS
    assert v["coverage"]["ratio"] == 1.0


def test_no_ticks_is_refused_and_says_why(store):
    v = assess(store, "GC=F", "2020-01-01", "2020-02-01")
    assert v["trustworthy"] is False
    assert v["source"] == Provenance.PROVIDER
    assert "No ticks recorded" in v["reason"]


def test_partial_coverage_is_reported_as_mixed(store):
    days = weekdays(dt.date(2026, 1, 5), 10)
    record_days(store, "GC=F", days[:3])           # 30% of the window
    v = assess(store, "GC=F", days[0].isoformat(), days[-1].isoformat())
    assert v["trustworthy"] is False
    assert v["source"] == Provenance.MIXED
    assert v["coverage"]["ratio"] < TRUSTWORTHY_COVERAGE
    assert "3 of 10" in v["reason"]


def test_asking_for_provider_bars_is_never_trustworthy(store):
    days = weekdays(dt.date(2026, 1, 5), 5)
    record_days(store, "GC=F", days)               # even with full ticks
    v = assess(store, "GC=F", days[0].isoformat(), days[-1].isoformat(),
               requested="provider")
    assert v["trustworthy"] is False
    assert v["source"] == Provenance.PROVIDER
    assert "indicative only" in v["reason"]


def test_missing_days_are_listed_for_diagnosis(store):
    days = weekdays(dt.date(2026, 1, 5), 5)
    record_days(store, "GC=F", days[:1])
    v = assess(store, "GC=F", days[0].isoformat(), days[-1].isoformat())
    assert days[1].isoformat() in v["coverage"]["missing"]


def test_a_malformed_date_yields_no_coverage_rather_than_raising(store):
    cov = tick_coverage(store, "GC=F", "not-a-date", "also-not")
    assert cov == {"covered": 0, "expected": 0, "ratio": 0.0,
                   "days": [], "missing": []}
