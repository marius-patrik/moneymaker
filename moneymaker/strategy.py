"""Strategy interface, built-in strategies, and drop-in strategy loading."""

from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Bar:
    time: dt.datetime
    price: float


@dataclass
class StrategyContext:
    """State a strategy can read/write as bars stream in. Reset per session."""
    bars: list[Bar] = field(default_factory=list)
    position_open: bool = False
    entry_price: Optional[float] = None
    entry_time: Optional[dt.datetime] = None
    direction: Optional[str] = None  # "long" or "short"
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    hard_exit_time: Optional[dt.datetime] = None
    trades_taken: int = 0
    extra: dict = field(default_factory=dict)


class Strategy(ABC):
    """
    Subclass this to define a new strategy. Drop the .py file in
    <home>/strategies/ and it's auto-loaded alongside built-ins — no need
    to touch this package. The simulator calls on_bar() for every new
    price bar (historical or live) and expects it to mutate ctx to
    open/close a position. Keep logic pure price-action so it behaves
    identically in backtest and live modes.
    """

    name: str = "base"
    max_trades_per_session: int = 1

    @abstractmethod
    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        raise NotImplementedError


class RetailSalesSpikeStrategy(Strategy):
    """
    Data-release fade/breakout strategy:
      1. Establish a pre-release baseline price.
      2. Watch the initial spike window after release.
      3. Enter once price "bases" (holds a tight range for N consecutive
         bars) in the direction of the post-spike hold.
      4. Fixed % stop-loss and target, hard time-box exit.
    """

    name = "retail_sales_spike"
    max_trades_per_session = 1

    def __init__(
        self,
        release_time: dt.time = dt.time(8, 30),
        baseline_minutes: int = 5,
        spike_window_min: int = 5,
        base_bars: int = 2,
        base_tolerance_pct: float = 0.0015,
        stop_pct: float = 0.0045,
        target_pct: float = 0.008,
        hard_exit_time: dt.time = dt.time(11, 0),
    ):
        self.release_time = release_time
        self.baseline_minutes = baseline_minutes
        self.spike_window_min = spike_window_min
        self.base_bars = base_bars
        self.base_tolerance_pct = base_tolerance_pct
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.hard_exit_time = hard_exit_time

    def _release_dt(self, bar_time: dt.datetime) -> dt.datetime:
        return dt.datetime.combine(bar_time.date(), self.release_time, tzinfo=bar_time.tzinfo)

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        release_dt = self._release_dt(bar.time)
        if ctx.hard_exit_time is None:
            ctx.hard_exit_time = dt.datetime.combine(
                bar.time.date(), self.hard_exit_time, tzinfo=bar.time.tzinfo
            )

        if ctx.position_open:
            hit_stop = (
                (ctx.direction == "long" and bar.price <= ctx.stop_price)
                or (ctx.direction == "short" and bar.price >= ctx.stop_price)
            )
            hit_target = (
                (ctx.direction == "long" and bar.price >= ctx.target_price)
                or (ctx.direction == "short" and bar.price <= ctx.target_price)
            )
            timed_out = bar.time >= ctx.hard_exit_time
            if hit_stop or hit_target or timed_out:
                reason = "stop" if hit_stop else "target" if hit_target else "time_box"
                ctx.extra["close_reason"] = reason
                ctx.extra["close_now"] = True
            return

        if ctx.trades_taken >= self.max_trades_per_session:
            return
        if bar.time < release_dt or bar.time >= ctx.hard_exit_time:
            return

        baseline_start = release_dt - dt.timedelta(minutes=self.baseline_minutes)
        baseline_bars = [b.price for b in ctx.bars if baseline_start <= b.time < release_dt]
        if not baseline_bars:
            return
        baseline = sum(baseline_bars) / len(baseline_bars)
        ctx.extra["baseline"] = baseline

        spike_end = release_dt + dt.timedelta(minutes=self.spike_window_min)
        if bar.time < spike_end:
            return

        post_spike_bars = [b for b in ctx.bars if b.time >= spike_end]
        if len(post_spike_bars) < self.base_bars:
            return
        recent = post_spike_bars[-self.base_bars:]
        prices = [b.price for b in recent]
        rng_pct = (max(prices) - min(prices)) / baseline
        if rng_pct > self.base_tolerance_pct:
            return

        avg_recent = sum(prices) / len(prices)
        direction = "long" if avg_recent > baseline else "short"
        entry = bar.price

        ctx.position_open = True
        ctx.entry_price = entry
        ctx.entry_time = bar.time
        ctx.direction = direction
        if direction == "long":
            ctx.stop_price = entry * (1 - self.stop_pct)
            ctx.target_price = entry * (1 + self.target_pct)
        else:
            ctx.stop_price = entry * (1 + self.stop_pct)
            ctx.target_price = entry * (1 - self.target_pct)
        ctx.trades_taken += 1
        ctx.extra["entry_reason"] = f"based {direction} after spike, baseline={baseline:.2f}"


BUILTIN_STRATEGIES: dict[str, type[Strategy]] = {
    RetailSalesSpikeStrategy.name: RetailSalesSpikeStrategy,
}


def load_strategies(home: str) -> dict[str, type[Strategy]]:
    """Built-ins plus anything dropped in <home>/strategies/*.py."""
    strategies = dict(BUILTIN_STRATEGIES)
    strat_dir = os.path.join(home, "strategies")
    if not os.path.isdir(strat_dir):
        return strategies
    for fname in os.listdir(strat_dir):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(strat_dir, fname)
        modname = f"moneymaker_user_strategy_{fname[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(modname, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for attr in vars(mod).values():
                if (isinstance(attr, type) and issubclass(attr, Strategy)
                        and attr is not Strategy and getattr(attr, "name", "base") != "base"):
                    strategies[attr.name] = attr
        except Exception as e:
            print(f"warning: failed to load strategy file {fname}: {e}", file=sys.stderr)
    return strategies
