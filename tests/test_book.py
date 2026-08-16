"""Tests for the manual position book (src/book.py)."""

import pathlib

import pytest

from src.book import ManualBook


@pytest.fixture
def book(tmp_path):
    return ManualBook(str(tmp_path))


def test_open_position_is_listed_and_retrievable(book):
    p = book.open(account_id="acct", ticker="GC=F", direction="long",
                  size=2.0, price=100.0)
    assert book.get(p["id"]) == p
    assert [x["id"] for x in book.list()] == [p["id"]]


def test_list_can_be_scoped_to_an_account(book):
    a = book.open(account_id="a", ticker="X", direction="long", size=1, price=10)
    book.open(account_id="b", ticker="Y", direction="short", size=1, price=10)
    assert [x["id"] for x in book.list("a")] == [a["id"]]
    assert len(book.list()) == 2


def test_closing_a_long_computes_pnl_and_removes_it(book):
    p = book.open(account_id="acct", ticker="GC=F", direction="long",
                  size=2.0, price=100.0)
    closed = book.close(p["id"], 110.0)

    assert closed["pnl"] == pytest.approx(20.0)     # (110-100) * 2
    assert book.get(p["id"]) is None
    assert book.list() == []


def test_closing_a_short_inverts_the_sign(book):
    p = book.open(account_id="acct", ticker="GC=F", direction="short",
                  size=3.0, price=100.0)
    closed = book.close(p["id"], 90.0)
    assert closed["pnl"] == pytest.approx(30.0)     # short profits as price falls


def test_closed_trades_are_appended_to_a_session_log(tmp_path):
    book = ManualBook(str(tmp_path))
    p = book.open(account_id="acct", ticker="GC=F", direction="long",
                  size=1.0, price=100.0)
    book.close(p["id"], 105.0)

    log = pathlib.Path(tmp_path) / "sessions" / "manual_acct.csv"
    assert log.is_file()
    text = log.read_text()
    assert "ticker" in text.splitlines()[0]          # header present
    assert "GC=F" in text                            # and the instrument recorded


def test_closing_an_unknown_position_raises(book):
    with pytest.raises(KeyError):
        book.close("nope", 100.0)
