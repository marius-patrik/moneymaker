"""
Intraday VWAP mean-reversion.

STUB — structure only, on_bar not yet implemented.

Premise:
  VWAP (volume-weighted average price) acts as a daily fair-value anchor for
  institutional order flow. Price deviations of N% from VWAP tend to revert
  during low-volatility sessions. Short above VWAP + buffer; long below.

Approach:
  1. Track cumulative VWAP from the session open (9:30 ET).
     VWAP = Σ(price × volume) / Σ(volume), updated bar-by-bar.
     Note: yfinance 5m bars include volume — this is implementable.
  2. Enter long when price is > deviation_pct below VWAP.
     Enter short when price is > deviation_pct above VWAP.
  3. Stop: further deviation (e.g., 2× the entry deviation from VWAP).
  4. Target: return to VWAP.
  5. Do not enter after 13:00 (low-liquidity afternoon drift).

Why it might work:
  Institutional algorithmic systems use VWAP as a benchmark. Large sellers push
  price below VWAP, then revert as they finish. Reversion is most reliable in
  the morning session with good volume.

Why it might not:
  On trend days, price can stay far from VWAP for hours without reverting.
  Works best in range-bound/choppy conditions — the opposite of a momentum day.
  Needs a volatility filter or trend-regime classifier to avoid trending days.

Known implementation requirement:
  Needs the Volume column from yfinance. The engine currently only passes Close
  to bars. Engine or Bar class may need to be extended to carry volume.

Parameters to explore:
  deviation_pct: 0.1%, 0.2%, 0.3%
  stop_multiple: 1.5, 2.0 (× entry deviation)
  max_entry_time: 13:00 or 14:00
  min_volume_ratio: require current bar volume > N× session average
"""

from __future__ import annotations

import datetime as dt

from moneymaker.strategy import Bar, Strategy, StrategyContext, reset_session_if_new_day


class VwapReversionStrategy(Strategy):
    """Intraday VWAP mean-reversion — stub, not yet implemented."""

    name = "vwap_reversion"

    def __init__(
        self,
        open_time: dt.time = dt.time(9, 30),
        deviation_pct: float = 0.002,
        stop_multiple: float = 2.0,
        max_entry_time: dt.time = dt.time(13, 0),
    ):
        self.open_time = open_time
        self.deviation_pct = deviation_pct
        self.stop_multiple = stop_multiple
        self.max_entry_time = max_entry_time

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        raise NotImplementedError(
            "vwap_reversion is a stub. Implement on_bar before backtesting. "
            "Note: requires volume data — engine Bar class needs extending."
        )
