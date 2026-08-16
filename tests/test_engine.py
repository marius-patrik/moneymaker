"""
Tests that don't require network access (no live yfinance calls) — they
exercise the engine's own logic with synthetic price data. Run with:
    pytest
from the repo root, after `pip install -e ".[dev]"` or
`pip install -r requirements.txt`.
"""

import datetime as dt

import pytest

from moneymaker.accounts import AccountManager, CredentialStore
from moneymaker.config import get_home
from moneymaker.engine import Simulator
from moneymaker.logger import TradeLogger
from moneymaker.providers import PROVIDERS, make_provider
from moneymaker.providers.ibkr import IBKRPaperProvider
from moneymaker.providers.oanda import OANDAPracticeProvider
from moneymaker.providers.simulated import SimulatedExecutionProvider
from moneymaker.providers.trading212 import Trading212DemoProvider
from moneymaker.risk import RiskManager
from moneymaker.strategy import Bar, RetailSalesSpikeStrategy, load_strategies


@pytest.fixture
def home(tmp_path):
    return get_home(str(tmp_path / ".moneymaker"))


# --------------------------------------------------------------------------
# Risk manager
# --------------------------------------------------------------------------

def test_position_sizing():
    risk = RiskManager(risk_pct=0.01)
    size = risk.position_size(account_balance=10000, entry_price=100, stop_price=99)
    # risking 1% of 10000 = 100, stop distance = 1 -> size = 100
    assert size == pytest.approx(100.0)


def test_position_sizing_zero_stop_distance():
    risk = RiskManager(risk_pct=0.01)
    assert risk.position_size(10000, 100, 100) == 0.0


# --------------------------------------------------------------------------
# Credential store
# --------------------------------------------------------------------------

def test_credential_store_env_ref(home, monkeypatch):
    monkeypatch.setenv("TEST_SECRET", "shh")
    store = CredentialStore(home)
    store.set_ref("some_provider", "api_key", "TEST_SECRET")
    assert store.get("some_provider", "api_key") == "shh"
    masked = store.list_masked()
    assert masked["some_provider"]["api_key"] == "env:TEST_SECRET"  # never exposes the value


def test_credential_store_direct_value(home):
    store = CredentialStore(home)
    store.set_value("some_provider", "api_key", "raw-secret")
    assert store.get("some_provider", "api_key") == "raw-secret"
    masked = store.list_masked()
    assert "raw-secret" not in str(masked)  # never exposes the value, even for direct storage


def test_credential_store_clear(home):
    store = CredentialStore(home)
    store.set_value("p", "k", "v")
    store.clear("p", "k")
    assert store.get("p", "k") is None


# --------------------------------------------------------------------------
# Account manager / multi-account support
# --------------------------------------------------------------------------

def test_account_manager_multi_account(home):
    mgr = AccountManager(home)
    a1 = mgr.create("paper-1", "simulated", starting_balance=10000)
    a2 = mgr.create("paper-2", "simulated", starting_balance=25000)
    accts = mgr.list(provider="simulated")
    assert {a.account_id for a in accts} == {a1.account_id, a2.account_id}
    assert mgr.get(a1.account_id).balance == 10000
    assert mgr.get(a2.account_id).balance == 25000

    mgr.update_balance(a1.account_id, 10500)
    assert mgr.get(a1.account_id).balance == 10500

    mgr.delete(a2.account_id)
    assert mgr.get(a2.account_id) is None


# --------------------------------------------------------------------------
# Provider parity: simulated provider has the full account-aware surface
# --------------------------------------------------------------------------

