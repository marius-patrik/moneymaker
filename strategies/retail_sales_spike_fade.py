"""
Data-release spike-fade strategy: enter AGAINST the spike direction after basing.

Empirical finding (2026-08-16): large ES spikes (>=0.10%) on macro releases
systematically FADE within 1–2 bars. The initial move overshoots as the market
digests the release; by the time a post-spike basing window forms, the move is
exhausted and mean-reverts toward the pre-release baseline.

The continuation strategy (retail_sales_spike_filtered) enters IN the spike
direction and consistently loses on genuine release days. This strategy enters
in the OPPOSITE direction, targeting the baseline as the take-profit.

Flow:
  1-3. Same as retail_sales_spike_filtered: baseline, spike detection, surprise gate.
  4.   Basing window: wait for N bars of tight consolidation after the spike.
  5.   Fade entry: once a basing window is confirmed, enter on the FIRST bar that
       breaks AGAINST the spike direction (i.e. toward the baseline).
         Long spike  → enter SHORT when bar.price < basing_low
         Short spike → enter LONG  when bar.price > basing_high
  6.   Stop: far side of basing range + buffer (assumes the move was not a fade,
       and price is continuing in the original spike direction past basing).
  7.   Target: baseline price (the pre-release level the fade is expected to reach).
  8.   Hard time-box exit regardless.

FORKS = [
  ("fade", "retail_sales_spike_fade", {default params}),
  ("continuation", "retail_sales_spike_filtered", {default params}),
]
allows `fork-eval --strategy retail_sales_spike_fade` to compare both hypotheses
over identical windows.
"""

from __future__ import annotations

import datetime as dt

