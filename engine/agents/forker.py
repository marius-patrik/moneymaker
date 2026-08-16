"""
Fork-and-eval: run N strategy variants (forks) over identical windows and rank
them by the default objective score.

A Fork is a (name, cls, params_dict) triple describing one variant. Results are
returned ranked best-to-worst so the caller can immediately act on the winner.

Rolling eval (P011): run fork-eval repeatedly as the evaluation window slides
forward in time. Results are appended to a JSON file in the evaluations/ dir so
that score trajectories accumulate across multiple runs.
"""

from __future__ import annotations

import datetime as dt
import json
import os
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


# ---------------------------------------------------------------------------
# Rolling evaluation (P011)
# ---------------------------------------------------------------------------

@dataclass
class RollingEntry:
    """One evaluation run: a window range + scores for each fork at that point."""
    window_start: str
    window_end: str
    evaluated_at: str
    forks: list[dict]  # [{name, score, summary}]

    def to_dict(self) -> dict:
        return {
            "window_start": self.window_start,
            "window_end": self.window_end,
            "evaluated_at": self.evaluated_at,
            "forks": self.forks,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RollingEntry":
        return cls(
            window_start=d["window_start"],
            window_end=d["window_end"],
            evaluated_at=d.get("evaluated_at", ""),
            forks=d.get("forks", []),
        )


@dataclass
class RollingEvalResult:
    strategy: str
    ticker: str
    entries: list[RollingEntry] = field(default_factory=list)

    def score_trajectory(self, fork_name: str) -> list[tuple[str, float]]:
        """Return [(window_end, score), ...] for a specific fork over time."""
        out = []
        for e in self.entries:
            for f in e.forks:
                if f["name"] == fork_name:
                    out.append((e.window_end, f["score"]))
                    break
        return out

    def fork_names(self) -> list[str]:
        if not self.entries:
            return []
        return [f["name"] for f in self.entries[-1].forks]

    def trend(self, fork_name: str, last_n: int = 3) -> str:
        """'improving', 'degrading', or 'flat' based on last N entries."""
        traj = self.score_trajectory(fork_name)
        if len(traj) < 2:
            return "insufficient data"
        scores = [s for _, s in traj[-last_n:]]
        delta = scores[-1] - scores[0]
        if delta > 0.5:
            return "improving"
        elif delta < -0.5:
            return "degrading"
        return "flat"

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "ticker": self.ticker,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RollingEvalResult":
        return cls(
            strategy=d["strategy"],
            ticker=d["ticker"],
            entries=[RollingEntry.from_dict(e) for e in d.get("entries", [])],
        )


def _evaluations_dir(home: str) -> str:
    path = os.path.join(home, "evaluations")
    os.makedirs(path, exist_ok=True)
    return path


def _rolling_path(home: str, strategy: str, ticker: str) -> str:
    safe_ticker = ticker.replace("=", "_").replace("/", "_")
    return os.path.join(_evaluations_dir(home), f"{strategy}_{safe_ticker}_rolling.json")


def _load_rolling(home: str, strategy: str, ticker: str) -> RollingEvalResult:
    path = _rolling_path(home, strategy, ticker)
    if os.path.exists(path):
        with open(path) as f:
            return RollingEvalResult.from_dict(json.load(f))
    return RollingEvalResult(strategy=strategy, ticker=ticker)


def _save_rolling(home: str, result: RollingEvalResult) -> str:
    path = _rolling_path(home, result.strategy, result.ticker)
    with open(path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    return path


def rolling_fork_eval(
    strategy_name: str,
    forks: list[tuple[str, type, dict[str, Any]]],
    provider_name: str,
    home: str,
    ticker: str,
    rolling_start: str,
    rolling_end: str,
    window_days: int,
    step_days: int,
    interval: str = "5m",
    account_balance: float = 10000.0,
    risk_pct: float = 0.01,
    objective: Callable[[dict], float] = default_objective,
) -> RollingEvalResult:
    """
    Slide a window of `window_days` days forward by `step_days` from
    rolling_start to rolling_end, running fork_and_eval at each step.
    Appends results to the persistent rolling JSON file so trajectories
    accumulate across multiple invocations.
    """
    result = _load_rolling(home, strategy_name, ticker)

    start = dt.date.fromisoformat(rolling_start)
    end = dt.date.fromisoformat(rolling_end)
    window = dt.timedelta(days=window_days)
    step = dt.timedelta(days=step_days)

    cursor = start
    steps_run = 0
    while cursor + window <= end:
        ws = cursor.isoformat()
        we = (cursor + window).isoformat()

        existing = {(e.window_start, e.window_end) for e in result.entries}
        if (ws, we) not in existing:
            print(f"  Rolling window {ws} → {we} ...")
            set_result = fork_and_eval(
                forks, provider_name, home, ticker, [(ws, we)],
                interval=interval, account_balance=account_balance, risk_pct=risk_pct,
                objective=objective,
            )
            entry = RollingEntry(
                window_start=ws,
                window_end=we,
                evaluated_at=dt.datetime.now().isoformat(timespec="seconds"),
                forks=[{"name": fr.name, "score": fr.score, "summary": fr.summary}
                       for fr in set_result.forks],
            )
            result.entries.append(entry)
            steps_run += 1
        else:
            print(f"  Skipping {ws} → {we} (already evaluated)")

        cursor += step

    if steps_run > 0:
        path = _save_rolling(home, result)
        print(f"Rolling results ({steps_run} new windows) saved to {path}")

    return result


def load_all_rolling(home: str) -> list[RollingEvalResult]:
    """Load all rolling eval files from the evaluations/ dir."""
    evdir = os.path.join(home, "evaluations")
    if not os.path.exists(evdir):
        return []
    results = []
    for fname in sorted(os.listdir(evdir)):
        if fname.endswith("_rolling.json"):
            with open(os.path.join(evdir, fname)) as f:
                try:
                    results.append(RollingEvalResult.from_dict(json.load(f)))
                except (json.JSONDecodeError, KeyError):
                    pass
    return results