def test_simulated_provider_full_parity(home):
    provider = make_provider("simulated", home)
    provider.authenticate()  # no-op, should not raise

    acct = provider.create_account("test-account", starting_balance=5000)
    assert acct.balance == 5000
    assert provider.get_account_balance(acct.account_id) == 5000

    fetched = provider.get_account(acct.account_id)
    assert fetched.account_id == acct.account_id

    accts = provider.list_accounts()
    assert acct.account_id in [a.account_id for a in accts]

    result = provider.execute_order(
        account_id=acct.account_id, ticker="TEST", direction="long", size=1,
        reference_price=100.0, timestamp=dt.datetime.now(), closing=False,
    )
    assert result.fill_price > 100.0  # slippage works against you on entry

    provider.on_trade_closed(acct.account_id, pnl=42.0)
    assert provider.get_account_balance(acct.account_id) == pytest.approx(5042.0)


def test_make_provider_refuses_unknown_name(home):
    with pytest.raises(ValueError):
        make_provider("not_a_real_provider", home)


def test_stub_providers_raise_not_implemented(home):
    for cls in (Trading212DemoProvider, IBKRPaperProvider, OANDAPracticeProvider):
        provider = cls(home)
        with pytest.raises(NotImplementedError):
            provider.execute_order(
                account_id="x", ticker="X", direction="long", size=1,
                reference_price=100.0, timestamp=dt.datetime.now(), closing=False,
            )


def test_stub_provider_credential_check_before_stub_error(home):
    # Without credentials registered, authenticate() should fail on the
    # *missing credentials* message, not silently fall through.
    provider = Trading212DemoProvider(home)
    with pytest.raises(RuntimeError, match="Missing credentials"):
        provider.authenticate()


def test_no_provider_is_auto_constructible_if_marked_live(home):
    # None of the shipped providers are live yet, but the safety rail
    # itself must hold: is_live=True providers are never auto-constructed.
    for name, cls in PROVIDERS.items():
        assert cls.is_live is False, f"{name} is marked live but still in the default registry"


# --------------------------------------------------------------------------
# Full simulator lifecycle with synthetic bars (no network needed)
# --------------------------------------------------------------------------

def test_simulator_full_trade_lifecycle(home):
    strategy = RetailSalesSpikeStrategy()
    provider = make_provider("simulated", home)
    account = provider.create_account("test", starting_balance=10000)
    risk = RiskManager(risk_pct=0.01)
    logger = TradeLogger(home, "test_session")
    sim = Simulator(strategy, provider, account.account_id, risk, logger, ticker="TEST")

    base_time = dt.datetime(2026, 8, 14, 8, 20)
    prices = [
        5000, 5001, 5000, 5000, 5001,   # baseline window
        5030, 5045, 5020, 5015, 5013,    # spike window
        5014, 5013, 5013, 5012, 5030,     # still building
        5045, 5045,                        # two stable post-spike bars -> long entry
        5090,                                # should hit target
    ]
    for i, p in enumerate(prices):
        sim.feed_bar(Bar(time=base_time + dt.timedelta(minutes=i), price=float(p)))

    logger.write_csv()
    summary = logger.summary()
    assert summary["trades"] == 1
    assert summary["wins"] == 1
    assert summary["total_pnl"] > 0

    # Account balance should reflect the realized P&L via on_trade_closed
    assert provider.get_account_balance(account.account_id) == pytest.approx(
        10000 + summary["total_pnl"]
    )


def test_simulator_stop_loss_path(home):
    strategy = RetailSalesSpikeStrategy()
    provider = make_provider("simulated", home)
    account = provider.create_account("test", starting_balance=10000)
    risk = RiskManager(risk_pct=0.01)
    logger = TradeLogger(home, "test_session_stop")
    sim = Simulator(strategy, provider, account.account_id, risk, logger, ticker="TEST")

    base_time = dt.datetime(2026, 8, 14, 8, 20)
    # Same setup as the winning-trade test (long entry around 5045),
    # but this time price drops straight through the stop instead of
    # continuing toward the target.
    prices = [
        5000, 5001, 5000, 5000, 5001,   # baseline window
        5030, 5045, 5020, 5015, 5013,    # spike window
        5014, 5013, 5013, 5012, 5030,     # still building
        5045, 5045,                        # two stable post-spike bars -> long entry
        5000,                                # drops through stop -> exit
    ]
    for i, p in enumerate(prices):
        sim.feed_bar(Bar(time=base_time + dt.timedelta(minutes=i), price=float(p)))

    logger.write_csv()
    summary = logger.summary()
    assert summary["trades"] == 1
    assert summary["losses"] == 1
    assert summary["total_pnl"] < 0
    assert logger.trades[0].exit_reason == "stop"


