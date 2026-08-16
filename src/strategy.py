"""Strategy interface, built-in strategies, and drop-in strategy loading."""

from __future__ import annotations

import datetime as dt
import importlib.util
import inspect
import os
import pathlib
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Bar:
    time: dt.datetime
    price: float
    volume: float = 0.0


@dataclass
class StrategyContext:
    """State a strategy can read/write as bars stream in. Reset per session."""
    bars: list[Bar] = field(default_factory=list)
    position_open: bool = False
    entry_price: Optional[float] = None
    entry_time: Optional[dt.datetime] = None
    direction: Optional[str] = None  # "long" or "short"
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    hard_exit_time: Optional[dt.datetime] = None
    trades_taken: int = 0
    extra: dict = field(default_factory=dict)
    # If > 0, ctx.bars is capped to the most recent max_bars entries after
    # each append. Strategies with absolute-time lookbacks (e.g. "5 min before
    # 8:30") must set this large enough to cover their full lookback window.
    max_bars: int = 0


class Strategy(ABC):
    """
    Subclass this to define a new strategy. Drop the .py file in
    <home>/strategies/ and it's auto-loaded alongside built-ins — no need
    to touch this package. The simulator calls on_bar() for every new
    price bar (historical or live) and expects it to mutate ctx to
    open/close a position. Keep logic pure price-action so it behaves
    identically in backtest and live modes.

    Class-level FORKS is a list of (name, cls, params_dict) tuples naming
    alternative implementations for automatic fork-eval. Fork-eval runs all
    variants over the same windows and ranks by the default objective score.
    """

    name: str = "base"
    max_trades_per_session: int = 1
    # FORKS: list of (label, strategy_name, params_dict) triples declaring
    # variants to compare via `fork-eval`. Strategy names (strings) are
    # resolved through load_strategies at eval time — no class import needed.
    FORKS: list[tuple[str, str, dict[str, Any]]] = []

    @abstractmethod
    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        raise NotImplementedError

    @classmethod
    def params(cls) -> dict[str, Any]:
        """Return {param_name: default_value} for all __init__ parameters."""
        sig = inspect.signature(cls.__init__)
        return {
            name: param.default
            for name, param in sig.parameters.items()
            if name != "self" and param.default is not inspect.Parameter.empty
        }

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> "Strategy":
        """Instantiate this strategy from a params dict (ignores unknown keys)."""
        valid = set(inspect.signature(cls.__init__).parameters) - {"self"}
        return cls(**{k: v for k, v in params.items() if k in valid})


def reset_session_if_new_day(ctx: StrategyContext, bar: Bar) -> None:
    """
    Time-boxed, daily-recurring strategies (data-release strategies, and
    likely most others tied to a specific clock time) need their
    per-session state reset when a new calendar day starts within a
    single continuous backtest or live run. Without this, state left
    over from day one — trades_taken, hard_exit_time — silently blocks
    every subsequent day: hard_exit_time stays pinned to day one's
    cutoff, so every later bar looks "timed out" before the strategy
    ever gets a chance to look at it.

    Call this at the very top of on_bar(), but only when no position is
    open — if a position is somehow still open when the date rolls over
    (e.g. a data gap prevented the time-box exit from firing exactly on
    schedule), we deliberately do NOT reset here. Leaving the stale
    hard_exit_time in place forces an immediate time-boxed close on the
    next bar instead of silently carrying a supposedly-intraday position
    across an indefinite gap.
    """
    if ctx.position_open:
        return
    session_date = ctx.extra.get("session_date")
    if session_date == bar.time.date():
        return
    ctx.extra["session_date"] = bar.time.date()
    ctx.trades_taken = 0
    ctx.hard_exit_time = None
    # Clear any per-session scratch state a strategy may have cached
    # (e.g. a filtered strategy's signal_evaluated/signal_valid flags).
    for key in list(ctx.extra.keys()):
        if key not in ("session_date",):
            ctx.extra.pop(key, None)


