"""
Momentum continuation after data release.

STUB — structure only, on_bar not yet implemented.

Premise:
  Opposite of the spike-fade approach: instead of waiting for price to base
  and then fading the spike, enter IN the direction of the spike as soon as
  a momentum signal confirms continuation. The idea is that large surprise
  releases (not just noisy ones) produce multi-hour directional moves.

Approach:
  1. Same baseline + spike window as retail_sales_spike.
  2. Require a minimum spike size (larger than the fade version — we want
     conviction, not noise).
  3. Enter in the DIRECTION of the spike on the first bar that shows
     momentum confirmation: e.g., consecutive closes in the spike direction,
     or a bar close above/below the prior bar's high/low.
  4. Stop: below the spike low (for longs) / above the spike high (for shorts).
  5. Target: 1.5–2× the spike magnitude beyond entry.
  6. Trailing stop once 1:1 is reached.

Why this might work differently from the fade:
  On strong data surprises, price often continues for hours rather than
  reversing. The fade strategy fades EVERY spike regardless of size;
  momentum continuation only trades the large ones.

Why it might not:
  ES is highly efficient at pricing macro surprises quickly. By the time a
  5m bar closes above the spike high, much of the move may already be done.
  Needs real-data verification across multiple release types (CPI, NFP, etc.)
  before drawing conclusions from retail sales alone.

Parameters to explore:
  min_spike_pct: minimum spike to qualify (try 0.10–0.20%)
  confirmation_bars: consecutive bars needed (1–3)
  trailing_stop_pct: trailing stop distance once profitable
  target_spike_multiple: target at N× the spike size beyond entry
"""

from __future__ import annotations

import datetime as dt

from moneymaker.strategy import Bar, Strategy, StrategyContext


class MomentumContinuationStrategy(Strategy):
    """Momentum continuation after data release — stub, not yet implemented."""

    name = "momentum_continuation"

    def __init__(
        self,
        release_time: dt.time = dt.time(8, 30),
        spike_window_min: int = 5,
        min_spike_pct: float = 0.0015,
        confirmation_bars: int = 2,
        trailing_stop_pct: float = 0.003,
        target_spike_multiple: float = 1.5,
        hard_exit_time: dt.time = dt.time(12, 0),
    ):
        self.release_time = release_time
        self.spike_window_min = spike_window_min
        self.min_spike_pct = min_spike_pct
        self.confirmation_bars = confirmation_bars
        self.trailing_stop_pct = trailing_stop_pct
        self.target_spike_multiple = target_spike_multiple
        self.hard_exit_time = hard_exit_time

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        raise NotImplementedError(
            "momentum_continuation is a stub. Implement on_bar before backtesting."
        )
