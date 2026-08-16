"""
Hill-climbing evolution: iteratively perturb a strategy's parameters and keep
changes that improve the objective score. Not a learning algorithm — it's
systematic local search, the same kind of thing a careful analyst would do by
hand, just faster and logged.

Each generation tries perturbing each numeric parameter up and down by
`perturbation_pct`. Non-numeric params are left untouched (they'd need a
discrete mutation, which is out of scope here). Converges when no single
perturbation improves the score, or when max_generations is reached.
"""

from __future__ import annotations

import copy
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from engine.agents.forker import fork_and_eval, ForkResult
from engine.optimizer import default_objective


@dataclass
class EvolutionStep:
    generation: int
    best_params: dict[str, Any]
    best_score: float
    improved: bool
    candidate_name: str = ""


@dataclass
class EvolutionResult:
    best_params: dict[str, Any]
    best_score: float
    steps: list[EvolutionStep] = field(default_factory=list)
    generations_run: int = 0

    def to_dict(self) -> dict:
        return {
            "best_params": self.best_params,
            "best_score": self.best_score,
            "generations_run": self.generations_run,
            "steps": [
                {
                    "generation": s.generation,
                    "best_params": s.best_params,
                    "best_score": s.best_score,
                    "improved": s.improved,
                    "candidate_name": s.candidate_name,
                }
                for s in self.steps
            ],
        }


def _perturb(params: dict[str, Any], key: str, factor: float) -> dict[str, Any]:
    p = copy.copy(params)
    val = p[key]
    if isinstance(val, float):
        p[key] = val * factor
    elif isinstance(val, int) and not isinstance(val, bool):
        candidate = round(val * factor)
        p[key] = max(1, candidate)
    return p


def evolve(
    strategy_cls: type,
    provider_name: str,
    home: str,
    ticker: str,
    windows: list[tuple[str, str]],
    start_params: Optional[dict[str, Any]] = None,
    max_generations: int = 20,
    perturbation_pct: float = 0.20,
    interval: str = "5m",
    account_balance: float = 10000.0,
    risk_pct: float = 0.01,
    objective: Callable[[dict], float] = default_objective,
    get_data_fn=None,
    verbose: bool = True,
) -> EvolutionResult:
    """
    Hill-climb strategy_cls's numeric parameters starting from start_params
    (or the class defaults if omitted).

    Each generation tries ±perturbation_pct on every numeric parameter,
    keeping any improvement, until no improvement is found or max_generations
    is exhausted.
    """
    params = dict(start_params or strategy_cls.params())
    numeric_keys = [k for k, v in params.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]

    # Score the baseline
    baseline = fork_and_eval(
        [("baseline", strategy_cls, params)],
        provider_name, home, ticker, windows,
        interval=interval, account_balance=account_balance,
        risk_pct=risk_pct, objective=objective, get_data_fn=get_data_fn,
    )
    best_score = baseline.winner.score if baseline.winner else float("-inf")
    best_params = dict(params)
    steps: list[EvolutionStep] = []

    if verbose:
        print(f"[evolve] baseline score={best_score:+.2f}  params={best_params}")

    for gen in range(max_generations):
        improved = False
        best_candidate_name = ""

        for key in numeric_keys:
            factor_up = 1.0 + perturbation_pct
            factor_down = 1.0 - perturbation_pct

            candidates = [
                (f"gen{gen+1}_{key}+{perturbation_pct:.0%}", _perturb(best_params, key, factor_up)),
                (f"gen{gen+1}_{key}-{perturbation_pct:.0%}", _perturb(best_params, key, factor_down)),
            ]
            forks = [(name, strategy_cls, p) for name, p in candidates]
            result = fork_and_eval(
                forks, provider_name, home, ticker, windows,
                interval=interval, account_balance=account_balance,
                risk_pct=risk_pct, objective=objective, get_data_fn=get_data_fn,
            )
            if result.winner and result.winner.score > best_score:
                best_score = result.winner.score
                best_params = dict(result.winner.params)
                best_candidate_name = result.winner.name
                improved = True
                if verbose:
                    print(f"[evolve] gen={gen+1} improved via {result.winner.name}: "
                          f"score={best_score:+.2f}  params={best_params}")

        steps.append(EvolutionStep(
            generation=gen + 1,
            best_params=dict(best_params),
            best_score=best_score,
            improved=improved,
            candidate_name=best_candidate_name,
        ))

        if not improved:
            if verbose:
                print(f"[evolve] gen={gen+1} no improvement — converged after {gen+1} generation(s)")
            break

    return EvolutionResult(
        best_params=best_params,
        best_score=best_score,
        steps=steps,
        generations_run=len(steps),
    )
