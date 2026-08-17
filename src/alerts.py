"""Price alerts.

The order monitor already polls every instrument being recorded, so an alert
is the same trigger test as a resting order without the fill — which makes
this nearly free to run and means alerts fire on the same data the engine
trades on.

Alerts are notifications, not orders: firing one records that the level was
reached and leaves the decision to the user.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import threading
import uuid
from typing import Optional

ALERTS_FILE = "alerts.json"

CONDITIONS = {
    "above": "Fires when the price rises through the level.",
    "below": "Fires when the price falls through the level.",
    "crosses": "Fires on either side — useful for a level you are watching, not trading.",
}


def has_fired(alert: dict, price: float, previous: Optional[float]) -> bool:
    """
    Whether `price` satisfies the alert.

    "crosses" needs the previous price: without it, a level sitting between
    two polls would either never fire or fire on every tick afterwards.
    """
    level, cond = alert["level"], alert["condition"]
    if cond == "above":
        return price >= level
    if cond == "below":
        return price <= level
    if cond == "crosses":
        if previous is None:
            return False
        return (previous < level <= price) or (previous > level >= price)
    raise ValueError(f"unknown condition: {cond}")


class AlertStore:
    def __init__(self, home: str):
        self.path = pathlib.Path(home) / ALERTS_FILE
        self._lock = threading.Lock()

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def create(self, *, ticker: str, level: float, condition: str,
               note: str = "", repeat: bool = False) -> dict:
        if condition not in CONDITIONS:
            raise ValueError(f"unknown condition: {condition}")
        if level <= 0:
            raise ValueError("level must be positive")

        alert = {
            "id": uuid.uuid4().hex[:10],
            "ticker": ticker,
            "level": level,
            "condition": condition,
            "note": note,
            # A one-shot alert disarms itself; a repeating one keeps watching,
            # which is what you want for a level price oscillates around.
            "repeat": repeat,
            "status": "armed",
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            "fired_at": None,
            "fired_price": None,
        }
        with self._lock:
            data = self._read()
            data[alert["id"]] = alert
            self._write(data)
        return alert

    def list(self, ticker: Optional[str] = None,
             include_fired: bool = True) -> list[dict]:
        rows = list(self._read().values())
        if ticker:
            rows = [a for a in rows if a["ticker"] == ticker]
        if not include_fired:
            rows = [a for a in rows if a["status"] == "armed"]
        return sorted(rows, key=lambda a: a["created_at"], reverse=True)

    def armed(self) -> list[dict]:
        return [a for a in self._read().values() if a["status"] == "armed"]

    def delete(self, alert_id: str) -> dict:
        with self._lock:
            data = self._read()
            alert = data.pop(alert_id, None)
            if not alert:
                raise KeyError(alert_id)
            self._write(data)
        return alert

    def rearm(self, alert_id: str) -> dict:
        with self._lock:
            data = self._read()
            alert = data.get(alert_id)
            if not alert:
                raise KeyError(alert_id)
            alert.update(status="armed", fired_at=None, fired_price=None)
            self._write(data)
        return alert

    def mark_fired(self, alert_id: str, price: float) -> Optional[dict]:
        with self._lock:
            data = self._read()
            alert = data.get(alert_id)
            if not alert:
                return None
            alert["fired_at"] = dt.datetime.now().isoformat(timespec="seconds")
            alert["fired_price"] = price
            if not alert["repeat"]:
                alert["status"] = "fired"
            self._write(data)
            return alert

    def check(self, prices: dict[str, float],
              previous: Optional[dict[str, float]] = None) -> list[dict]:
        """Alerts satisfied by this set of prices, marked fired."""
        previous = previous or {}
        fired = []
        for alert in self.armed():
            price = prices.get(alert["ticker"])
            if price is None:
                continue
            try:
                if has_fired(alert, price, previous.get(alert["ticker"])):
                    marked = self.mark_fired(alert["id"], price)
                    if marked:
                        fired.append(marked)
            except ValueError:
                continue     # malformed alert; leave it alone
        return fired
