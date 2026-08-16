"""
Opening range breakout (ORB).

STUB — structure only, on_bar not yet implemented.

Premise:
  The first N minutes after the regular session open (9:30 ET) establish a
  price range. A breakout above/below that range signals directional bias for
  the morning session. Not tied to a specific data release — runs every day.

Approach:
  1. Record the high and low of bars from 9:30 to 9:30 + orb_minutes.
  2. After the ORB window closes, watch for a close above the range high (long)
     or below the range low (short).
  3. Enter on breakout. Stop: other side of the ORB range. Target: range_width × rr.
  4. Hard exit at hard_exit_time (e.g., 12:00).

Variants to evaluate:
  - ORB 5m vs 15m vs 30m: wider range = fewer false breakouts, fewer trades.
  - Require a retest of the ORB level before entry (reduces whipsaws).
  - Only trade breakouts in the direction of the prior day's close vs prior close.
  - Volume filter: only trade if breakout bar volume > N× the ORB average.

Why it's interesting here:
  Completely independent of any data release. Could run alongside the spike
  strategy on non-release days, or as a daily baseline to compare against.

Parameters to explore:
  orb_minutes: 5, 15, 30
  retest_required: bool
  target_rr: 1.5, 2.0, 3.0
  max_stop_pct: cap the stop if the ORB is unusually wide
"""

from __future__ import annotations

import datetime as dt

from engine.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class OpeningRangeBreakoutStrategy(Strategy):
    """Opening range breakout — stub, not yet implemented."""

    name = "opening_range_breakout"

    def __init__(
        self,
        open_time: dt.time = dt.time(9, 30),
        orb_minutes: int = 15,
        target_rr: float = 2.0,
        max_stop_pct: float = 0.005,
        hard_exit_time: dt.time = dt.time(12, 0),
    ):
        self.open_time = open_time
        self.orb_minutes = orb_minutes
        self.target_rr = target_rr
        self.max_stop_pct = max_stop_pct
        self.hard_exit_time = hard_exit_time

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        raise NotImplementedError(
            "opening_range_breakout is a stub. Implement on_bar before backtesting."
        )