class MultiBarStrategy(Strategy):
    """
    Strategy that observes bars from multiple tickers before deciding to trade.

    Subclass this to implement cross-asset confirmation filters, relative-value
    strategies, or any strategy that needs correlated data from more than one
    instrument (e.g. ES=F enters only when NQ=F confirms the move).

    How the engine feeds bars:
      - Bars from the PRIMARY ticker (tickers[0]) are fed via the standard
        on_bar() call — same as a regular Strategy.
      - Bars from SECONDARY tickers are fed via on_secondary_bar(). Store
        whatever you need in ctx.extra so on_bar() can access it.

    MultiBarSimulator (engine/engine.py) handles the multi-ticker logic.
    Existing Simulator is unchanged and still works for single-ticker strategies.

    Example:
        class ESWithNQConfirmation(MultiBarStrategy):
            name = "es_nq_confirm"
            tickers = ["ES=F", "NQ=F"]   # ES = primary, NQ = confirmation

            def on_secondary_bar(self, ctx, bar, ticker):
                ctx.extra[f"last_{ticker}"] = bar.price

            def on_bar(self, ctx, bar):
                nq = ctx.extra.get("last_NQ=F")
                if nq is None:
                    return  # no NQ data yet
                # ... rest of entry logic
    """

    tickers: list[str] = []  # override in subclass; first entry is the primary

    def on_secondary_bar(self, ctx: StrategyContext, bar: Bar, ticker: str) -> None:
        """Called for each bar from a secondary ticker. Default is a no-op."""
        pass

    # on_bar() is still abstract (inherited from Strategy) — subclass must implement it.


class RetailSalesSpikeStrategy(Strategy):
    """
    Data-release fade/breakout strategy:
      1. Establish a pre-release baseline price.
      2. Watch the initial spike window after release.
      3. Enter once price "bases" (holds a tight range for N consecutive
         bars) in the direction of the post-spike hold.
      4. Fixed % stop-loss and target, hard time-box exit.

    Note: stop_price/target_price are computed from the raw signal price
    at entry (bar.price), not the slippage-adjusted fill. At typical
    slippage this is a small effect (the realized stop distance ends up
    a hair tighter than configured), but it means the *stated* stop_pct
    isn't exactly the *realized* one. Worth knowing if you're tuning
    stop_pct against live P&L rather than just backtest output.
    """

    name = "retail_sales_spike"
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
    ):
        self.release_time = release_time
        self.baseline_minutes = baseline_minutes
        self.spike_window_min = spike_window_min
        self.base_bars = base_bars
        self.base_tolerance_pct = base_tolerance_pct
        self.stop_pct = stop_pct
        self.target_pct = target_pct
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
        ctx.extra["baseline"] = baseline

        spike_end = release_dt + dt.timedelta(minutes=self.spike_window_min)
        if bar.time < spike_end:
            return

        post_spike_bars = [b for b in ctx.bars if b.time >= spike_end]
        if len(post_spike_bars) < self.base_bars:
            return
        recent = post_spike_bars[-self.base_bars:]
        prices = [b.price for b in recent]
        rng_pct = (max(prices) - min(prices)) / baseline
        if rng_pct > self.base_tolerance_pct:
            return

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
        ctx.extra["entry_reason"] = f"based {direction} after spike, baseline={baseline:.2f}"


BUILTIN_STRATEGIES: dict[str, type[Strategy]] = {
    RetailSalesSpikeStrategy.name: RetailSalesSpikeStrategy,
}


def _load_strategy_dir(strategies: dict, strat_dir: str, label: str) -> None:
    """Scan one directory for Strategy subclasses and merge into strategies dict."""
    if not os.path.isdir(strat_dir):
        return
    for fname in sorted(os.listdir(strat_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(strat_dir, fname)
        modname = f"moneymaker_{label}_{fname[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(modname, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for attr in vars(mod).values():
                if (isinstance(attr, type) and issubclass(attr, Strategy)
                        and attr is not Strategy and getattr(attr, "name", "base") != "base"):
                    strategies[attr.name] = attr
        except Exception as e:
            print(f"warning: failed to load strategy file {fname}: {e}", file=sys.stderr)
            # The engine/ package was renamed to src/ in 0.3.1. Installed
            # copies from before that still import `engine.*` and fail here,
            # which otherwise just looks like the strategy vanished.
            if isinstance(e, ModuleNotFoundError) and e.name == "engine":
                print("         this copy predates the engine/ → src/ rename — "
                      "run `moneymaker upgrade-strategies` to refresh it.",
                      file=sys.stderr)


def load_strategies(home: str) -> dict[str, type[Strategy]]:
    """
    Built-ins + repo-bundled strategies/ dir + <home>/strategies/ drop-ins.

    Load order (later entries win on name collision):
      1. BUILTIN_STRATEGIES (hardcoded in this file)
      2. strategies/ dir next to this package (repo-bundled, always up-to-date)
      3. <home>/strategies/ drop-ins (user-added or overrides)
    """
    strategies = dict(BUILTIN_STRATEGIES)
    # Repo-bundled: strategies/ sits one level above this package dir
    repo_strategies = pathlib.Path(__file__).parent.parent / "strategies"
    _load_strategy_dir(strategies, str(repo_strategies), "bundled")
    # User drop-ins: ~/.moneymaker/strategies/ (or override via --data-dir)
    _load_strategy_dir(strategies, os.path.join(home, "strategies"), "user")
    return strategies
