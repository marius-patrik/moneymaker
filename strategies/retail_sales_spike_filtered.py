"""
Improved version of retail_sales_spike: adds a minimum-surprise filter so
the strategy stands down entirely on days where the release doesn't
actually move price — instead of forcing a low-conviction trade off pure
noise, which is what the original strategy would do on a flat day.
"""

from __future__ import annotations

import datetime as dt

from moneymaker.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class FilteredDataReleaseStrategy(Strategy):
    """
    Data-release fade/breakout strategy with a minimum-surprise filter:
      1. Establish a pre-release baseline price and measure its own noise
         (pre_noise_pct) — how much price wiggles in the calm window
         before release, on a normal day.
      2. Watch the spike window right after release. Measure the biggest
         deviation from baseline during that window (spike_move_pct).
      3. GATE: only proceed if spike_move_pct clears both an absolute
         floor (min_spike_pct) and a multiple of that day's own
         pre-release noise (min_surprise_ratio * pre_noise_pct). If it
         doesn't, stand down for the rest of the session — take zero
         trades rather than forcing one on a day the market didn't react.
      4. If the gate passes, same basing/entry logic as before: enter
         once price holds a tight range after the spike, in the
         direction of the hold.
      5. Fixed % stop-loss and target, hard time-box exit.
    """

    name = "retail_sales_spike_filtered"
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
        min_spike_pct: float = 0.0015,
        min_surprise_ratio: float = 2.0,
    ):
        self.release_time = release_time
        self.baseline_minutes = baseline_minutes
        self.spike_window_min = spike_window_min
        self.base_bars = base_bars
        self.base_tolerance_pct = base_tolerance_pct
        self.stop_pct = stop_pct
        self.target_pct = target_pct
        self.hard_exit_time = hard_exit_time
        self.min_spike_pct = min_spike_pct
        self.min_surprise_ratio = min_surprise_ratio

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
        pre_noise_pct = (max(baseline_bars) - min(baseline_bars)) / baseline
        ctx.extra["baseline"] = baseline
        ctx.extra["pre_noise_pct"] = pre_noise_pct

        spike_end = release_dt + dt.timedelta(minutes=self.spike_window_min)
        if bar.time < spike_end:
            return

        # Evaluate the surprise filter exactly once, right as the spike
        # window closes, and cache the verdict for the rest of the session.
        if "signal_evaluated" not in ctx.extra:
            spike_prices = [b.price for b in ctx.bars if release_dt <= b.time < spike_end]
            if not spike_prices:
                ctx.extra["signal_evaluated"] = True
                ctx.extra["signal_valid"] = False
            else:
                spike_move_pct = max(abs(p - baseline) for p in spike_prices) / baseline
                valid = (
                    spike_move_pct >= self.min_spike_pct
                    and spike_move_pct >= self.min_surprise_ratio * pre_noise_pct
                )
                ctx.extra["signal_evaluated"] = True
                ctx.extra["signal_valid"] = valid
                ctx.extra["spike_move_pct"] = spike_move_pct
                if not valid:
                    ctx.extra["stand_down_reason"] = (
                        f"spike_move={spike_move_pct:.4%} vs floor={self.min_spike_pct:.4%} "
                        f"and {self.min_surprise_ratio}x pre_noise={pre_noise_pct:.4%} "
                        f"(needed >= {self.min_surprise_ratio * pre_noise_pct:.4%}) — standing down, no trade today"
                    )

        if not ctx.extra.get("signal_valid", False):
            return  # gate failed: no real move to trade, sit this session out

        post_spike_bars = [b for b in ctx.bars if b.time >= spike_end]
        if len(post_spike_bars) < self.base_bars:
            return
        recent = post_spike_bars[-self.base_bars:]
        prices = [b.price for b in recent]
        rng_pct = (max(prices) - min(prices)) / baseline
        if rng_pct > self.base_tolerance_pct:
            return  # still too choppy after the spike, keep waiting

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
        ctx.extra["entry_reason"] = (
            f"based {direction} after {ctx.extra['spike_move_pct']:.3%} spike "
            f"(vs {self.min_surprise_ratio}x noise floor), baseline={baseline:.2f}"
        )