def test_simulator_trades_independently_across_multiple_days(home):
    """
    Regression test: a single continuous backtest spanning multiple
    calendar days must let each day trade independently. Before
    reset_session_if_new_day() existed, day one's leftover
    trades_taken/hard_exit_time silently blocked every later day —
    a multi-day backtest would only ever produce (at most) one trade
    total, no matter how many valid setups appeared on later days.
    """
    strategy = RetailSalesSpikeStrategy()
    provider = make_provider("simulated", home)
    account = provider.create_account("test", starting_balance=10000)
    risk = RiskManager(risk_pct=0.01)
    logger = TradeLogger(home, "test_multi_day")
    sim = Simulator(strategy, provider, account.account_id, risk, logger, ticker="TEST")

    def day_bars(date, base_price):
        base_time = dt.datetime.combine(date, dt.time(8, 20))
        prices = [
            base_price, base_price, base_price + 1, base_price, base_price,
            base_price, base_price + 1, base_price, base_price + 0.5, base_price,
            base_price + 20, base_price + 30, base_price + 25, base_price + 28, base_price + 27,
            base_price + 27, base_price + 26,
            base_price + 90,
        ]
        return [Bar(time=base_time + dt.timedelta(minutes=i), price=float(p)) for i, p in enumerate(prices)]

    for bar in day_bars(dt.date(2026, 7, 6), 5000):
        sim.feed_bar(bar)
    for bar in day_bars(dt.date(2026, 7, 7), 5100):
        sim.feed_bar(bar)
    for bar in day_bars(dt.date(2026, 7, 8), 5200):
        sim.feed_bar(bar)

    logger.write_csv()
    summary = logger.summary()
    # Each of the 3 days has an equally valid, independent setup — all
    # three should trade, not just the first one the engine ever sees.
    assert summary["trades"] == 3


# --------------------------------------------------------------------------
# Strategy loading from filesystem
# --------------------------------------------------------------------------

def test_drop_in_strategy_loading(home, tmp_path):
    strat_dir_file = f"{home}/strategies/custom_test_strategy.py"
    with open(strat_dir_file, "w") as f:
        f.write(
            "from moneymaker.strategy import Strategy, StrategyContext, Bar\n"
            "class CustomTest(Strategy):\n"
            "    \"\"\"A custom test strategy.\"\"\"\n"
            "    name = 'custom_test'\n"
            "    def on_bar(self, ctx, bar):\n"
            "        pass\n"
        )
    strategies = load_strategies(home)
    assert "custom_test" in strategies
    assert "retail_sales_spike" in strategies  # built-ins still present


# --------------------------------------------------------------------------
# Filtered strategy: minimum-surprise gate (real spike day vs. flat day)
# --------------------------------------------------------------------------

