"""Pending orders: limit, stop, and protective exits attached to a position.

The execution provider fills at a reference price the moment it is called,
which is a market order and nothing else. Anything that waits for a price
needs somewhere to wait and something to watch the market — that is this
module: a persisted book of resting orders plus the rules that decide when
one becomes marketable.

Paper only. Triggering routes through the same provider path as a manual
order, and `make_provider` refuses to construct a live one.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import threading
import uuid
from typing import Callable, Optional

ORDERS_FILE = "pending_orders.json"

# What each type is waiting for, stated once so the UI and the trigger rule
# cannot disagree about it.
ORDER_TYPES = {
    "limit": "Fills at the limit price or better — buy below the market, sell above.",
    "stop": "Becomes a market order once the stop is touched — buy above, sell below.",
    "stop_loss": "Protective exit below a long, above a short.",
    "take_profit": "Profit target above a long, below a short.",
}


def is_triggered(order: dict, price: float) -> bool:
    """
    Whether `price` makes this order marketable.

    Limit and stop are mirror images: a buy limit waits for the market to
    come down to it, a buy stop waits for it to rise through. Protective
    exits are expressed against the position they guard, so their direction
    is already the closing side.
    """
    kind, side, trigger = order["type"], order["direction"], order["trigger_price"]

    if kind == "limit":
        return price <= trigger if side == "long" else price >= trigger
    if kind == "stop":
        return price >= trigger if side == "long" else price <= trigger
    if kind == "stop_loss":
        # Attached to a long → closing side is short → stop sits below.
        return price <= trigger if side == "short" else price >= trigger
    if kind == "take_profit":
        return price >= trigger if side == "short" else price <= trigger
    raise ValueError(f"unknown order type: {kind}")


class OrderBook:
    """Resting orders, persisted so they survive a restart."""

    def __init__(self, home: str):
        self.home = home
        self.path = pathlib.Path(home) / ORDERS_FILE
        self._lock = threading.Lock()

    # -- persistence ----------------------------------------------------

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    # -- lifecycle ------------------------------------------------------

    def place(self, *, account_id: str, ticker: str, direction: str, size: float,
              order_type: str, trigger_price: float, limit_price: Optional[float] = None,
              position_id: Optional[str] = None, tif: str = "gtc") -> dict:
        if order_type not in ORDER_TYPES:
            raise ValueError(f"unknown order type: {order_type}")
        if direction not in ("long", "short"):
            raise ValueError("direction must be 'long' or 'short'")
        if size <= 0:
            raise ValueError("size must be positive")
        if trigger_price <= 0:
            raise ValueError("trigger price must be positive")
        if tif not in ("gtc", "day"):
            raise ValueError("tif must be 'gtc' or 'day'")

        order = {
            "id": uuid.uuid4().hex[:10],
            "account_id": account_id,
            "ticker": ticker,
            "direction": direction,
            "size": size,
            "type": order_type,
            "trigger_price": trigger_price,
            # A limit order fills at its limit; a stop becomes a market order.
            "limit_price": limit_price if order_type == "limit" else None,
            "position_id": position_id,
            "status": "working",
            # A day order dies at the end of the session it was placed in; a
            # GTC order rests until filled or cancelled.
            "tif": tif,
            "placed_on": dt.date.today().isoformat(),
            "placed_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        with self._lock:
            data = self._read()
            data[order["id"]] = order
            self._write(data)
        return order

    def get(self, order_id: str) -> Optional[dict]:
        return self._read().get(order_id)

    def list(self, account_id: Optional[str] = None,
             ticker: Optional[str] = None) -> list[dict]:
        rows = [o for o in self._read().values() if o.get("status") == "working"]
        if account_id:
            rows = [o for o in rows if o.get("account_id") == account_id]
        if ticker:
            rows = [o for o in rows if o.get("ticker") == ticker]
        return sorted(rows, key=lambda o: o["placed_at"], reverse=True)

    def cancel(self, order_id: str) -> dict:
        with self._lock:
            data = self._read()
            order = data.pop(order_id, None)
            if not order:
                raise KeyError(order_id)
            self._write(data)
        return {**order, "status": "cancelled"}

    def remove(self, order_id: str) -> None:
        """Drop a filled order. Cancel is for the user; this is for the monitor."""
        with self._lock:
            data = self._read()
            data.pop(order_id, None)
            self._write(data)

    def expire_day_orders(self, today: Optional[dt.date] = None) -> list[dict]:
        """
        Drop day orders left over from an earlier session.

        Run at sweep time rather than on a schedule, so an order cannot
        outlive its day just because the server was asleep at midnight.
        """
        today = today or dt.date.today()
        with self._lock:
            data = self._read()
            stale = [o for o in data.values()
                     if o.get("tif") == "day"
                     and o.get("placed_on")
                     and o["placed_on"] < today.isoformat()]
            for o in stale:
                data.pop(o["id"], None)
            if stale:
                self._write(data)
        return [{**o, "status": "expired"} for o in stale]

    def cancel_for_position(self, position_id: str) -> int:
        """
        Cancel a position's protective orders.

        Leaving a stop-loss working after its position closed would open a
        new position in the opposite direction the next time it triggered.
        """
        with self._lock:
            data = self._read()
            doomed = [k for k, o in data.items() if o.get("position_id") == position_id]
            for k in doomed:
                data.pop(k)
            if doomed:
                self._write(data)
        return len(doomed)

    # -- matching -------------------------------------------------------

    def marketable(self, quote: Callable[[str], Optional[float]]) -> list[tuple[dict, float]]:
        """
        Orders whose trigger the market has reached, paired with the price
        that triggered them.

        `quote` is injected so this stays testable without a data provider,
        and so one price lookup serves every order on that instrument.
        """
        working = self.list()
        if not working:
            return []

        prices: dict[str, Optional[float]] = {}
        hits = []
        for order in working:
            tk = order["ticker"]
            if tk not in prices:
                try:
                    prices[tk] = quote(tk)
                except Exception:
                    prices[tk] = None      # a quote failure must not kill the sweep
            price = prices[tk]
            if price is None:
                continue
            try:
                if is_triggered(order, price):
                    hits.append((order, price))
            except ValueError:
                continue                   # malformed order; leave it alone
        return hits


def fill_price_for(order: dict, market_price: float) -> float:
    """
    What the order fills at.

    A limit fills at its limit or better, so the limit is the worst case and
    the price to record. A stop becomes a market order, so it fills wherever
    the market is — which is what makes stops slip.
    """
    if order["type"] == "limit" and order.get("limit_price"):
        return float(order["limit_price"])
    return market_price
