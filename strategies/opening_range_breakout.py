"""
Opening range breakout (ORB).

Premise:
  The first N minutes after the regular session open (9:30 ET for US equity
  index futures/ETFs) establish a price range. A close outside that range
  signals directional bias for the morning session. Completely independent of
  any scheduled data release — runs every session.

Flow:
  1. Accumulate bars from open_time to open_time + orb_minutes to form the ORB.
  2. After the ORB window closes, watch for a bar closing outside the range.
  3. Enter on breakout. Stop: opposite edge of the ORB. Target: rr × range_width.
  4. Skip if ORB is unusually wide (max_stop_pct cap prevents outsized risk on
     gap-open or high-volatility sessions).
  5. Skip if entry price has already moved too far past the ORB edge (slippage guard).
  6. Hard exit at hard_exit_time regardless.

FORKS compare the three standard ORB window widths (5m, 15m, 30m).
"""

from __future__ import annotations

import datetime as dt

from engine.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class OpeningRangeBreakoutStrategy(Strategy):
    """
    Opening range breakout: enter on first close outside the ORB,
    stop at opposite ORB edge, target at rr × range width.
    """

    name = "opening_range_breakout"
    max_trades_per_session = 1

    FORKS = [
        ("orb_15m", "opening_range_breakout", {
            "orb_minutes": 15, "target_rr": 2.0, "max_stop_pct": 0.005,
            "max_entry_slippage_pct": 0.002,
        }),
        ("orb_5m", "opening_range_breakout", {
            "orb_minutes": 5, "target_rr": 2.0, "max_stop_pct": 0.005,
            "max_entry_slippage_pct": 0.002,
        }),
        ("orb_30m", "opening_range_breakout", {
            "orb_minutes": 30, "target_rr": 2.0, "max_stop_pct": 0.005,
            "max_entry_slippage_pct": 0.002,
        }),
    ]

    def __init__(
        self,
        open_time: dt.time = dt.time(9, 30),
        orb_minutes: int = 15,
        target_rr: float = 2.0,
        max_stop_pct: float = 0.005,
        max_entry_slippage_pct: float = 0.002,
        hard_exit_time: dt.time = dt.time(12, 0),
    ):
        self.open_time = open_time
        self.orb_minutes = orb_minutes
        self.target_rr = target_rr
        self.max_stop_pct = max_stop_pct
        self.max_entry_slippage_pct = max_entry_slippage_pct
        self.hard_exit_time = hard_exit_time

    def _open_dt(self, bar_time: dt.datetime) -> dt.datetime:
        return dt.datetime.combine(bar_time.date(), self.open_time, tzinfo=bar_time.tzinfo)

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        reset_session_if_new_day(ctx, bar)

        open_dt = self._open_dt(bar.time)
        if ctx.hard_exit_time is None:
            ctx.hard_exit_time = dt.datetime.combine(
                bar.time.date(), self.hard_exit_time, tzinfo=bar.time.tzinfo
            )

        # --- Manage open position ---
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
                ctx.extra["close_reason"] = "stop" if hit_stop else "target" if hit_target else "time_box"
                ctx.extra["close_now"] = True
            return

        if ctx.trades_taken >= self.max_trades_per_session:
            return
        if bar.time < open_dt or bar.time >= ctx.hard_exit_time:
            return

        # --- ORB window ---
        orb_end = open_dt + dt.timedelta(minutes=self.orb_minutes)
        if bar.time < orb_end:
            return  # still inside the ORB window; accumulating range

        # --- Build ORB from bars strictly inside the window ---
        orb_bars = [b for b in ctx.bars if open_dt <= b.time < orb_end]
        if not orb_bars:
            return

        orb_high = max(b.price for b in orb_bars)
        orb_low = min(b.price for b in orb_bars)
        orb_width = orb_high - orb_low
        orb_mid = (orb_high + orb_low) / 2

        # Skip sessions where the ORB itself is unusually wide
        if orb_width / orb_mid > self.max_stop_pct:
            return

        # --- Breakout check ---
        if bar.price > orb_high:
            direction = "long"
            edge = orb_high
        elif bar.price < orb_low:
            direction = "short"
            edge = orb_low
        else:
            return  # inside range, no breakout yet

        entry = bar.price

        # Skip if already moved too far past the ORB edge
        slippage_pct = abs(entry - edge) / orb_mid
        if slippage_pct > self.max_entry_slippage_pct:
            return

        # Stop: opposite ORB edge. Target: rr × actual stop distance (not orb_width)
        # so the R:R holds even when entry has slipped past the ORB edge.
        if direction == "long":
            ctx.stop_price = orb_low
            stop_dist = entry - ctx.stop_price
            ctx.target_price = entry + stop_dist * self.target_rr
        else:
            ctx.stop_price = orb_high
            stop_dist = ctx.stop_price - entry
            ctx.target_price = entry - stop_dist * self.target_rr

        ctx.position_open = True
        ctx.entry_price = entry
        ctx.entry_time = bar.time
        ctx.direction = direction
        ctx.trades_taken += 1
        ctx.extra["entry_reason"] = (
            f"ORB{self.orb_minutes}m {direction} break of [{orb_low:.2f}–{orb_high:.2f}] "
            f"(width={orb_width:.2f}, stop_pct={orb_width/orb_mid:.3%})"
        )
        ctx.extra["orb_high"] = orb_high
        ctx.extra["orb_low"] = orb_low
        ctx.extra["orb_width"] = orb_width
