"""
Example drop-in strategy. Copy this file (or a modified version of it) to
your <MONEYMAKER_HOME>/strategies/ directory and it will be auto-loaded
alongside the built-ins — no need to edit the moneymaker package at all.
"""

from src.strategy import Bar, Strategy, StrategyContext


class ExampleMomentum(Strategy):
    """Trivial example: enters long on the first bar, exits on a 0.1% move either way."""

    name = "example_momentum"

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        if ctx.position_open:
            change = (bar.price - ctx.entry_price) / ctx.entry_price
            if abs(change) >= 0.001:
                ctx.extra["close_reason"] = "target" if change > 0 else "stop"
                ctx.extra["close_now"] = True
            return

        if ctx.trades_taken >= 1:
            return

        ctx.position_open = True
        ctx.entry_price = bar.price
        ctx.entry_time = bar.time
        ctx.direction = "long"
        ctx.stop_price = bar.price * 0.999
        ctx.target_price = bar.price * 1.001
        ctx.trades_taken += 1
        ctx.extra["entry_reason"] = "example: first bar entry"
