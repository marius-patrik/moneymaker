"""Manual position book.

Strategy runs record their trades through TradeLogger, but an order placed
by hand had no home: it adjusted the account balance and vanished, so
nothing showed up in the portfolio afterwards. This is that missing record —
open positions persist here, and closing one appends a completed trade to a
session log so it joins the same history as everything else.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import pathlib
import uuid
from typing import Optional

BOOK_FILE = "manual_positions.json"
LOG_PREFIX = "manual"


class ManualBook:
    def __init__(self, home: str):
        self.home = home
        self.path = pathlib.Path(home) / BOOK_FILE

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

    def open(self, *, account_id: str, ticker: str, direction: str, size: float,
             price: float, note: str = "") -> dict:
        data = self._read()
        pos_id = uuid.uuid4().hex[:10]
        pos = {
            "id": pos_id,
            "account_id": account_id,
            "ticker": ticker,
            "direction": direction,
            "size": size,
            "entry_price": price,
            "entry_time": dt.datetime.now().isoformat(timespec="seconds"),
            "note": note,
            "source": "manual",
        }
        data[pos_id] = pos
        self._write(data)
        return pos

    def get(self, pos_id: str) -> Optional[dict]:
        return self._read().get(pos_id)

    def list(self, account_id: Optional[str] = None) -> list[dict]:
        rows = list(self._read().values())
        if account_id:
            rows = [r for r in rows if r.get("account_id") == account_id]
        return sorted(rows, key=lambda r: r.get("entry_time", ""), reverse=True)

    def close(self, pos_id: str, price: float, reason: str = "manual") -> dict:
        data = self._read()
        pos = data.pop(pos_id, None)
        if not pos:
            raise KeyError(pos_id)

        sign = 1 if pos["direction"] == "long" else -1
        pnl = sign * (price - pos["entry_price"]) * pos["size"]
        closed = {
            **pos,
            "exit_price": price,
            "exit_time": dt.datetime.now().isoformat(timespec="seconds"),
            "exit_reason": reason,
            "pnl": round(pnl, 2),
            "pnl_pct": sign * (price - pos["entry_price"]) / pos["entry_price"],
        }
        self._write(data)
        self._append_log(closed)
        return closed

    # -- history --------------------------------------------------------

    def _append_log(self, t: dict) -> None:
        """
        Append to a per-account session log so closed manual trades appear in
        the same history as strategy trades, with the same columns.
        """
        sess = pathlib.Path(self.home) / "sessions"
        sess.mkdir(parents=True, exist_ok=True)
        path = sess / f"{LOG_PREFIX}_{t['account_id']}.csv"
        header = ["entry_time", "entry_price", "direction", "size", "account_id",
                  "ticker", "exit_time", "exit_price", "exit_reason", "pnl", "pnl_pct"]
        exists = path.exists()
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(header)
            w.writerow([
                t["entry_time"], f"{t['entry_price']:.4f}", t["direction"],
                f"{t['size']:.4f}", t["account_id"], t["ticker"],
                t["exit_time"], f"{t['exit_price']:.4f}", t["exit_reason"],
                f"{t['pnl']:.2f}", f"{t['pnl_pct']:.4%}",
            ])
