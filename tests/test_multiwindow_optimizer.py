"""
Tests for multiwindow.py and optimizer.py. Both take an injectable
get_data_fn, so these run entirely against synthetic per-window price
data — no network access needed.
"""

import datetime as dt

import pandas as pd
import pytest

from src.config import get_home
from src.multiwindow import run_multi_window_backtest
from src.optimizer import default_objective, grid_search
from src.strategy import RetailSalesSpikeStrategy


@pytest.fixture
def home(tmp_path):
    return get_home(str(tmp_path / ".moneymaker"))


def _prices_to_df(prices: list[float], base_time: dt.datetime) -> pd.DataFrame:
    idx = [base_time + dt.timedelta(minutes=i) for i in range(len(prices))]
    return pd.DataFrame({"Close": prices}, index=pd.DatetimeIndex(idx))


# A clear winning setup: calm baseline, real spike, holds, hits target.
WINNING_DAY_PRICES = [
    5000, 5001, 5000, 5000, 5001,
    5030, 5045, 5020, 5015, 5013,
    5014, 5013, 5013, 5012, 5030,
    5045, 5045,
    5090,
]

# A losing setup: same entry, but reverses hard and hits stop.
LOSING_DAY_PRICES = [
    5000, 5001, 5000, 5000, 5001,
    5030, 5045, 5020, 5015, 5013,
    5014, 5013, 5013, 5012, 5030,
    5045, 5045,
    5000,
]


def make_synthetic_data_fn(day_to_prices: dict[str, list[float]]):
    """Returns a get_data_fn keyed by the window's start date string."""
    def get_data_fn(ticker: str, start: str, end: str, interval: str) -> pd.DataFrame:
        prices = day_to_prices.get(start)
        if prices is None:
            raise ValueError(f"No synthetic data configured for window starting {start}")
        base_time = dt.datetime.strptime(start, "%Y-%m-%d").replace(hour=8, minute=20)
        return _prices_to_df(prices, base_time)
    return get_data_fn


# --------------------------------------------------------------------------
# Multi-window backtest
# --------------------------------------------------------------------------

def test_multi_window_aggregates_across_windows(home):
    data_fn = make_synthetic_data_fn({
        "2026-08-01": WINNING_DAY_PRICES,
        "2026-08-02": WINNING_DAY_PRICES,
        "2026-08-03": LOSING_DAY_PRICES,
    })
    result = run_multi_window_backtest(
        strategy_factory=RetailSalesSpikeStrategy,
        provider_name="simulated", home=home, ticker="TEST",
        windows=[("2026-08-01", "2026-08-01x"), ("2026-08-02", "2026-08-02x"), ("2026-08-03", "2026-08-03x")],
        get_data_fn=data_fn,
    )
    assert len(result.windows) == 3
    assert all(w.error is None for w in result.windows)
    s = result.summary()
    assert s["valid_windows"] == 3
    assert s["total_trades"] == 3
    # 2 wins, 1 loss -> overall win rate 2/3
    assert s["overall_win_rate"] == pytest.approx(2 / 3)
    assert s["pct_windows_profitable"] == pytest.approx(2 / 3)
    # total pnl should be positive (two wins outweigh one loss in this setup)
    assert s["total_pnl"] > 0


def test_multi_window_reports_errors_without_crashing(home):
    data_fn = make_synthetic_data_fn({"2026-08-01": WINNING_DAY_PRICES})
    result = run_multi_window_backtest(
        strategy_factory=RetailSalesSpikeStrategy,
        provider_name="simulated", home=home, ticker="TEST",
        # second window has no synthetic data configured -> should error, not crash
        windows=[("2026-08-01", "2026-08-01x"), ("2026-08-99", "2026-08-99x")],
        get_data_fn=data_fn,
    )
    assert len(result.windows) == 2
    assert result.windows[0].error is None
    assert result.windows[1].error is not None
    assert len(result.valid_windows) == 1
    s = result.summary()
    assert s["valid_windows"] == 1  # the errored window is excluded from aggregate stats


# --------------------------------------------------------------------------
# Optimizer / grid search
# --------------------------------------------------------------------------

def test_grid_search_finds_better_stop_distance(home):
    """
    A tight stop (small stop_pct) gets clipped by a dip right after entry;
    a wider stop survives the same dip and goes on to hit target. The
    optimizer should score the wider stop higher despite it sizing the
    position smaller (bigger stop distance -> smaller size for the same
    % risk), because it actually reaches the win instead of getting
    stopped out first.
    """
    # Entry lands around 5047.5 (with slippage). A tight 0.1% stop sits at
    # ~5042.5; a wide 2% stop sits at ~4946.6. The dip to 5040 clips the
    # tight stop but not the wide one, before price rallies to target.
    winning_with_dip = [
        5000, 5001, 5000, 5000, 5001,
        5030, 5045, 5020, 5015, 5013,
        5014, 5013, 5013, 5012, 5030,
        5045, 5045,           # -> long entry
        5030,                    # dip: clips the tight stop (~5039.95), not the wide one (~4944.10)
        5090,                       # rally to target for whichever position survived
    ]
    data_fn = make_synthetic_data_fn({
        "2026-08-01": winning_with_dip,
        "2026-08-02": winning_with_dip,
    })
    result = grid_search(
        strategy_cls=RetailSalesSpikeStrategy,
        param_grid={"stop_pct": [0.001, 0.02], "target_pct": [0.008]},
        provider_name="simulated", home=home, ticker="TEST",
        train_windows=[("2026-08-01", "2026-08-01x"), ("2026-08-02", "2026-08-02x")],
        get_data_fn=data_fn,
    )
    assert len(result.candidates) == 2
    tight = next(c for c in result.candidates if c.params["stop_pct"] == 0.001)
    wide = next(c for c in result.candidates if c.params["stop_pct"] == 0.02)
    assert tight.train_summary["total_pnl"] < 0   # stopped out on the dip, both windows
    assert wide.train_summary["total_pnl"] > 0     # survived the dip, hit target, both windows

    ranked = result.ranked(default_objective)
    assert ranked[0].params["stop_pct"] == 0.02


def test_grid_search_flags_train_test_gap(home):
    """
    A strategy that wins on the training window but loses on a held-out
    test window is exactly the overfitting case the train/test split
    exists to catch. Confirm test_summary is populated and shows the
    divergence, independent of the CLI's warning message.
    """
    data_fn = make_synthetic_data_fn({
        "2026-08-01": WINNING_DAY_PRICES,   # train: a winner
        "2026-08-10": LOSING_DAY_PRICES,     # test: a loser
    })
    result = grid_search(
        strategy_cls=RetailSalesSpikeStrategy,
        param_grid={"stop_pct": [0.0045]},
        provider_name="simulated", home=home, ticker="TEST",
        train_windows=[("2026-08-01", "2026-08-01x")],
        test_windows=[("2026-08-10", "2026-08-10x")],
        get_data_fn=data_fn,
    )
    c = result.candidates[0]
    assert c.train_summary["total_pnl"] > 0
    assert c.test_summary is not None
    assert c.test_summary["total_pnl"] < 0


def test_default_objective_scores_no_trades_as_worst(home):
    empty_summary = {"valid_windows": 0}
    profitable_summary = {"valid_windows": 1, "mean_pnl_per_window": 100.0,
                           "pnl_stdev": 0.0, "pct_windows_profitable": 1.0}
    assert default_objective(empty_summary) < default_objective(profitable_summary)
