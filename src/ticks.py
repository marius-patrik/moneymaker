"""Tick recorder.

yfinance's finest history is 1-minute bars, and live polling threw its
quotes away — so the engine had no record of what price it actually saw at
the moment it acted. The order monitor already polls every 20 seconds, so
persisting those quotes costs one append per instrument and gives real
intraday data we own rather than rent.

Stored as newline-delimited JSON per instrument per day: appendable without
reading, greppable, and trivially replaced later by a columnar store if the
volume ever justifies one.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import threading
from typing import Iterator, Optional

TICKS_DIR = "ticks"


def _safe(ticker: str) -> str:
    """Filesystem-safe instrument name — symbols carry = ^ / and spaces."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in ticker)


class TickStore:
    def __init__(self, home: str):
        self.root = pathlib.Path(home) / TICKS_DIR
        self._lock = threading.Lock()
        # Last value per instrument, so an unchanged quote is not written
        # twice — a polled feed repeats itself between trades.
        self._last: dict[str, float] = {}

    def _path(self, ticker: str, day: dt.date) -> pathlib.Path:
        return self.root / _safe(ticker) / f"{day.isoformat()}.jsonl"

    def record(self, ticker: str, price: float,
               at: Optional[dt.datetime] = None) -> bool:
        """
        Append a quote. Returns False when the price is unchanged.

        Deduplicating here rather than at read time keeps the files honest:
        every line is a price that actually moved.
        """
        if price is None or price != price:      # None or NaN
            return False
        with self._lock:
            if self._last.get(ticker) == price:
                return False
            self._last[ticker] = price

        at = at or dt.datetime.now()
        path = self._path(ticker, at.date())
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps({"t": int(at.timestamp()), "p": price}) + "\n")
        return True

    def read(self, ticker: str, day: Optional[dt.date] = None) -> list[dict]:
        path = self._path(ticker, day or dt.date.today())
        if not path.is_file():
            return []
        out = []
        with open(path) as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue      # a half-written final line must not poison the read
        return out

    def days(self, ticker: str) -> list[str]:
        d = self.root / _safe(ticker)
        if not d.is_dir():
            return []
        return sorted(p.stem for p in d.glob("*.jsonl"))

    def instruments(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def candles(self, ticker: str, day: Optional[dt.date] = None,
                seconds: int = 60) -> list[dict]:
        """
        Aggregate ticks into OHLC bars.

        Lets recorded ticks feed the same chart as provider history, at
        resolutions the provider does not offer.
        """
        ticks = self.read(ticker, day)
        if not ticks:
            return []

        bars: list[dict] = []
        bucket: Optional[int] = None
        for t in ticks:
            b = t["t"] - (t["t"] % seconds)
            p = t["p"]
            if b != bucket:
                bars.append({"time": b, "open": p, "high": p, "low": p,
                             "close": p, "volume": 0.0})
                bucket = b
            else:
                bar = bars[-1]
                bar["high"] = max(bar["high"], p)
                bar["low"] = min(bar["low"], p)
                bar["close"] = p
        return bars

    def enroll(self, ticker: str) -> bool:
        """
        Start recording an instrument.

        Called wherever an instrument is touched — charted, traded,
        backtested — so the archive covers what you actually use without
        anyone maintaining a list. Returns False if already enrolled.
        """
        path = self.root.parent / "tick_watch.json"
        try:
            current = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            current = []
        if ticker in current:
            return False
        current = sorted(set(current) | {ticker})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, indent=2))
        return True

    def enrolled(self) -> list[str]:
        path = self.root.parent / "tick_watch.json"
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return []

    def record_batch(self, prices: dict[str, float],
                     at: Optional[dt.datetime] = None) -> int:
        """Record many instruments at once. Returns how many actually moved."""
        at = at or dt.datetime.now()
        return sum(1 for tk, px in prices.items() if self.record(tk, px, at))

    def stats(self) -> dict:
        """What has been captured — for the UI to report honestly."""
        total = 0
        per: dict[str, int] = {}
        for name in self.instruments():
            d = self.root / name
            n = sum(1 for p in d.glob("*.jsonl") for _ in open(p))
            per[name] = n
            total += n
        return {"instruments": len(per), "ticks": total, "per_instrument": per}
