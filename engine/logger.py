"""Trade record and per-session CSV trade logging."""

from __future__ import annotations

import csv
import datetime as dt
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Trade:
    entry_time: dt.datetime
    entry_price: float
    direction: str
    size: float
    account_id: str = ""
    exit_time: Optional[dt.datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None

    def close(self, exit_time: dt.datetime, exit_price: float, reason: str) -> None:
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason
        sign = 1 if self.direction == "long" else -1
        self.pnl = sign * (exit_price - self.entry_price) * self.size
        self.pnl_pct = sign * (exit_price - self.entry_price) / self.entry_price

    def to_dict(self) -> dict:
        return {
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "entry_price": self.entry_price,
            "direction": self.direction,
            "size": self.size,
            "account_id": self.account_id,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
        }


class TradeLogger:
    def __init__(self, home: str, session_name: str):
        self.session_name = session_name
        self.session_path = os.path.join(home, "sessions", f"{session_name}.csv")
        self.trades: list[Trade] = []

    def record(self, trade: Trade) -> None:
        self.trades.append(trade)

    def write_csv(self) -> None:
        with open(self.session_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "entry_time", "entry_price", "direction", "size", "account_id",
                "exit_time", "exit_price", "exit_reason", "pnl", "pnl_pct",
            ])
            for t in self.trades:
                writer.writerow([
                    t.entry_time, f"{t.entry_price:.4f}", t.direction, f"{t.size:.4f}", t.account_id,
                    t.exit_time, f"{t.exit_price:.4f}" if t.exit_price else "",
                    t.exit_reason, f"{t.pnl:.2f}" if t.pnl is not None else "",
                    f"{t.pnl_pct:.4%}" if t.pnl_pct is not None else "",
                ])

    def summary(self, open_pnl: Optional[float] = None) -> dict:
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed and open_pnl is None:
            return {"trades": 0}
        wins = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl <= 0]
        total_pnl = sum(t.pnl for t in closed)
        result = {
            "trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(closed) if closed else 0.0,
            "total_pnl": total_pnl,
            "avg_win": sum(t.pnl for t in wins) / len(wins) if wins else 0.0,
            "avg_loss": sum(t.pnl for t in losses) / len(losses) if losses else 0.0,
            "best_trade": max((t.pnl for t in closed), default=0.0),
            "worst_trade": min((t.pnl for t in closed), default=0.0),
        }
        if open_pnl is not None:
            result["open_pnl"] = open_pnl
        return result

    def print_summary(self, open_pnl: Optional[float] = None) -> None:
        s = self.summary(open_pnl=open_pnl)
        print("\n" + "=" * 50)
        print(f"SESSION SUMMARY — {self.session_path}")
        print("=" * 50)
        if s["trades"] == 0 and open_pnl is None:
            print("No trades were taken this session.")
            return
        if s["trades"] > 0:
            print(f"Trades:      {s['trades']}  (wins: {s['wins']}, losses: {s['losses']})")
            print(f"Win rate:    {s['win_rate']:.1%}")
            print(f"Total P&L:   {s['total_pnl']:+.2f}")
            print(f"Avg win:     {s['avg_win']:+.2f}")
            print(f"Avg loss:    {s['avg_loss']:+.2f}")
            print(f"Best trade:  {s['best_trade']:+.2f}")
            print(f"Worst trade: {s['worst_trade']:+.2f}")
        if open_pnl is not None:
            print(f"Open P&L:    {open_pnl:+.2f}  (unrealized)")
        print("=" * 50)
