"""
Intraday VWAP mean-reversion.

Premise:
  VWAP (volume-weighted average price) acts as a daily fair-value anchor for
  institutional order flow. Price deviations of N% from VWAP tend to revert
  during low-volatility sessions. Short above VWAP + buffer; long below.

Flow:
  1. Track cumulative VWAP from the session open (9:30 ET).
     VWAP = Σ(price × volume) / Σ(volume), updated bar-by-bar.
  2. Regime filter: skip today if yesterday's intraday range exceeded
     max_prev_day_range_pct. A wide prior-day range signals a trending/volatile
     market regime where mean-reversion is unlikely to work.
  3. Enter long when price is > deviation_pct below VWAP.
     Enter short when price is > deviation_pct above VWAP.
  4. Stop: stop_multiple × entry_deviation from entry, on the far side.
  5. Target: entry + stop_dist × target_rr (positive R:R by construction).
  6. Hard exit at hard_exit_time regardless.

Why it might work:
  Institutional algos use VWAP as a benchmark. Large sellers push price below
  VWAP; reversion fires as they finish. Most reliable in morning with volume.
  The regime filter gates out trending days where price stays extended for hours.

Why it might not:
  The prior-day range filter is a lagging proxy for regime. A quiet prior day
  followed by a trend day today will still produce bad entries.

FORKS compare deviation thresholds and regime filter thresholds.
"""

from __future__ import annotations

import datetime as dt

from engine.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class VwapReversionStrategy(Strategy):
    """
    Intraday VWAP mean-reversion with prior-day range regime filter.
    Only enters on low-volatility (choppy/range-bound) sessions.
    """

    name = "vwap_reversion"
    max_trades_per_session = 2

    FORKS = [
        # Regime filter ON (max_prev_day_range_pct gates trending days)
        ("vwap_regime_tight",  "vwap_reversion", {"deviation_pct": 0.002, "stop_multiple": 1.5, "target_rr": 1.5, "max_prev_day_range_pct": 0.008}),
        ("vwap_regime_std",    "vwap_reversion", {"deviation_pct": 0.003, "stop_multiple": 1.5, "target_rr": 1.5, "max_prev_day_range_pct": 0.010}),
        ("vwap_regime_wide",   "vwap_reversion", {"deviation_pct": 0.003, "stop_multiple": 1.5, "target_rr": 2.0, "max_prev_day_range_pct": 0.012}),
        # No regime filter — baseline comparison
        ("vwap_no_filter",     "vwap_reversion", {"deviation_pct": 0.003, "stop_multiple": 1.5, "target_rr": 1.5, "max_prev_day_range_pct": 0.0}),
    ]

    def __init__(
        self,
        open_time: dt.time = dt.time(9, 30),
        deviation_pct: float = 0.002,
        stop_multiple: float = 2.0,
        target_rr: float = 1.5,
        max_prev_day_range_pct: float = 0.010,
        max_entry_time: dt.time = dt.time(13, 0),
        hard_exit_time: dt.time = dt.time(15, 45),
        min_volume: float = 0.0,
    ):
        self.open_time = open_time
        self.deviation_pct = deviation_pct
        self.stop_multiple = stop_multiple
        self.target_rr = target_rr
        self.max_prev_day_range_pct = max_prev_day_range_pct
        self.max_entry_time = max_entry_time
        self.hard_exit_time = hard_exit_time
        self.min_volume = min_volume

    def _open_dt(self, bar_time: dt.datetime) -> dt.datetime:
        return dt.datetime.combine(bar_time.date(), self.open_time, tzinfo=bar_time.tzinfo)

    def _vwap(self, ctx: StrategyContext, open_dt: dt.datetime) -> float | None:
        """Compute cumulative VWAP from session open through current bar."""
        session_bars = [b for b in ctx.bars if b.time >= open_dt]
        sum_pv = sum(b.price * b.volume for b in session_bars)
        sum_v = sum(b.volume for b in session_bars)
        if sum_v == 0:
            return None
        return sum_pv / sum_v

    def _prev_day_range_pct(self, ctx: StrategyContext, today: dt.date) -> float | None:
        """
        Intraday range of the prior calendar day as a fraction of mid-price.
        Returns None if no prior-day bars exist yet (e.g. first day of data).
        """
        prev_date = today - dt.timedelta(days=1)
        # Walk back up to 7 calendar days to find the most recent trading day
        for _ in range(7):
            prev_bars = [b for b in ctx.bars if b.time.date() == prev_date]
            if prev_bars:
                hi = max(b.price for b in prev_bars)
                lo = min(b.price for b in prev_bars)
                mid = (hi + lo) / 2
                return (hi - lo) / mid if mid > 0 else None
            prev_date -= dt.timedelta(days=1)
        return None

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        reset_session_if_new_day(ctx, bar)

        open_dt = self._open_dt(bar.time)
        if ctx.hard_exit_time is None:
            ctx.hard_exit_time = dt.datetime.combine(
                bar.time.date(), self.hard_exit_time, tzinfo=bar.time.tzinfo
            )
        max_entry_dt = dt.datetime.combine(
            bar.time.date(), self.max_entry_time, tzinfo=bar.time.tzinfo
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
                ctx.extra["close_reason"] = "stop" if hit_stop else "target" if hit_target else "time_box"
                ctx.extra["close_now"] = True
            return

        if ctx.trades_taken >= self.max_trades_per_session:
            return
        if bar.time < open_dt or bar.time >= max_entry_dt:
            return
        if self.min_volume > 0 and bar.volume < self.min_volume:
            return

        # Regime filter: skip if prior day was a trending/volatile session
        if self.max_prev_day_range_pct > 0:
            prev_range = self._prev_day_range_pct(ctx, bar.time.date())
            if prev_range is None or prev_range > self.max_prev_day_range_pct:
                return

        vwap = self._vwap(ctx, open_dt)
        if vwap is None:
            return

        deviation = (bar.price - vwap) / vwap

        if deviation < -self.deviation_pct:
            direction = "long"
        elif deviation > self.deviation_pct:
            direction = "short"
        else:
            return

        entry = bar.price
        entry_deviation = abs(bar.price - vwap)
        stop_dist = entry_deviation * self.stop_multiple
        target_dist = stop_dist * self.target_rr

        if direction == "long":
            ctx.stop_price = entry - stop_dist
            ctx.target_price = entry + target_dist
        else:
            ctx.stop_price = entry + stop_dist
            ctx.target_price = entry - target_dist

        ctx.position_open = True
        ctx.entry_price = entry
        ctx.entry_time = bar.time
        ctx.direction = direction
        ctx.trades_taken += 1
        ctx.extra["entry_reason"] = (
            f"VWAP reversion {direction}: price={entry:.2f} vwap={vwap:.2f} "
            f"deviation={deviation:+.3%}"
        )
        ctx.extra["vwap_at_entry"] = vwap
