"""
Fork-and-eval: run N strategy variants (forks) over identical windows and rank
them by the default objective score.

A Fork is a (name, cls, params_dict) triple describing one variant. Results are
returned ranked best-to-worst so the caller can immediately act on the winner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from engine.multiwindow import run_multi_window_backtest
from engine.optimizer import default_objective


@dataclass
class ForkResult:
    name: str
    params: dict[str, Any]
    summary: dict
    score: float

    def __str__(self) -> str:
        s = self.summary
        return (
            f"{self.name}: score={self.score:+.2f}  "
            f"trades={s.get('total_trades', 0)}  "
            f"win_rate={s.get('overall_win_rate', 0):.1%}  "
            f"pnl={s.get('total_pnl', 0):+.2f}"
        )


@dataclass
class ForkSetResult:
    forks: list[ForkResult] = field(default_factory=list)

    @property
    def winner(self) -> Optional[ForkResult]:
        return self.forks[0] if self.forks else None

    def ranked(self) -> list[ForkResult]:
        return self.forks  # already sorted on construction

    def to_dict(self) -> dict:
        return {
            "winner": self.winner.name if self.winner else None,
            "forks": [
                {
                    "name": f.name,
                    "params": f.params,
                    "summary": f.summary,
                    "score": f.score,
                }
                for f in self.forks
            ],
        }


def fork_and_eval(
    forks: list[tuple[str, type, dict[str, Any]]],
    provider_name: str,
    home: str,
    ticker: str,
    windows: list[tuple[str, str]],
    interval: str = "5m",
    account_balance: float = 10000.0,
    risk_pct: float = 0.01,
    objective: Callable[[dict], float] = default_objective,
    get_data_fn=None,
) -> ForkSetResult:
    """
    Evaluate each (name, cls, params) fork over the same windows and rank by
    objective score. Identical windows for all forks means differences in score
    come purely from strategy behavior, not from data variation.
    """
    results: list[ForkResult] = []
    for name, cls, params in forks:
        def factory(c=cls, p=params):
            return c.from_params(p)

        mw = run_multi_window_backtest(
            factory, provider_name, home, ticker, windows,
            interval=interval, account_balance=account_balance,
            risk_pct=risk_pct, get_data_fn=get_data_fn,
        )
        summary = mw.summary()
        score = objective(summary)
        results.append(ForkResult(name=name, params=params, summary=summary, score=score))

    results.sort(key=lambda r: r.score, reverse=True)
    return ForkSetResult(forks=results)
