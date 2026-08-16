"""
Daily trend-following via MA crossover.

Premise:
  A fast moving average crossing a slow moving average signals a shift in
  directional momentum. Enter in the crossover direction; hold until the
  opposite crossover fires or a fixed-% stop is hit.

Why this matters for the engine:
  All previous strategies operate on 5m bars and suffer from bar-level stop
  execution noise — stops get hit at bar close, which can be significantly
  past the intended stop level. Daily bars are much larger relative to the
  stop distance, so simulated execution is materially more accurate.

  Daily bars are also available from yfinance for multiple years (vs the 60-day
  5m limit), giving far more independent trade samples for statistical grounding.

Flow:
  1. Compute fast_ma and slow_ma from ctx.bars (accumulates across the backtest).
  2. Detect crossover: previous bars had fast<=slow (or fast>=slow), now reversed.
  3. Enter long (fast crosses above slow) or short (fast crosses below slow).
  4. Stop: stop_pct % from entry. No fixed target — hold until next crossover.
  5. Exit: opposite crossover signal OR stop hit (whichever fires first).

Position holds across calendar days — the session reset guard in
reset_session_if_new_day() skips when ctx.position_open=True, so
ctx.stop_price and direction persist correctly across the backtest.

FORKS compare three standard MA period pairs.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from engine.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class TrendMomentumStrategy(Strategy):
    """
    Daily MA crossover trend-following: enter on crossover, exit on reversal or stop.
    Use with --interval 1d and a multi-year date range.
    """

    name = "trend_momentum"
    max_trades_per_session = 1

    FORKS = [
        ("ma_5_20",        "trend_momentum", {"fast_period": 5,  "slow_period": 20,  "stop_pct": 0.03,   "long_only": False}),
        ("ma_5_20_long",   "trend_momentum", {"fast_period": 5,  "slow_period": 20,  "stop_pct": 0.03,   "long_only": True}),
        ("ma_10_50",       "trend_momentum", {"fast_period": 10, "slow_period": 50,  "stop_pct": 0.03,   "long_only": False}),
        ("ma_10_50_long",  "trend_momentum", {"fast_period": 10, "slow_period": 50,  "stop_pct": 0.03,   "long_only": True}),
        # Evolved params — 100% window profitability on GC=F 2022–2026 walk-forward (+72% over 4y).
        ("gc_evolved",     "trend_momentum", {"fast_period": 5,  "slow_period": 25,  "stop_pct": 0.0053, "long_only": True, "init_on_trend": True}),
    ]

    def __init__(
        self,
        fast_period: int = 5,
        slow_period: int = 20,
        stop_pct: float = 0.03,
        long_only: bool = False,
        init_on_trend: bool = True,
        min_ma_spread_pct: float = 0.005,
    ):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.stop_pct = stop_pct
        self.long_only = long_only
        # When True: on the first bar where we have enough history, enter if MAs are
        # already separated — catches trends that started before the window opened.
        self.init_on_trend = init_on_trend
        # Minimum % spread between fast and slow MA to consider MAs "separated enough"
        # for an init_on_trend entry (filters ambiguous/flat market states).
        self.min_ma_spread_pct = min_ma_spread_pct

    def _mas(self, bars: list[Bar]) -> tuple[Optional[float], Optional[float]]:
        if len(bars) < self.slow_period:
            return None, None
        prices = [b.price for b in bars]
        fast = sum(prices[-self.fast_period:]) / self.fast_period
        slow = sum(prices[-self.slow_period:]) / self.slow_period
        return fast, slow

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        # Session reset only fires when no position is open — safe for multi-day holds.
        reset_session_if_new_day(ctx, bar)

        if ctx.position_open:
            hit_stop = (
                (ctx.direction == "long" and bar.price <= ctx.stop_price)
                or (ctx.direction == "short" and bar.price >= ctx.stop_price)
            )
            fast_ma, slow_ma = self._mas(ctx.bars)
            reversal = False
            if fast_ma is not None and slow_ma is not None:
                reversal = (
                    (ctx.direction == "long" and fast_ma < slow_ma)
                    or (ctx.direction == "short" and fast_ma > slow_ma)
                )
            if hit_stop or reversal:
                ctx.extra["close_reason"] = "stop" if hit_stop else "ma_reversal"
                ctx.extra["close_now"] = True
            return

        if ctx.trades_taken >= self.max_trades_per_session:
            return

        # Need at least slow_period + 1 bars to detect a crossover
        if len(ctx.bars) < self.slow_period + 1:
            return

        fast_now, slow_now = self._mas(ctx.bars)
        fast_prev, slow_prev = self._mas(ctx.bars[:-1])
        if fast_now is None or fast_prev is None:
            return

        # Crossover detection
        crossed_up = (fast_prev <= slow_prev) and (fast_now > slow_now)
        crossed_dn = (fast_prev >= slow_prev) and (fast_now < slow_now)

        # init_on_trend: on the FIRST bar where we have enough data, enter if the MAs
        # are already clearly separated. This captures trends that started before the
        # window opened (e.g. a sub-window of a larger bull run has 5d > 20d from bar 1
        # with no crossover to detect, so a normal crossover system would sit out).
        first_signal_bar = len(ctx.bars) == self.slow_period + 1
        if self.init_on_trend and first_signal_bar and not crossed_up and not crossed_dn:
            spread_pct = abs(fast_now - slow_now) / slow_now
            if spread_pct >= self.min_ma_spread_pct:
                crossed_up = fast_now > slow_now
                crossed_dn = fast_now < slow_now

        if not crossed_up and not crossed_dn:
            return

        direction = "long" if crossed_up else "short"

        if self.long_only and direction == "short":
            return
        entry = bar.price

        ctx.stop_price = (
            entry * (1 - self.stop_pct) if direction == "long"
            else entry * (1 + self.stop_pct)
        )
        ctx.target_price = None  # hold until reversal
        ctx.position_open = True
        ctx.entry_price = entry
        ctx.entry_time = bar.time
        ctx.direction = direction
        ctx.trades_taken += 1
        ctx.extra["entry_reason"] = (
            f"MA{self.fast_period}/{self.slow_period} crossover {direction}: "
            f"fast={fast_now:.2f}, slow={slow_now:.2f}"
        )
