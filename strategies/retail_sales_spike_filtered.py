"""
Improved data-release strategy: breakout entry with range-based stops.

Changes from v1:
  - Entry trigger: wait for a confirmed BREAKOUT of the post-spike basing range
    rather than entering while price is still basing. Avoids entries that turn
    into immediate reversals.
  - Stop placement: derived from the basing range rather than a fixed % from
    entry. The range is typically 3-5 pts on ES at 5m, so the stop is tight
    and tied to the actual structure of the setup.
  - Target: set at `target_rr` × the stop distance (default 2:1), scaling
    dynamically to each setup rather than a fixed absolute %.
  - Minimum-surprise gate retained: require the 8:30 spike to clear both an
    absolute floor and a multiple of that day's own pre-release noise. With
    5m bars the noise baseline is a single bar (noise ≈ 0), so in practice
    the gate is the absolute floor alone. Set min_spike_pct to 0.0 to disable.
"""

from __future__ import annotations

import datetime as dt

from src.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class FilteredDataReleaseStrategy(Strategy):
    """
    Data-release strategy with breakout entry and range-based stops.

    Flow:
      1. Pre-release baseline: average close in the calm window before 8:30.
      2. Spike window (8:30–8:35): measure the biggest move from baseline.
      3. Surprise gate: if the spike doesn't clear the absolute floor, stand
         down for the session (no trade).
      4. Basing window: accumulate `base_bars` bars after the spike window.
         Check the range is tight (< base_tolerance_pct). If not, keep waiting
         for a subsequent tight window before the hard exit.
      5. Breakout entry: once a tight basing window is established, enter on
         the FIRST bar that closes outside the basing range in the spike
         direction.
      6. Stop: just beyond the far edge of the basing range (+ stop_buffer).
         Target: stop_distance × target_rr from entry.
      7. Hard time-box exit at hard_exit_time regardless.
    """

    name = "retail_sales_spike_filtered"
    max_trades_per_session = 1

    FORKS = [
        ("continuation", "retail_sales_spike_filtered", {
            "min_spike_pct": 0.001,
            "base_bars": 3,
            "base_tolerance_pct": 0.0010,
            "stop_buffer": 0.0005,
            "target_rr": 2.0,
        }),
        ("fade", "retail_sales_spike_fade", {
            "min_spike_pct": 0.001,
            "base_bars": 3,
            "base_tolerance_pct": 0.0010,
            "stop_buffer": 0.0005,
            "target_rr": 0.0,
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
        target_rr: float = 2.0,
        max_entry_slippage_pct: float = 0.003,
        hard_exit_time: dt.time = dt.time(11, 0),
        min_spike_pct: float = 0.0,
        min_surprise_ratio: float = 0.0,
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
        self.max_entry_slippage_pct = max_entry_slippage_pct
        self.hard_exit_time = hard_exit_time
        self.min_spike_pct = min_spike_pct
        self.min_surprise_ratio = min_surprise_ratio
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
            from src.econ_calendar import get_calendar
            from src.config import get_home
            today = bar.time.date()
            try:
                cal = get_calendar(self.calendar_series, get_home())
                dates = cal.get_release_dates(today, today)
                ctx.extra["is_release_day"] = bool(dates)
            except Exception:
                ctx.extra["is_release_day"] = True  # fail-open: trade if calendar unavailable
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
                if not valid:
                    if self.max_pre_range_pct > 0 and pre_noise_pct > self.max_pre_range_pct:
                        ctx.extra["stand_down_reason"] = (
                            f"pre_range={pre_noise_pct:.4%} > max={self.max_pre_range_pct:.4%} — noisy session, standing down"
                        )
                    else:
                        ctx.extra["stand_down_reason"] = (
                            f"spike={spike_move_pct:.4%} < floor={self.min_spike_pct:.4%} — standing down"
                        )

        if not ctx.extra.get("signal_valid", False):
            return

        # --- Basing window: find the most recent tight window of bars BEFORE
        #     the current bar (excluding it so the current bar can be the breakout) ---
        past_post_spike = [b for b in ctx.bars if spike_end <= b.time < bar.time]
        if len(past_post_spike) < self.base_bars:
            return

        basing_window = None
        for i in range(len(past_post_spike) - self.base_bars + 1):
            window = past_post_spike[i:i + self.base_bars]
            prices = [b.price for b in window]
            rng_pct = (max(prices) - min(prices)) / baseline
            if rng_pct <= self.base_tolerance_pct:
                basing_window = window  # keep the most recent qualifying window
        if basing_window is None:
            return  # no tight window yet; keep waiting

        basing_prices = [b.price for b in basing_window]
        basing_high = max(basing_prices)
        basing_low = min(basing_prices)

        # Direction from spike: which way did the 8:30 bar resolve vs baseline.
        # Noisier than basing direction on tiny spikes, but more reliable when
        # the spike is meaningful. Tiny spikes are gated by min_spike_pct below.
        spike_prices_all = [b.price for b in ctx.bars if release_dt <= b.time < spike_end]
        avg_spike = sum(spike_prices_all) / len(spike_prices_all) if spike_prices_all else baseline
        spike_dir = "long" if avg_spike > baseline else "short"

        # --- Breakout entry: current bar must clear the basing range ---
        if spike_dir == "long" and bar.price > basing_high:
            direction = "long"
        elif spike_dir == "short" and bar.price < basing_low:
            direction = "short"
        else:
            return  # basing confirmed but no breakout yet

        entry = bar.price

        # Reject chasing entries: if the current bar has already moved too far
        # from the basing range edge, the risk/reward is compromised.
        slippage_pct = abs(entry - (basing_high if direction == "long" else basing_low)) / baseline
        if slippage_pct > self.max_entry_slippage_pct:
            return

        # Stop: far side of the basing range + buffer
        # Target: stop_distance × target_rr from entry
        if direction == "long":
            ctx.stop_price = basing_low * (1 - self.stop_buffer)
            stop_dist = entry - ctx.stop_price
            ctx.target_price = entry + stop_dist * self.target_rr
        else:
            ctx.stop_price = basing_high * (1 + self.stop_buffer)
            stop_dist = ctx.stop_price - entry
            ctx.target_price = entry - stop_dist * self.target_rr

        ctx.position_open = True
        ctx.entry_price = entry
        ctx.entry_time = bar.time
        ctx.direction = direction
        ctx.trades_taken += 1
        ctx.extra["entry_reason"] = (
            f"breakout {direction} past basing [{basing_low:.2f}–{basing_high:.2f}] "
            f"after {ctx.extra.get('spike_move_pct', 0):.3%} spike, baseline={baseline:.2f}"
        )
        ctx.extra["basing_range_pct"] = (basing_high - basing_low) / baseline
        ctx.extra["stop_dist_pct"] = stop_dist / entry
