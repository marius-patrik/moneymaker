"""
Multi-window backtesting: run a single strategy configuration across
several distinct historical date ranges and aggregate the results.

A strategy that looks great on one lucky (or unlucky) window tells you
almost nothing. This runs the same strategy across N independent windows
and reports consistency (% of windows profitable, P&L variance across
windows) alongside the raw totals, so a single good/bad window can't
dominate the picture.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Callable, Optional

from engine.engine import Simulator
from engine.logger import TradeLogger
from engine.providers import make_provider
from engine.risk import RiskManager


@dataclass
class WindowResult:
    start: str
    end: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "start": self.start, "end": self.end, "trades": self.trades,
            "wins": self.wins, "losses": self.losses, "win_rate": self.win_rate,
            "total_pnl": self.total_pnl, "error": self.error,
        }


@dataclass
class MultiWindowResult:
    windows: list[WindowResult] = field(default_factory=list)

    @property
    def valid_windows(self) -> list[WindowResult]:
        return [w for w in self.windows if w.error is None]

    def summary(self) -> dict:
        valid = self.valid_windows
        if not valid:
            return {"windows": len(self.windows), "valid_windows": 0}
        pnls = [w.total_pnl for w in valid]
        profitable = [w for w in valid if w.total_pnl > 0]
        total_trades = sum(w.trades for w in valid)
        return {
            "windows": len(self.windows),
            "valid_windows": len(valid),
            "total_trades": total_trades,
            "total_pnl": sum(pnls),
            "mean_pnl_per_window": statistics.mean(pnls),
            "pnl_stdev": statistics.pstdev(pnls) if len(pnls) > 1 else 0.0,
            "pct_windows_profitable": len(profitable) / len(valid),
            "best_window_pnl": max(pnls),
            "worst_window_pnl": min(pnls),
            "overall_win_rate": (
                sum(w.wins for w in valid) / total_trades if total_trades else 0.0
            ),
        }

    def to_dict(self) -> dict:
        return {"windows": [w.to_dict() for w in self.windows], "summary": self.summary()}


def run_multi_window_backtest(
    strategy_factory: Callable[[], "Strategy"],  # noqa: F821 — Strategy from engine.strategy
    provider_name: str,
    home: str,
    ticker: str,
    windows: list[tuple[str, str]],
    interval: str = "5m",
    account_balance: float = 10000.0,
    risk_pct: float = 0.01,
    get_data_fn: Optional[Callable] = None,
) -> MultiWindowResult:
    """
    strategy_factory: called once per window to get a *fresh* strategy
    instance (strategies carry per-session state, so reusing one across
    windows would leak state between them).

    get_data_fn(ticker, start, end, interval) -> DataFrame with a "Close"
    column, indexed by timestamp. Defaults to the real yfinance-backed
    DataFeed; tests inject a synthetic one instead so this is testable
    without network access.
    """
    if get_data_fn is None:
        from engine.data import DataFeed
        feed = DataFeed(home)
        get_data_fn = feed.get_historical

    result = MultiWindowResult()
    for start, end in windows:
        try:
            df = get_data_fn(ticker, start, end, interval)
            strategy = strategy_factory()
            provider = make_provider(provider_name, home)
            account = provider.create_account(
                f"mw_{strategy.name}_{start}_{end}", starting_balance=account_balance
            )
            risk = RiskManager(risk_pct=risk_pct)
            logger = TradeLogger(home, f"multiwindow_{strategy.name}_{start}_{end}".replace(":", "-"))
            sim = Simulator(strategy, provider, account.account_id, risk, logger, ticker=ticker)
            sim.run_backtest(df)
            s = logger.summary()
            result.windows.append(WindowResult(
                start=start, end=end, trades=s.get("trades", 0), wins=s.get("wins", 0),
                losses=s.get("losses", 0), win_rate=s.get("win_rate", 0.0),
                total_pnl=s.get("total_pnl", 0.0),
            ))
        except Exception as e:
            result.windows.append(WindowResult(start=start, end=end, error=str(e)))
    return result
