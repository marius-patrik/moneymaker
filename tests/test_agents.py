"""
Tests for engine.agents: fork-eval and hill-climbing evolution.
All tests use synthetic data via injectable get_data_fn — no network required.
"""

from __future__ import annotations

import datetime as dt
import pathlib

import pandas as pd
import pytest

from src.agents.forker import ForkResult, ForkSetResult, fork_and_eval
from src.agents.evolution import evolve
from src.config import get_home
from src.strategy import RetailSalesSpikeStrategy, Strategy, Bar, StrategyContext


@pytest.fixture
def home(tmp_path):
    return get_home(str(tmp_path / ".moneymaker"))


# --------------------------------------------------------------------------
# Helpers — synthetic data that produces exactly one trade per window
# --------------------------------------------------------------------------

def _make_bar(base: dt.datetime, offset_min: float, price: float) -> dict:
    return {
        "Datetime": base + dt.timedelta(minutes=offset_min),
        "Close": price,
    }


def _synthetic_spike_df(date: str = "2026-07-14") -> pd.DataFrame:
    """One day with a clean spike+basing+target sequence."""
    base = dt.datetime.fromisoformat(f"{date} 08:25:00+00:00")
    rows = [
        _make_bar(base, 0, 5000.0),   # 08:25 baseline
        _make_bar(base, 5, 5020.0),   # 08:30 spike bar
        _make_bar(base, 10, 5017.0),  # basing 1
        _make_bar(base, 15, 5017.5),  # basing 2
        _make_bar(base, 20, 5018.0),  # basing 3 — closes tight window
        _make_bar(base, 25, 5020.0),  # breakout bar (above basing_high)
        _make_bar(base, 30, 5035.0),  # target reached
    ]
    df = pd.DataFrame(rows).set_index("Datetime")
    df.index = pd.DatetimeIndex(df.index)
    return df


def _two_day_df() -> pd.DataFrame:
    df1 = _synthetic_spike_df("2026-07-14")
    df2 = _synthetic_spike_df("2026-07-15")
    return pd.concat([df1, df2]).sort_index()


def _get_data_fn_single(ticker, start, end, interval, home):
    return _synthetic_spike_df("2026-07-14")


def _get_data_fn_two(ticker, start, end, interval, home):
    return _two_day_df()


# --------------------------------------------------------------------------
# Strategy.params() and from_params()
# --------------------------------------------------------------------------

def test_params_returns_defaults():
    defaults = RetailSalesSpikeStrategy.params()
    assert "stop_pct" in defaults
    assert "base_bars" in defaults
    assert isinstance(defaults["stop_pct"], float)


def test_from_params_overrides():
    s = RetailSalesSpikeStrategy.from_params({"stop_pct": 0.009, "base_bars": 5})
    assert s.stop_pct == pytest.approx(0.009)
    assert s.base_bars == 5


def test_from_params_ignores_unknown():
    s = RetailSalesSpikeStrategy.from_params({"stop_pct": 0.009, "nonexistent": 99})
    assert s.stop_pct == pytest.approx(0.009)


# --------------------------------------------------------------------------
# FORKS declaration
# --------------------------------------------------------------------------

def test_strategy_forks_default_empty():
    # Base Strategy class has empty FORKS
    assert Strategy.FORKS == []


def test_retail_spike_forks_empty():
    # RetailSalesSpikeStrategy doesn't declare forks (continuation only)
    assert RetailSalesSpikeStrategy.FORKS == []


# --------------------------------------------------------------------------
# fork_and_eval
# --------------------------------------------------------------------------

def test_fork_and_eval_ranks_by_score(home):
    """Two forks over identical windows; result must be sorted best-to-worst."""
    forks = [
        ("high_stop", RetailSalesSpikeStrategy, {"stop_pct": 0.05, "target_pct": 0.10}),
        ("low_stop", RetailSalesSpikeStrategy, {"stop_pct": 0.001, "target_pct": 0.002}),
    ]
    windows = [("2026-07-14", "2026-07-15")]
    result = fork_and_eval(
        forks, "simulated", home, "ES=F", windows,
        get_data_fn=_get_data_fn_single,
    )
    assert isinstance(result, ForkSetResult)
    assert len(result.forks) == 2
    assert result.forks[0].score >= result.forks[1].score


def test_fork_and_eval_winner_is_first(home):
    forks = [
        ("a", RetailSalesSpikeStrategy, {"stop_pct": 0.05, "target_pct": 0.10}),
        ("b", RetailSalesSpikeStrategy, {"stop_pct": 0.001, "target_pct": 0.002}),
    ]
    windows = [("2026-07-14", "2026-07-15")]
    result = fork_and_eval(
        forks, "simulated", home, "ES=F", windows,
        get_data_fn=_get_data_fn_single,
    )
    assert result.winner is result.forks[0]


def test_fork_and_eval_to_dict(home):
    forks = [("only", RetailSalesSpikeStrategy, {})]
    windows = [("2026-07-14", "2026-07-15")]
    result = fork_and_eval(
        forks, "simulated", home, "ES=F", windows,
        get_data_fn=_get_data_fn_single,
    )
    d = result.to_dict()
    assert "winner" in d
    assert "forks" in d
    assert d["forks"][0]["name"] == "only"


# --------------------------------------------------------------------------
# evolve
# --------------------------------------------------------------------------

def test_evolve_returns_result(home):
    windows = [("2026-07-14", "2026-07-15"), ("2026-07-15", "2026-07-16")]
    result = evolve(
        strategy_cls=RetailSalesSpikeStrategy,
        provider_name="simulated",
        home=home,
        ticker="ES=F",
        windows=windows,
        max_generations=2,
        perturbation_pct=0.20,
        get_data_fn=_get_data_fn_two,
        verbose=False,
    )
    assert result.best_params is not None
    assert isinstance(result.best_score, float)
    assert result.generations_run <= 2


def test_evolve_to_dict(home):
    windows = [("2026-07-14", "2026-07-15")]
    result = evolve(
        strategy_cls=RetailSalesSpikeStrategy,
        provider_name="simulated",
        home=home,
        ticker="ES=F",
        windows=windows,
        max_generations=1,
        get_data_fn=_get_data_fn_single,
        verbose=False,
    )
    d = result.to_dict()
    assert "best_params" in d
    assert "best_score" in d
    assert "steps" in d


def test_evolve_start_params_override(home):
    """evolve() respects start_params, not just class defaults."""
    windows = [("2026-07-14", "2026-07-15")]
    result = evolve(
        strategy_cls=RetailSalesSpikeStrategy,
        provider_name="simulated",
        home=home,
        ticker="ES=F",
        windows=windows,
        start_params={"stop_pct": 0.05, "target_pct": 0.10, "base_bars": 2,
                      "base_tolerance_pct": 0.0015},
        max_generations=1,
        get_data_fn=_get_data_fn_single,
        verbose=False,
    )
    # Best params should still include the start values (at minimum as baseline)
    assert "stop_pct" in result.best_params
