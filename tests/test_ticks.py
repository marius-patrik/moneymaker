"""Tests for the tick recorder (src/ticks.py)."""

import datetime as dt
import json
import pathlib

import pytest

from src.ticks import TickStore


@pytest.fixture
def store(tmp_path):
    return TickStore(str(tmp_path))


def test_a_repeated_price_is_not_recorded_twice(store):
    """A polled feed repeats itself between trades; only moves are ticks."""
    assert store.record("GC=F", 100.0) is True
    assert store.record("GC=F", 100.0) is False
    assert store.record("GC=F", 100.5) is True
    assert len(store.read("GC=F")) == 2


def test_none_and_nan_are_ignored(store):
    assert store.record("GC=F", None) is False       # type: ignore[arg-type]
    assert store.record("GC=F", float("nan")) is False
    assert store.read("GC=F") == []


def test_instruments_with_awkward_symbols_get_safe_filenames(store, tmp_path):
    store.record("BRK.B", 1.0)
    store.record("^GSPC", 2.0)
    store.record("EURUSD=X", 3.0)
    names = {p.name for p in (tmp_path / "ticks").iterdir()}
    assert names == {"BRK_B", "_GSPC", "EURUSD_X"}
    assert len(store.instruments()) == 3


def test_a_corrupt_line_does_not_poison_the_read(store, tmp_path):
    store.record("GC=F", 100.0)
    path = tmp_path / "ticks" / "GC_F" / f"{dt.date.today().isoformat()}.jsonl"
    with open(path, "a") as f:
        f.write("{not json\n")           # a half-written final line
    assert len(store.read("GC=F")) == 1


def test_ticks_aggregate_into_ohlc_candles(store):
    base = dt.datetime(2026, 1, 1, 12, 0, 0)
    for i, price in enumerate([100.0, 102.0, 99.0, 101.0]):
        store.record("GC=F", price, at=base + dt.timedelta(seconds=i * 10))

    bars = store.candles("GC=F", base.date(), seconds=60)
    assert len(bars) == 1
    bar = bars[0]
    assert bar["open"] == 100.0
    assert bar["high"] == 102.0
    assert bar["low"] == 99.0
    assert bar["close"] == 101.0


def test_candles_split_across_buckets(store):
    base = dt.datetime(2026, 1, 1, 12, 0, 0)
    store.record("GC=F", 100.0, at=base)
    store.record("GC=F", 105.0, at=base + dt.timedelta(seconds=70))
    assert len(store.candles("GC=F", base.date(), seconds=60)) == 2


def test_enrolling_is_idempotent_and_persists(store, tmp_path):
    assert store.enroll("GC=F") is True
    assert store.enroll("GC=F") is False          # already following it
    assert store.enroll("ES=F") is True
    assert store.enrolled() == ["ES=F", "GC=F"]
    assert json.loads((tmp_path / "tick_watch.json").read_text()) == ["ES=F", "GC=F"]


def test_record_batch_counts_only_the_ones_that_moved(store):
    assert store.record_batch({"A": 1.0, "B": 2.0}) == 2
    assert store.record_batch({"A": 1.0, "B": 2.5}) == 1     # only B moved


def test_stats_reports_what_was_captured(store):
    store.record("GC=F", 1.0)
    store.record("GC=F", 2.0)
    store.record("ES=F", 1.0)
    s = store.stats()
    assert s["instruments"] == 2
    assert s["ticks"] == 3
    assert s["per_instrument"]["GC_F"] == 2


def test_reading_an_unrecorded_instrument_is_empty_not_an_error(store):
    assert store.read("NEVER") == []
    assert store.candles("NEVER") == []
    assert store.days("NEVER") == []
