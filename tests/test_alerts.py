"""Tests for price alerts (src/alerts.py)."""

import pytest

from src.alerts import AlertStore, has_fired


def alert(level, condition, **kw):
    return {"level": level, "condition": condition, **kw}


@pytest.fixture
def store(tmp_path):
    return AlertStore(str(tmp_path))


# ----------------------------------------------------------------- firing

@pytest.mark.parametrize("price,expected", [(101, True), (100, True), (99, False)])
def test_above_fires_at_or_over_the_level(price, expected):
    assert has_fired(alert(100, "above"), price, None) is expected


@pytest.mark.parametrize("price,expected", [(99, True), (100, True), (101, False)])
def test_below_fires_at_or_under_the_level(price, expected):
    assert has_fired(alert(100, "below"), price, None) is expected


def test_crosses_needs_a_previous_price():
    """Without one, a level between polls would never fire or always fire."""
    assert has_fired(alert(100, "crosses"), 101, None) is False


def test_crosses_fires_in_both_directions():
    a = alert(100, "crosses")
    assert has_fired(a, 101, 99) is True      # upward through
    assert has_fired(a, 99, 101) is True      # downward through


def test_crosses_does_not_refire_while_it_stays_past_the_level():
    a = alert(100, "crosses")
    assert has_fired(a, 102, 101) is False


def test_unknown_condition_is_rejected():
    with pytest.raises(ValueError):
        has_fired(alert(100, "vibes"), 100, None)


# ------------------------------------------------------------------ store

def test_creating_validates_its_input(store):
    with pytest.raises(ValueError):
        store.create(ticker="X", level=100, condition="sideways")
    with pytest.raises(ValueError):
        store.create(ticker="X", level=0, condition="above")


def test_a_one_shot_alert_disarms_itself(store):
    store.create(ticker="GC=F", level=100, condition="above")
    assert len(store.check({"GC=F": 101})) == 1
    assert store.armed() == []
    assert store.list()[0]["status"] == "fired"


def test_a_repeating_alert_stays_armed(store):
    store.create(ticker="GC=F", level=100, condition="above", repeat=True)
    assert len(store.check({"GC=F": 101})) == 1
    assert len(store.armed()) == 1
    assert len(store.check({"GC=F": 102})) == 1     # fires again


def test_firing_records_the_price_that_did_it(store):
    store.create(ticker="GC=F", level=100, condition="above")
    fired = store.check({"GC=F": 137.5})[0]
    assert fired["fired_price"] == 137.5
    assert fired["fired_at"]


def test_an_instrument_with_no_price_is_skipped(store):
    store.create(ticker="GC=F", level=100, condition="above")
    assert store.check({"ES=F": 9999}) == []
    assert len(store.armed()) == 1


def test_rearming_clears_the_fired_state(store):
    a = store.create(ticker="GC=F", level=100, condition="above")
    store.check({"GC=F": 101})
    rearmed = store.rearm(a["id"])
    assert rearmed["status"] == "armed"
    assert rearmed["fired_price"] is None


def test_deleting_and_rearming_unknown_alerts_raise(store):
    with pytest.raises(KeyError):
        store.delete("nope")
    with pytest.raises(KeyError):
        store.rearm("nope")


def test_listing_can_exclude_fired_alerts(store):
    store.create(ticker="GC=F", level=100, condition="above")
    store.create(ticker="ES=F", level=100, condition="above")
    store.check({"GC=F": 101})
    assert len(store.list()) == 2
    assert len(store.list(include_fired=False)) == 1
    assert len(store.list(ticker="ES=F")) == 1
