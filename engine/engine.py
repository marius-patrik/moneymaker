"""Simulator: the loop shared by backtest and live-paper modes. Feeds bars
to a strategy, and whenever the strategy opens/closes a position, routes
the fill through whichever ExecutionProvider + account was configured."""

from __future__ import annotations

import datetime as dt
import sys
import threading
import time
from typing import Optional

import pandas as pd

from engine.data import DataFeed
from engine.logger import Trade, TradeLogger
from engine.providers.base import ExecutionProvider
from engine.risk import RiskManager
from engine.strategy import Bar, Strategy, StrategyContext


class Simulator:
    def __init__(self, strategy: Strategy, provider: ExecutionProvider, account_id: str,
                 risk: RiskManager, logger: TradeLogger, ticker: str = ""):
        self.strategy = strategy
        self.provider = provider
        self.account_id = account_id
        self.risk = risk
        self.logger = logger
        self.ticker = ticker
        self.ctx = StrategyContext()
        self._open_trade: Optional[Trade] = None
        self._last_bar_time: Optional[dt.datetime] = None
        self.stopped = threading.Event()

    def feed_bar(self, bar: Bar, deduplicate: bool = False) -> None:
        if deduplicate and self._last_bar_time is not None and bar.time <= self._last_bar_time:
            return
        self._last_bar_time = bar.time
        was_open = self.ctx.position_open
        self.ctx.bars.append(bar)
        self.strategy.on_bar(self.ctx, bar)

        if not was_open and self.ctx.position_open:
            result = self.provider.execute_order(
                account_id=self.account_id, ticker=self.ticker, direction=self.ctx.direction,
                size=0,  # real size is derived from the fill price below, via RiskManager
                reference_price=self.ctx.entry_price, timestamp=bar.time, closing=False,
            )
            balance = self.provider.get_account_balance(self.account_id)
            size = self.risk.position_size(balance, result.fill_price, self.ctx.stop_price)
            self._open_trade = Trade(
                entry_time=self.ctx.entry_time,
                entry_price=result.fill_price,
                direction=self.ctx.direction,
                size=size,
                account_id=self.account_id,
            )
            target_str = f"{self.ctx.target_price:.2f}" if self.ctx.target_price is not None else "none"
            print(f"[{bar.time}] ENTER {self.ctx.direction.upper()} @ {result.fill_price:.2f} "
                  f"size={size:.4f} stop={self.ctx.stop_price:.2f} target={target_str} "
                  f"via={self.provider.name}/{self.account_id} ({self.ctx.extra.get('entry_reason', '')})")

        if self.ctx.extra.get("close_now"):
            reason = self.ctx.extra.get("close_reason", "unknown")
            result = self.provider.execute_order(
                account_id=self.account_id, ticker=self.ticker, direction=self.ctx.direction,
                size=self._open_trade.size, reference_price=bar.price, timestamp=bar.time, closing=True,
            )
            self._open_trade.close(bar.time, result.fill_price, reason)
            self.logger.record(self._open_trade)
            self.provider.on_trade_closed(self.account_id, self._open_trade.pnl)
            print(f"[{bar.time}] EXIT {self.ctx.direction.upper()} @ {result.fill_price:.2f} "
                  f"reason={reason} pnl={self._open_trade.pnl:+.2f} ({self._open_trade.pnl_pct:+.3%})")
            self._open_trade = None
            self.ctx.position_open = False
            self.ctx.extra["close_now"] = False

    def run_backtest(self, df: pd.DataFrame) -> None:
        last_bar = None
        for ts, row in df.iterrows():
            bar = Bar(
                time=ts.to_pydatetime(),
                price=float(row["Close"]),
                volume=float(row["Volume"]) if "Volume" in row.index else 0.0,
            )
            self.feed_bar(bar)
            last_bar = bar
        # Force-close any position still open at end of data (P006).
        if self.ctx.position_open and self._open_trade is not None and last_bar is not None:
            result = self.provider.execute_order(
                account_id=self.account_id, ticker=self.ticker, direction=self.ctx.direction,
                size=self._open_trade.size, reference_price=last_bar.price,
                timestamp=last_bar.time, closing=True,
            )
            self._open_trade.close(last_bar.time, result.fill_price, "end_of_data")
            self.logger.record(self._open_trade)
            self.provider.on_trade_closed(self.account_id, self._open_trade.pnl)
            print(f"[{last_bar.time}] EXIT {self.ctx.direction.upper()} @ {result.fill_price:.2f} "
                  f"reason=end_of_data pnl={self._open_trade.pnl:+.2f}")
            self._open_trade = None
            self.ctx.position_open = False
        self.logger.write_csv()
        self.logger.print_summary()

    def run_live(self, ticker: str, poll_seconds: int, end_time: dt.time) -> None:
        print(f"Starting live-paper session on {ticker} via {self.provider.name}/{self.account_id}. "
              f"Polling every {poll_seconds}s. Will stop at {end_time} local time. Ctrl+C to stop early.")
        while not self.stopped.is_set():
            now = dt.datetime.now()
            if now.time() >= end_time:
                print("Reached end time, stopping session.")
                break
            try:
                price, ts = DataFeed.get_last_price(ticker)
                bar = Bar(time=ts, price=price)
                self.feed_bar(bar, deduplicate=True)
            except Exception as e:
                print(f"[{now}] fetch error: {e}", file=sys.stderr)
            self.stopped.wait(poll_seconds)
        self.logger.write_csv()
        self.logger.print_summary()

    def status(self) -> dict:
        return {
            "position_open": self.ctx.position_open,
            "direction": self.ctx.direction,
            "entry_price": self.ctx.entry_price,
            "entry_time": self.ctx.entry_time.isoformat() if self.ctx.entry_time else None,
            "stop_price": self.ctx.stop_price,
            "target_price": self.ctx.target_price,
            "trades_taken": self.ctx.trades_taken,
            "closed_trades": [t.to_dict() for t in self.logger.trades],
            "bars_seen": len(self.ctx.bars),
            "last_price": self.ctx.bars[-1].price if self.ctx.bars else None,
            "summary": self.logger.summary(),
        }
