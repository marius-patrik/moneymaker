"""
Momentum continuation after data release.

Premise:
  Opposite of the spike-fade approach: enter IN the direction of the spike on
  momentum confirmation. Large surprise releases produce multi-hour directional
  moves. The fade fades every spike; this strategy only trades the large ones.

Flow:
  1. Establish baseline price before release_time.
  2. Measure spike: max deviation from baseline within spike_window_min of release.
  3. Require spike >= min_spike_pct to qualify (weeds out noise).
  4. Wait for confirmation_bars consecutive bars closing in the spike direction.
  5. Enter in spike direction. Stop: below spike low (long) / above spike high (short).
  6. Target: target_spike_multiple × spike size beyond entry.
  7. Trailing stop: once price moves trailing_activation_rr × stop_dist in our favor,
     trail the stop at trailing_stop_pct from current price.
  8. Hard exit at hard_exit_time.

FORKS compare spike thresholds and confirmation requirements.
"""

from __future__ import annotations

import datetime as dt

from engine.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class MomentumContinuationStrategy(Strategy):
    """Momentum continuation after data release with trailing stop."""

    name = "momentum_continuation"
    max_trades_per_session = 1

    FORKS = [
        ("mom_quick",  "momentum_continuation", {"min_spike_pct": 0.001, "confirmation_bars": 1, "trailing_stop_pct": 0.003}),
        ("mom_base",   "momentum_continuation", {"min_spike_pct": 0.0015, "confirmation_bars": 2, "trailing_stop_pct": 0.003}),
        ("mom_strong", "momentum_continuation", {"min_spike_pct": 0.003,  "confirmation_bars": 2, "trailing_stop_pct": 0.002}),
        ("mom_tight",  "momentum_continuation", {"min_spike_pct": 0.0015, "confirmation_bars": 2, "trailing_stop_pct": 0.002, "trailing_activation_rr": 0.5}),
    ]

    def __init__(
        self,
        release_time: dt.time = dt.time(8, 30),
        baseline_minutes: int = 5,
        spike_window_min: int = 5,
        min_spike_pct: float = 0.0015,
        confirmation_bars: int = 2,
        trailing_stop_pct: float = 0.003,
        trailing_activation_rr: float = 1.0,
        target_spike_multiple: float = 1.5,
        hard_exit_time: dt.time = dt.time(12, 0),
    ):
        self.release_time = release_time
        self.baseline_minutes = baseline_minutes
        self.spike_window_min = spike_window_min
        self.min_spike_pct = min_spike_pct
        self.confirmation_bars = confirmation_bars
        self.trailing_stop_pct = trailing_stop_pct
        self.trailing_activation_rr = trailing_activation_rr
        self.target_spike_multiple = target_spike_multiple
        self.hard_exit_time = hard_exit_time

    def _release_dt(self, bar_time: dt.datetime) -> dt.datetime:
        return dt.datetime.combine(bar_time.date(), self.release_time, tzinfo=bar_time.tzinfo)

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        reset_session_if_new_day(ctx, bar)
        release_dt = self._release_dt(bar.time)
        if ctx.hard_exit_time is None:
            ctx.hard_exit_time = dt.datetime.combine(
                bar.time.date(), self.hard_exit_time, tzinfo=bar.time.tzinfo
            )

        if ctx.position_open:
            # Trailing stop logic: advance stop once trailing_activation_rr × stop_dist profit
            init_stop_dist = ctx.extra.get("init_stop_dist", 0)
            activation_dist = init_stop_dist * self.trailing_activation_rr
            if activation_dist > 0:
                if ctx.direction == "long":
                    profit = bar.price - ctx.entry_price
                    if profit >= activation_dist:
                        trail_stop = bar.price * (1 - self.trailing_stop_pct)
                        if trail_stop > ctx.stop_price:
                            ctx.stop_price = trail_stop
                else:
                    profit = ctx.entry_price - bar.price
                    if profit >= activation_dist:
                        trail_stop = bar.price * (1 + self.trailing_stop_pct)
                        if trail_stop < ctx.stop_price:
                            ctx.stop_price = trail_stop

            hit_stop = (
                (ctx.direction == "long" and bar.price <= ctx.stop_price)
                or (ctx.direction == "short" and bar.price >= ctx.stop_price)
            )
            hit_target = (
                ctx.target_price is not None and (
                    (ctx.direction == "long" and bar.price >= ctx.target_price)
                    or (ctx.direction == "short" and bar.price <= ctx.target_price)
                )
            )
            timed_out = bar.time >= ctx.hard_exit_time
            if hit_stop or hit_target or timed_out:
                ctx.extra["close_reason"] = "stop" if hit_stop else "target" if hit_target else "time_box"
                ctx.extra["close_now"] = True
            return

        if ctx.trades_taken >= self.max_trades_per_session:
            return
        if bar.time < release_dt or bar.time >= ctx.hard_exit_time:
            return

        # Baseline: average price in the N minutes before release
        baseline_start = release_dt - dt.timedelta(minutes=self.baseline_minutes)
        baseline_bars = [b.price for b in ctx.bars if baseline_start <= b.time < release_dt]
        if not baseline_bars:
            return
        baseline = sum(baseline_bars) / len(baseline_bars)

        spike_end = release_dt + dt.timedelta(minutes=self.spike_window_min)
        if bar.time < spike_end:
            return  # still inside the spike window

        # Measure spike: max deviation from baseline during spike window
        spike_bars = [b for b in ctx.bars if release_dt <= b.time < spike_end]
        if not spike_bars:
            return

        spike_high = max(b.price for b in spike_bars)
        spike_low = min(b.price for b in spike_bars)
        up_spike = (spike_high - baseline) / baseline
        down_spike = (baseline - spike_low) / baseline

        if up_spike >= down_spike and up_spike >= self.min_spike_pct:
            spike_direction = "long"
            spike_extreme = spike_high
        elif down_spike > up_spike and down_spike >= self.min_spike_pct:
            spike_direction = "short"
            spike_extreme = spike_low
        else:
            return  # spike too small to qualify

        spike_magnitude = max(up_spike, down_spike) * baseline

        # Confirmation: last N post-spike bars must close in spike direction
        post_spike_bars = [b for b in ctx.bars if b.time >= spike_end]
        if len(post_spike_bars) < self.confirmation_bars:
            return

        recent = post_spike_bars[-self.confirmation_bars:]
        if spike_direction == "long":
            # Each bar should close higher than previous (or above baseline)
            if not all(b.price > baseline for b in recent):
                return
            if recent[-1].price < recent[0].price:
                return  # weakening, not confirming
        else:
            if not all(b.price < baseline for b in recent):
                return
            if recent[-1].price > recent[0].price:
                return

        entry = bar.price
        stop_dist = abs(entry - spike_extreme) if spike_direction == "long" \
            else abs(spike_extreme - entry)

        if spike_direction == "long":
            ctx.stop_price = spike_low  # stop below spike low
            stop_dist = entry - ctx.stop_price
        else:
            ctx.stop_price = spike_high  # stop above spike high
            stop_dist = ctx.stop_price - entry

        if stop_dist <= 0:
            return

        ctx.target_price = (
            entry + spike_magnitude * self.target_spike_multiple
            if spike_direction == "long"
            else entry - spike_magnitude * self.target_spike_multiple
        )

        ctx.position_open = True
        ctx.entry_price = entry
        ctx.entry_time = bar.time
        ctx.direction = spike_direction
        ctx.trades_taken += 1
        ctx.extra["init_stop_dist"] = stop_dist
        ctx.extra["entry_reason"] = (
            f"momentum continuation {spike_direction}: spike={max(up_spike,down_spike):.3%} "
            f"baseline={baseline:.2f} target={ctx.target_price:.2f}"
        )
