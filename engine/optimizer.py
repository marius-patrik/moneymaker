"""
Parameter "training" for strategies: grid search over a parameter space,
evaluated via multi-window backtests, with an explicit train/test split.

Important framing: this is NOT machine learning, and nothing here learns
from live trading. It's systematic grid search — try every combination
of the parameter values you give it, score each on the training windows,
and separately check the winners against held-out test windows they
never touched during scoring. That train/test split exists specifically
to catch overfitting: a strategy that only looks good on the days you
tuned it against is worse than useless.

With a small number of real historical event days available (which is
the realistic case for something like a monthly data release), overfitting
risk is real regardless of this safeguard. Treat results as a starting
point for further live-paper validation, not a guarantee — and be
suspicious of any candidate whose test performance is much worse than
its train performance.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from engine.multiwindow import run_multi_window_backtest


@dataclass
class CandidateResult:
    params: dict
    train_summary: dict
    test_summary: Optional[dict] = None

    def to_dict(self) -> dict:
        return {"params": self.params, "train_summary": self.train_summary, "test_summary": self.test_summary}


@dataclass
class OptimizationResult:
    candidates: list[CandidateResult] = field(default_factory=list)

    def ranked(self, key: Callable[[dict], float]) -> list[CandidateResult]:
        return sorted(self.candidates, key=lambda c: key(c.train_summary), reverse=True)

    def to_dict(self, key: Callable[[dict], float]) -> dict:
        return {"candidates": [c.to_dict() for c in self.ranked(key)]}


def default_objective(summary: dict) -> float:
    """
    Mean P&L per window, scaled by consistency (% of windows profitable)
    and lightly penalized for variance across windows. A strategy that
    never trades scores exactly 0 (not an artificially high average from
    an empty/zero-trade window), and a strategy that's wildly inconsistent
    across windows is penalized relative to one that's steadily mediocre.
    """
    if summary.get("valid_windows", 0) == 0:
        return float("-inf")
    mean_pnl = summary.get("mean_pnl_per_window", 0.0)
    stdev = summary.get("pnl_stdev", 0.0)
    consistency = summary.get("pct_windows_profitable", 0.0)
    return mean_pnl * (0.5 + 0.5 * consistency) - 0.1 * stdev


def grid_search(
    strategy_cls,
    param_grid: dict[str, list[Any]],
    provider_name: str,
    home: str,
    ticker: str,
    train_windows: list[tuple[str, str]],
    test_windows: Optional[list[tuple[str, str]]] = None,
    interval: str = "5m",
    account_balance: float = 10000.0,
    risk_pct: float = 0.01,
    get_data_fn: Optional[Callable] = None,
) -> OptimizationResult:
    """
    Tries every combination of param_grid's values against strategy_cls,
    scoring each on train_windows. If test_windows is given, also
    evaluates every candidate (not just the winner) against them, so you
    can see the train/test gap for every candidate, not just the one
    that happened to win on training data.
    """
    keys = list(param_grid.keys())
    value_lists = [param_grid[k] for k in keys]
    result = OptimizationResult()

    for combo in itertools.product(*value_lists):
        params = dict(zip(keys, combo))

        def factory(params=params):
            return strategy_cls(**params)

        train_result = run_multi_window_backtest(
            factory, provider_name, home, ticker, train_windows,
            interval=interval, account_balance=account_balance, risk_pct=risk_pct,
            get_data_fn=get_data_fn,
        )
        train_summary = train_result.summary()

        test_summary = None
        if test_windows:
            test_result = run_multi_window_backtest(
                factory, provider_name, home, ticker, test_windows,
                interval=interval, account_balance=account_balance, risk_pct=risk_pct,
                get_data_fn=get_data_fn,
            )
            test_summary = test_result.summary()

        result.candidates.append(CandidateResult(params=params, train_summary=train_summary, test_summary=test_summary))

    return result