from engine.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class FadeDataReleaseStrategy(Strategy):
    """
    Data-release fade strategy: enter against spike direction after basing,
    targeting the pre-release baseline. Designed for macro releases where
    the initial move overshoots and quickly reverts.
    """

    name = "retail_sales_spike_fade"
    max_trades_per_session = 1

    FORKS = [
        ("fade_base", "retail_sales_spike_fade", {
            "min_spike_pct": 0.001, "base_bars": 3, "base_tolerance_pct": 0.0010,
            "stop_buffer": 0.0005, "target_rr": 0.0,
            "min_retracement_pct": 0.0, "max_stop_dist_pct": 0.005,
        }),
        ("fade_retracement30", "retail_sales_spike_fade", {
            "min_spike_pct": 0.001, "base_bars": 3, "base_tolerance_pct": 0.0010,
            "stop_buffer": 0.0005, "target_rr": 0.0,
            "min_retracement_pct": 0.30, "max_stop_dist_pct": 0.005,
        }),
        ("fade_tight_stop", "retail_sales_spike_fade", {
            "min_spike_pct": 0.001, "base_bars": 3, "base_tolerance_pct": 0.0010,
            "stop_buffer": 0.0005, "target_rr": 0.0,
            "min_retracement_pct": 0.0, "max_stop_dist_pct": 0.003,
        }),
        ("continuation", "retail_sales_spike_filtered", {
            "min_spike_pct": 0.001, "base_bars": 3, "base_tolerance_pct": 0.0010,
            "stop_buffer": 0.0005, "target_rr": 2.0,
        }),
    ]

    def __init__(
        self,
        release_time: dt.time = dt.time(8, 30),
        baseline_minutes: int = 5,
        spike_window_min: int = 5,
        base_bars: int = 3,
        base_tolerance_pct: float = 0.0010,
        stop_buffer: float = 0.0005,
        target_rr: float = 0.0,
        hard_exit_time: dt.time = dt.time(11, 0),
        min_spike_pct: float = 0.001,
        min_surprise_ratio: float = 0.0,
        min_retracement_pct: float = 0.0,
        max_stop_dist_pct: float = 0.005,
        max_pre_range_pct: float = 0.0,
        calendar_series: str = "",
    ):
        self.release_time = release_time
        self.baseline_minutes = baseline_minutes
        self.spike_window_min = spike_window_min
        self.base_bars = base_bars
        self.base_tolerance_pct = base_tolerance_pct
        self.stop_buffer = stop_buffer
        self.target_rr = target_rr
        self.hard_exit_time = hard_exit_time
        self.min_spike_pct = min_spike_pct
        self.min_surprise_ratio = min_surprise_ratio
        self.min_retracement_pct = min_retracement_pct
        self.max_stop_dist_pct = max_stop_dist_pct
        self.max_pre_range_pct = max_pre_range_pct
        self.calendar_series = calendar_series

    def _release_dt(self, bar_time: dt.datetime) -> dt.datetime:
        return dt.datetime.combine(bar_time.date(), self.release_time, tzinfo=bar_time.tzinfo)

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        reset_session_if_new_day(ctx, bar)
        release_dt = self._release_dt(bar.time)
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
        if bar.time < release_dt or bar.time >= ctx.hard_exit_time:
            return

        # --- Calendar gate: skip sessions that are not release days ---
        if self.calendar_series and "is_release_day" not in ctx.extra:
            from engine.econ_calendar import get_calendar
            from engine.config import get_home
            today = bar.time.date()
            try:
                cal = get_calendar(self.calendar_series, get_home())
                dates = cal.get_release_dates(today, today)
                ctx.extra["is_release_day"] = bool(dates)
            except Exception:
                ctx.extra["is_release_day"] = True  # fail-open
        if self.calendar_series and not ctx.extra.get("is_release_day", True):
            return

        # --- Baseline + pre-noise ---
        baseline_start = release_dt - dt.timedelta(minutes=self.baseline_minutes)
        baseline_bars = [b.price for b in ctx.bars if baseline_start <= b.time < release_dt]
        if not baseline_bars:
            return
        baseline = sum(baseline_bars) / len(baseline_bars)
        pre_noise_pct = (max(baseline_bars) - min(baseline_bars)) / baseline

        # --- Spike window must have closed ---
        spike_end = release_dt + dt.timedelta(minutes=self.spike_window_min)
        if bar.time < spike_end:
            return

        # --- Surprise gate (evaluated once, cached) ---
        if "signal_evaluated" not in ctx.extra:
            spike_prices = [b.price for b in ctx.bars if release_dt <= b.time < spike_end]
            if not spike_prices:
                ctx.extra["signal_evaluated"] = True
                ctx.extra["signal_valid"] = False
            else:
                spike_move_pct = max(abs(p - baseline) for p in spike_prices) / baseline
                valid = (
                    spike_move_pct >= self.min_spike_pct
                    and (self.min_surprise_ratio == 0.0 or
                         spike_move_pct >= self.min_surprise_ratio * max(pre_noise_pct, 1e-9))
                    and (self.max_pre_range_pct == 0.0 or pre_noise_pct <= self.max_pre_range_pct)
                )
                ctx.extra.update({
                    "signal_evaluated": True,
                    "signal_valid": valid,
                    "spike_move_pct": spike_move_pct,
                    "pre_range_pct": pre_noise_pct,
                })
                if not valid and self.max_pre_range_pct > 0 and pre_noise_pct > self.max_pre_range_pct:
                    ctx.extra["stand_down_reason"] = (
                        f"pre_range={pre_noise_pct:.4%} > max={self.max_pre_range_pct:.4%} — noisy session, standing down"
                    )

        if not ctx.extra.get("signal_valid", False):
            return

        # --- Basing window (excludes current bar so it can be the entry trigger) ---
        past_post_spike = [b for b in ctx.bars if spike_end <= b.time < bar.time]
        if len(past_post_spike) < self.base_bars:
            return

        basing_window = None
        for i in range(len(past_post_spike) - self.base_bars + 1):
            window = past_post_spike[i:i + self.base_bars]
            prices = [b.price for b in window]
            rng_pct = (max(prices) - min(prices)) / baseline
            if rng_pct <= self.base_tolerance_pct:
                basing_window = window
        if basing_window is None:
            return

        basing_prices = [b.price for b in basing_window]
        basing_high = max(basing_prices)
        basing_low = min(basing_prices)

        # Direction of original spike and retracement measurement
        spike_prices_all = [b.price for b in ctx.bars if release_dt <= b.time < spike_end]
        avg_spike = sum(spike_prices_all) / len(spike_prices_all) if spike_prices_all else baseline
        spike_dir = "long" if avg_spike > baseline else "short"
        spike_move = abs(avg_spike - baseline)

        # Require basing to have retraced at least min_retracement_pct of the spike.
        # Basing at the spike peak (retracement≈0) → continuation more likely than fade.
        if self.min_retracement_pct > 0 and spike_move > 0:
            basing_avg = sum(basing_prices) / len(basing_prices)
            basing_move = abs(basing_avg - baseline)
            retracement = 1.0 - (basing_move / spike_move)
            if retracement < self.min_retracement_pct:
                return

        # --- Fade entry: break AGAINST spike direction ---
        if spike_dir == "long" and bar.price < basing_low:
            direction = "short"
        elif spike_dir == "short" and bar.price > basing_high:
            direction = "long"
        else:
            return

        entry = bar.price

        # Stop: far side of basing range + buffer (price resuming spike = stop out)
        if direction == "short":
            ctx.stop_price = basing_high * (1 + self.stop_buffer)
            stop_dist = ctx.stop_price - entry
        else:
            ctx.stop_price = basing_low * (1 - self.stop_buffer)
            stop_dist = entry - ctx.stop_price

        # Skip if stop distance is unusually large — likely a gapping or
        # high-volatility session where the entry/stop math is unreliable.
        if self.max_stop_dist_pct > 0 and stop_dist / baseline > self.max_stop_dist_pct:
            return

        # Target: baseline (expected reversion level)
        # If target_rr > 0, use RR multiple instead; target_rr=0 means use baseline
        if self.target_rr > 0:
            if direction == "short":
                ctx.target_price = entry - stop_dist * self.target_rr
            else:
                ctx.target_price = entry + stop_dist * self.target_rr
        else:
            ctx.target_price = baseline

        ctx.position_open = True
        ctx.entry_price = entry
        ctx.entry_time = bar.time
        ctx.direction = direction
        ctx.trades_taken += 1
        ctx.extra["entry_reason"] = (
            f"fade {direction} below basing [{basing_low:.2f}–{basing_high:.2f}] "
            f"after {ctx.extra.get('spike_move_pct', 0):.3%} {spike_dir} spike, "
            f"baseline={baseline:.2f} (target)"
        )
        ctx.extra["baseline"] = baseline
        ctx.extra["stop_dist_pct"] = stop_dist / entry