def _load_filtered_strategy():
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "strategies", "retail_sales_spike_filtered.py")
    spec = importlib.util.spec_from_file_location("retail_sales_spike_filtered", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.FilteredDataReleaseStrategy


def test_filtered_strategy_trades_on_real_spike(home):
    cls = _load_filtered_strategy()
    strategy = cls()
    provider = make_provider("simulated", home)
    account = provider.create_account("test", starting_balance=10000)
    risk = RiskManager(risk_pct=0.01)
    logger = TradeLogger(home, "test_filtered_spike")
    sim = Simulator(strategy, provider, account.account_id, risk, logger, ticker="TEST")

    base_time = dt.datetime(2026, 8, 14, 8, 20)
    prices = [
        5000, 5000, 5001, 5000, 5000,
        5000, 5001, 5000, 5000.5, 5000,   # tight baseline window
        5020, 5030, 5025, 5028, 5027,      # clear spike after release
        5027, 5026,                          # basing -> entry
        5070,                                  # -> target
    ]
    for i, p in enumerate(prices):
        sim.feed_bar(Bar(time=base_time + dt.timedelta(minutes=i), price=float(p)))
    logger.write_csv()
    summary = logger.summary()
    assert summary["trades"] == 1
    assert summary["wins"] == 1


def test_filtered_strategy_stands_down_on_flat_day(home):
    cls = _load_filtered_strategy()
    strategy = cls()
    provider = make_provider("simulated", home)
    account = provider.create_account("test", starting_balance=10000)
    risk = RiskManager(risk_pct=0.01)
    logger = TradeLogger(home, "test_filtered_flat")
    sim = Simulator(strategy, provider, account.account_id, risk, logger, ticker="TEST")

    base_time = dt.datetime(2026, 8, 14, 8, 20)
    # Mirrors the real Aug 14, 2026 case: a genuine data miss, but price
    # essentially unmoved through the release and the rest of the session.
    prices = [
        5000, 5000.5, 5000, 5000.2, 5000,
        5000.3, 5000, 5000.5, 5000.2, 5000,
        5000.4, 5000.1, 5000.3, 5000.5, 5000.2,
        5000.3, 5000.1, 5000.4, 5000.2, 5000, 5000.3, 5000.1,
    ]
    for i, p in enumerate(prices):
        sim.feed_bar(Bar(time=base_time + dt.timedelta(minutes=i), price=float(p)))
    logger.write_csv()
    summary = logger.summary()
    assert summary.get("trades", 0) == 0


def test_filtered_strategy_resets_signal_cache_across_days(home):
    """
    Regression test: the filtered strategy caches its surprise-filter
    verdict (signal_evaluated/signal_valid) per session. Confirm that
    cache is cleared on a new day too, not just trades_taken/hard_exit_time
    — otherwise day 2 could inherit day 1's stand-down verdict even when
    day 2's own price action clearly warrants a trade.
    """
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "strategies", "retail_sales_spike_filtered.py")
    spec = importlib.util.spec_from_file_location("retail_sales_spike_filtered", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    strategy = mod.FilteredDataReleaseStrategy()
    provider = make_provider("simulated", home)
    account = provider.create_account("test", starting_balance=10000)
    risk = RiskManager(risk_pct=0.01)
    logger = TradeLogger(home, "test_filtered_multi_day")
    sim = Simulator(strategy, provider, account.account_id, risk, logger, ticker="TEST")

    def real_spike_day(date, base):
        base_time = dt.datetime.combine(date, dt.time(8, 20))
        prices = [base, base, base + 1, base, base, base, base + 1, base, base + 0.5, base,
                  base + 20, base + 30, base + 25, base + 28, base + 27, base + 27, base + 26, base + 90]
        return [Bar(time=base_time + dt.timedelta(minutes=i), price=float(p)) for i, p in enumerate(prices)]

    def flat_day(date, base):
        base_time = dt.datetime.combine(date, dt.time(8, 20))
        prices = [base + 0.3 * ((-1) ** i) for i in range(22)]
        return [Bar(time=base_time + dt.timedelta(minutes=i), price=float(p)) for i, p in enumerate(prices)]

    for bar in real_spike_day(dt.date(2026, 7, 6), 5000):
        sim.feed_bar(bar)
    for bar in flat_day(dt.date(2026, 7, 7), 5000):
        sim.feed_bar(bar)  # should stand down, no trade
    for bar in real_spike_day(dt.date(2026, 7, 8), 5200):
        sim.feed_bar(bar)  # should trade again — filter re-evaluated fresh, not inheriting day 2's stand-down

    logger.write_csv()
    summary = logger.summary()
    assert summary["trades"] == 2  # day 1 and day 3 trade; day 2 (flat) correctly stands down
