"""Tests for resting orders (src/orders.py)."""

import pytest

from src.orders import OrderBook, fill_price_for, is_triggered


def order(kind, side, trigger, **kw):
    return {"type": kind, "direction": side, "trigger_price": trigger, **kw}


# ---------------------------------------------------------------- triggers

@pytest.mark.parametrize("side,trigger,price,expected", [
    ("long", 100, 99, True),     # buy limit waits for the market to come down
    ("long", 100, 100, True),    # touching the limit is marketable
    ("long", 100, 101, False),
    ("short", 100, 101, True),   # sell limit waits for the market to come up
    ("short", 100, 99, False),
])
def test_limit_triggers_when_price_reaches_it(side, trigger, price, expected):
    assert is_triggered(order("limit", side, trigger), price) is expected


@pytest.mark.parametrize("side,trigger,price,expected", [
    ("long", 100, 101, True),    # buy stop waits for the market to rise through
    ("long", 100, 99, False),
    ("short", 100, 99, True),    # sell stop waits for it to fall through
    ("short", 100, 101, False),
])
def test_stop_triggers_on_the_opposite_side_of_a_limit(side, trigger, price, expected):
    assert is_triggered(order("stop", side, trigger), price) is expected


def test_protective_exits_are_expressed_as_the_closing_side():
    """A stop-loss on a long closes short, so it sits below the entry."""
    sl = order("stop_loss", "short", 90)      # guards a long
    assert is_triggered(sl, 89) is True
    assert is_triggered(sl, 91) is False

    tp = order("take_profit", "short", 110)   # guards a long
    assert is_triggered(tp, 111) is True
    assert is_triggered(tp, 109) is False


def test_unknown_order_type_is_rejected():
    with pytest.raises(ValueError):
        is_triggered(order("nonsense", "long", 100), 100)


# ------------------------------------------------------------- fill price

def test_a_limit_fills_at_its_limit_not_the_market():
    o = order("limit", "long", 100, limit_price=100.0)
    assert fill_price_for(o, 95.0) == 100.0


def test_a_stop_fills_at_the_market_which_is_what_makes_stops_slip():
    o = order("stop", "long", 100)
    assert fill_price_for(o, 104.0) == 104.0


# ------------------------------------------------------------------- book

@pytest.fixture
def book(tmp_path):
    return OrderBook(str(tmp_path))


def test_placed_orders_are_listed_and_survive_a_new_instance(book, tmp_path):
    o = book.place(account_id="a", ticker="GC=F", direction="long", size=1,
                   order_type="limit", trigger_price=100.0)
    assert [x["id"] for x in OrderBook(str(tmp_path)).list()] == [o["id"]]


def test_listing_can_be_scoped_by_account_and_instrument(book):
    book.place(account_id="a", ticker="GC=F", direction="long", size=1,
               order_type="limit", trigger_price=100.0)
    book.place(account_id="b", ticker="ES=F", direction="long", size=1,
               order_type="limit", trigger_price=100.0)
    assert len(book.list(account_id="a")) == 1
    assert len(book.list(ticker="ES=F")) == 1
    assert len(book.list()) == 2


def test_invalid_orders_are_rejected(book):
    with pytest.raises(ValueError):
        book.place(account_id="a", ticker="X", direction="long", size=0,
                   order_type="limit", trigger_price=100.0)
    with pytest.raises(ValueError):
        book.place(account_id="a", ticker="X", direction="sideways", size=1,
                   order_type="limit", trigger_price=100.0)
    with pytest.raises(ValueError):
        book.place(account_id="a", ticker="X", direction="long", size=1,
                   order_type="teleport", trigger_price=100.0)


def test_cancelling_an_unknown_order_raises(book):
    with pytest.raises(KeyError):
        book.cancel("nope")


def test_closing_a_position_can_cancel_its_protective_orders(book):
    book.place(account_id="a", ticker="GC=F", direction="short", size=1,
               order_type="stop_loss", trigger_price=90.0, position_id="p1")
    book.place(account_id="a", ticker="GC=F", direction="short", size=1,
               order_type="take_profit", trigger_price=110.0, position_id="p1")
    book.place(account_id="a", ticker="ES=F", direction="long", size=1,
               order_type="limit", trigger_price=100.0)

    assert book.cancel_for_position("p1") == 2
    remaining = book.list()
    assert len(remaining) == 1 and remaining[0]["ticker"] == "ES=F"


def test_marketable_returns_only_orders_the_market_has_reached(book):
    book.place(account_id="a", ticker="GC=F", direction="long", size=1,
               order_type="limit", trigger_price=100.0)     # market at 95 → hit
    book.place(account_id="a", ticker="GC=F", direction="long", size=1,
               order_type="limit", trigger_price=90.0)      # still resting

    hits = book.marketable(lambda _t: 95.0)
    assert [o["trigger_price"] for o, _ in hits] == [100.0]
    assert hits[0][1] == 95.0                                # price came back too


def test_a_quote_failure_does_not_abort_the_sweep(book):
    """One bad instrument must not stop every other order from filling."""
    book.place(account_id="a", ticker="BROKEN", direction="long", size=1,
               order_type="limit", trigger_price=100.0)
    book.place(account_id="a", ticker="GC=F", direction="long", size=1,
               order_type="limit", trigger_price=100.0)

    def quote(ticker):
        if ticker == "BROKEN":
            raise RuntimeError("no quote")
        return 95.0

    hits = book.marketable(quote)
    assert [o["ticker"] for o, _ in hits] == ["GC=F"]
