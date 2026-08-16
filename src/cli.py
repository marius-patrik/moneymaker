#!/usr/bin/env python3
"""moneymaker CLI. Run `moneymaker --help` (or `python3 -m moneymaker.cli --help`)
after install for full usage."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

from src.accounts import AccountManager, CredentialStore
from src.config import get_home
from src.data import DataFeed
from src.data_providers import DATA_PROVIDERS, make_data_provider
from src.engine import Simulator
from src.logger import TradeLogger
from src.multiwindow import run_multi_window_backtest
from src.optimizer import default_objective, grid_search
from src.providers import PROVIDERS, make_provider
from src.providers.simulated import SimulatedExecutionProvider
from src.risk import RiskManager
from src.strategy import BUILTIN_STRATEGIES, load_strategies


def _parse_param_overrides(param_list: list[str], strategy_cls) -> dict:
    """Parse ['key=value', ...] into typed dict using the strategy's signature."""
    import inspect as _inspect
    sig = _inspect.signature(strategy_cls.__init__)
    defaults = {
        name: param.default
        for name, param in sig.parameters.items()
        if name != "self" and param.default is not _inspect.Parameter.empty
    }
    result = {}
    for item in (param_list or []):
        if "=" not in item:
            print(f"--param must be key=value, got: {item!r}", file=sys.stderr)
            sys.exit(1)
        key, raw = item.split("=", 1)
        if key not in defaults:
            print(f"Unknown param '{key}' for strategy {strategy_cls.name}. "
                  f"Valid: {list(defaults)}", file=sys.stderr)
            sys.exit(1)
        default_val = defaults[key]
        try:
            if isinstance(default_val, bool):
                result[key] = raw.lower() in ("1", "true", "yes")
            elif isinstance(default_val, float):
                result[key] = float(raw)
            elif isinstance(default_val, int):
                result[key] = int(raw)
            else:
                result[key] = raw
        except ValueError:
            print(f"Could not parse --param {key}={raw!r} as {type(default_val).__name__}", file=sys.stderr)
            sys.exit(1)
    return result


# --------------------------------------------------------------------------
# strategies / providers
# --------------------------------------------------------------------------

def cmd_strategies(args):
    home = get_home(args.data_dir)
    strategies = load_strategies(home)
    print(f"Data dir: {home}")
    print("Available strategies:")
    for name, cls in strategies.items():
        doc = (cls.__doc__ or "").strip().split("\n")[0]
        source = "built-in" if name in BUILTIN_STRATEGIES else "custom (strategies/)"
        print(f"  {name} [{source}] — {doc}")


def cmd_providers(args):
    print("Available execution providers:")
    for name, cls in PROVIDERS.items():
        doc = (cls.__doc__ or "").strip().split("\n")[0]
        status = "ready" if cls is SimulatedExecutionProvider else "STUB — not implemented"
        print(f"  {name} [{status}] — {doc}")


# --------------------------------------------------------------------------
# accounts
# --------------------------------------------------------------------------

def cmd_accounts_list(args):
    home = get_home(args.data_dir)
    mgr = AccountManager(home)
    accts = mgr.list(provider=args.provider)
    if not accts:
        print("No accounts yet. Create one with `accounts create`.")
        return
    for a in accts:
        live_tag = "LIVE" if a.is_live else "paper"
        print(f"  {a.account_id}  [{live_tag}]  {a.name}  ({a.provider})  "
              f"balance={a.balance:.2f} {a.currency}")


def cmd_accounts_create(args):
    home = get_home(args.data_dir)
    mgr = AccountManager(home)
    a = mgr.create(args.name, args.provider, currency=args.currency,
                    starting_balance=args.balance, is_live=args.live)
    print(f"Created account {a.account_id}: {a.name} ({a.provider}), "
          f"balance={a.balance:.2f} {a.currency}, live={a.is_live}")


def cmd_accounts_delete(args):
    home = get_home(args.data_dir)
    mgr = AccountManager(home)
    mgr.delete(args.account_id)
    print(f"Deleted account {args.account_id} (if it existed).")


# --------------------------------------------------------------------------
# credentials
# --------------------------------------------------------------------------

def cmd_credentials_set(args):
    home = get_home(args.data_dir)
    store = CredentialStore(home)
    if args.env_var:
        store.set_ref(args.provider, args.key, args.env_var)
        print(f"Registered {args.provider}.{args.key} as a reference to env var {args.env_var}. "
              f"Nothing secret was written to disk.")
    elif args.value:
        store.set_value(args.provider, args.key, args.value)
        print(f"Stored {args.provider}.{args.key} directly on disk "
              f"({store.path}, permissions locked to owner-only).")
    else:
        print("Provide either --env-var NAME (recommended) or --value SECRET.", file=sys.stderr)
        sys.exit(1)


def cmd_credentials_list(args):
    home = get_home(args.data_dir)
    store = CredentialStore(home)
    masked = store.list_masked()
    if not masked:
        print("No credentials registered.")
        return
    for provider, keys in masked.items():
        print(f"{provider}:")
        for k, desc in keys.items():
            print(f"  {k}: {desc}")


def cmd_credentials_clear(args):
    home = get_home(args.data_dir)
    store = CredentialStore(home)
    store.clear(args.provider, args.key)
    print(f"Cleared credentials for {args.provider}" + (f".{args.key}" if args.key else " (all keys)."))


# --------------------------------------------------------------------------
# backtest / live / log
# --------------------------------------------------------------------------

def _resolve_account(home: str, provider, args) -> str:
    if args.account_id:
        return args.account_id
    accts = provider.list_accounts()
    if not accts:
        acct = provider.create_account("default", starting_balance=args.account)
        return acct.account_id
    return accts[0].account_id


def _make_data_provider(args, home: str):
    dp_name = getattr(args, "data_provider", None) or "yfinance"
    dp_path = getattr(args, "data_provider_path", None)
    kwargs = {}
    if dp_path:
        kwargs["path"] = dp_path
    return make_data_provider(dp_name, home, **kwargs)


def cmd_backtest(args):
    home = get_home(args.data_dir)
    strategies = load_strategies(home)
    strategy_cls = strategies.get(args.strategy)
    if not strategy_cls:
        print(f"Unknown strategy '{args.strategy}'. Run `strategies` to list options.", file=sys.stderr)
        sys.exit(1)
    overrides = _parse_param_overrides(getattr(args, "param", None) or [], strategy_cls)
    data_prov = _make_data_provider(args, home)
    df = data_prov.get_historical(args.ticker, args.start, args.end, interval=args.interval)
    strategy = strategy_cls.from_params({**strategy_cls.params(), **overrides}) if overrides else strategy_cls()
    provider = make_provider(args.provider, home)
    account_id = _resolve_account(home, provider, args)
    risk = RiskManager(risk_pct=args.risk_pct)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = TradeLogger(home, f"backtest_{args.strategy}_{ts}")
    sim = Simulator(strategy, provider, account_id, risk, logger, ticker=args.ticker)
    sim.run_backtest(df)


def cmd_live(args):
    home = get_home(args.data_dir)
    strategies = load_strategies(home)
    strategy_cls = strategies.get(args.strategy)
    if not strategy_cls:
        print(f"Unknown strategy '{args.strategy}'. Run `strategies` to list options.", file=sys.stderr)
        sys.exit(1)
    overrides = _parse_param_overrides(getattr(args, "param", None) or [], strategy_cls)
    strategy = strategy_cls.from_params({**strategy_cls.params(), **overrides}) if overrides else strategy_cls()
    data_prov = _make_data_provider(args, home)
    if not data_prov.is_live:
        print(f"Data provider '{data_prov.name}' does not support live price feeds. "
              f"Use --data-provider yfinance or alpaca for live mode.", file=sys.stderr)
        sys.exit(1)
    provider = make_provider(args.provider, home)
    account_id = _resolve_account(home, provider, args)
    risk = RiskManager(risk_pct=args.risk_pct)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = TradeLogger(home, f"live_{args.strategy}_{ts}")
    sim = Simulator(strategy, provider, account_id, risk, logger, ticker=args.ticker)
    end_time = dt.datetime.strptime(args.end_time, "%H:%M").time()
    sim.run_live(args.ticker, args.poll_seconds, end_time,
                 get_price_fn=data_prov.get_last_price)


def cmd_log(args):
    home = get_home(args.data_dir)
    path = args.session
    if not os.path.exists(path):
        candidate = os.path.join(home, "sessions", path if path.endswith(".csv") else f"{path}.csv")
        if os.path.exists(candidate):
            path = candidate
        else:
            print(f"No such session: {args.session}", file=sys.stderr)
            sys.exit(1)
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("Session file is empty — no trades recorded.")
        return
    for r in rows:
        print(r)
    pnls = [float(r["pnl"]) for r in rows if r["pnl"]]
    if pnls:
        wins = [p for p in pnls if p > 0]
        print(f"\nTrades: {len(pnls)}  Win rate: {len(wins)/len(pnls):.1%}  Total P&L: {sum(pnls):+.2f}")


# --------------------------------------------------------------------------
# multi-window backtest / optimize ("training")
# --------------------------------------------------------------------------

def _parse_windows(spec: str) -> list[tuple[str, str]]:
    """'2026-01-01:2026-02-01,2026-03-01:2026-04-01' -> [(start,end), ...]"""
    windows = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"Bad window '{part}' — expected START:END, e.g. 2026-06-01:2026-07-01")
        start, end = part.split(":", 1)
        windows.append((start.strip(), end.strip()))
    if not windows:
        raise ValueError("No windows parsed from --windows")
    return windows


def _generate_walk_forward_windows(start: str, end: str, n: int) -> list[tuple[str, str]]:
    """Split [start, end) into N equal-sized date windows."""
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    total_days = (e - s).days
    if total_days <= 0:
        raise ValueError(f"--wf-start must be before --wf-end, got {start} to {end}")
    if n < 1:
        raise ValueError(f"--walk-forward must be >= 1, got {n}")
    window_days = total_days / n
    windows = []
    for i in range(n):
        ws = s + dt.timedelta(days=round(i * window_days))
        we = s + dt.timedelta(days=round((i + 1) * window_days))
        if i == n - 1:
            we = e  # avoid rounding drift on last window
        windows.append((ws.isoformat(), we.isoformat()))
    return windows


def cmd_backtest_multi(args):
    home = get_home(args.data_dir)
    strategies = load_strategies(home)
    strategy_cls = strategies.get(args.strategy)
    if not strategy_cls:
        print(f"Unknown strategy '{args.strategy}'. Run `strategies` to list options.", file=sys.stderr)
        sys.exit(1)
    overrides = _parse_param_overrides(getattr(args, "param", None) or [], strategy_cls)
    try:
        if getattr(args, "walk_forward", None):
            if not args.wf_start or not args.wf_end:
                print("--walk-forward requires --wf-start and --wf-end", file=sys.stderr)
                sys.exit(1)
            windows = _generate_walk_forward_windows(args.wf_start, args.wf_end, args.walk_forward)
            print(f"Walk-forward: {args.walk_forward} windows from {args.wf_start} to {args.wf_end}")
            for s, e in windows:
                print(f"  {s} → {e}")
        elif args.windows:
            windows = _parse_windows(args.windows)
        else:
            print("Provide either --windows or --walk-forward with --wf-start/--wf-end", file=sys.stderr)
            sys.exit(1)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    def factory():
        base = strategy_cls.params()
        return strategy_cls.from_params({**base, **overrides}) if overrides else strategy_cls()

    data_prov = _make_data_provider(args, home)
    result = run_multi_window_backtest(
        strategy_factory=factory, provider_name=args.provider, home=home,
        ticker=args.ticker, windows=windows, interval=args.interval,
        account_balance=args.account, risk_pct=args.risk_pct,
        get_data_fn=data_prov.get_historical,
    )
    print(f"\n{'Window':<28} {'Trades':>7} {'Win%':>7} {'P&L':>12}")
    print("-" * 58)
    for w in result.windows:
        if w.error:
            print(f"{w.start} - {w.end:<10} ERROR: {w.error}")
            continue
        print(f"{w.start} - {w.end:<10} {w.trades:>7} {w.win_rate:>6.1%} {w.total_pnl:>12.2f}")
    s = result.summary()
    print("-" * 58)
    print(f"Valid windows: {s.get('valid_windows', 0)}/{s.get('windows', 0)}   "
          f"Total trades: {s.get('total_trades', 0)}")
    print(f"Total P&L: {s.get('total_pnl', 0):+.2f}   "
          f"Mean P&L/window: {s.get('mean_pnl_per_window', 0):+.2f}   "
          f"Stdev: {s.get('pnl_stdev', 0):.2f}")
    print(f"Windows profitable: {s.get('pct_windows_profitable', 0):.1%}   "
          f"Overall win rate: {s.get('overall_win_rate', 0):.1%}")

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(home, "sessions", f"multiwindow_{args.strategy}_{ts}.json")
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    print(f"\nFull results written to {out_path}")


def cmd_optimize(args):
    home = get_home(args.data_dir)
    strategies = load_strategies(home)
    strategy_cls = strategies.get(args.strategy)
    if not strategy_cls:
        print(f"Unknown strategy '{args.strategy}'. Run `strategies` to list options.", file=sys.stderr)
        sys.exit(1)
    try:
        param_grid = json.loads(args.param_grid)
    except json.JSONDecodeError as e:
        print(f"--param-grid must be valid JSON, e.g. "
              f'\'{{"stop_pct": [0.003, 0.0045], "min_surprise_ratio": [1.5, 2.0]}}\'. Error: {e}',
              file=sys.stderr)
        sys.exit(1)
    try:
        train_windows = _parse_windows(args.train_windows)
        test_windows = _parse_windows(args.test_windows) if args.test_windows else None
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    combos = 1
    for v in param_grid.values():
        combos *= len(v)
    print(f"Grid search: {combos} parameter combination(s), {len(train_windows)} train window(s)"
          + (f", {len(test_windows)} test window(s)" if test_windows else
             " (NO test windows given — results are train-only, higher overfitting risk)"))

    result = grid_search(
        strategy_cls=strategy_cls, param_grid=param_grid, provider_name=args.provider,
        home=home, ticker=args.ticker, train_windows=train_windows, test_windows=test_windows,
        interval=args.interval, account_balance=args.account, risk_pct=args.risk_pct,
    )
    ranked = result.ranked(default_objective)
    print(f"\nTop {min(args.top, len(ranked))} of {len(ranked)} candidates (by objective score, train windows):\n")
    for i, c in enumerate(ranked[: args.top]):
        train_s = c.train_summary
        print(f"#{i+1}  params={c.params}")
        print(f"     train: trades={train_s.get('total_trades', 0)} "
              f"win_rate={train_s.get('overall_win_rate', 0):.1%} "
              f"pnl={train_s.get('total_pnl', 0):+.2f} "
              f"profitable_windows={train_s.get('pct_windows_profitable', 0):.1%}")
        if c.test_summary is not None:
            test_s = c.test_summary
            print(f"     test:  trades={test_s.get('total_trades', 0)} "
                  f"win_rate={test_s.get('overall_win_rate', 0):.1%} "
                  f"pnl={test_s.get('total_pnl', 0):+.2f} "
                  f"profitable_windows={test_s.get('pct_windows_profitable', 0):.1%}")
            if test_s.get("total_pnl", 0) < 0 and train_s.get("total_pnl", 0) > 0:
                print("     ⚠ profitable on train, LOSING on test — likely overfit, treat with suspicion")
        print()

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(home, "sessions", f"optimize_{args.strategy}_{ts}.json")
    with open(out_path, "w") as f:
        json.dump(result.to_dict(default_objective), f, indent=2, default=str)
    print(f"Full results (all candidates) written to {out_path}")


# --------------------------------------------------------------------------
# fork-eval / evolve
# --------------------------------------------------------------------------

def _resolve_forks(strategy_cls, strategies: dict) -> list:
    """Resolve FORKS string names to (label, cls, params) triples."""
    raw_forks = strategy_cls.FORKS
    if not raw_forks:
        print(f"Strategy '{strategy_cls.name}' declares no FORKS. "
              f"Add a FORKS class variable to define variants to compare.", file=sys.stderr)
        sys.exit(1)
    forks = []
    for label, strat_name, params in raw_forks:
        cls = strategies.get(strat_name)
        if not cls:
            print(f"Fork '{label}' references unknown strategy '{strat_name}'. "
                  f"Available: {list(strategies)}", file=sys.stderr)
            sys.exit(1)
        forks.append((label, cls, params))
    return forks


def cmd_fork_eval(args):
    from src.agents.forker import fork_and_eval, rolling_fork_eval
    home = get_home(args.data_dir)
    strategies = load_strategies(home)
    strategy_cls = strategies.get(args.strategy)
    if not strategy_cls:
        print(f"Unknown strategy '{args.strategy}'. Run `strategies` to list options.", file=sys.stderr)
        sys.exit(1)
    forks = _resolve_forks(strategy_cls, strategies)

    if getattr(args, "rolling", False):
        if not args.rolling_start or not args.rolling_end:
            print("--rolling requires --rolling-start and --rolling-end", file=sys.stderr)
            sys.exit(1)
        window_days = getattr(args, "rolling_window", 30)
        step_days = getattr(args, "rolling_step", 7)
        print(f"Rolling fork-eval: {len(forks)} variant(s) of '{args.strategy}' on {args.ticker}")
        print(f"  Range: {args.rolling_start} → {args.rolling_end}  "
              f"window={window_days}d  step={step_days}d")
        result = rolling_fork_eval(
            strategy_name=args.strategy, forks=forks,
            provider_name=args.provider, home=home, ticker=args.ticker,
            rolling_start=args.rolling_start, rolling_end=args.rolling_end,
            window_days=window_days, step_days=step_days,
            interval=args.interval, account_balance=args.account, risk_pct=args.risk_pct,
        )
        print(f"\nScore trajectory ({len(result.entries)} windows):")
        fork_names = result.fork_names()
        header = f"{'Window end':<14}" + "".join(f"{n[:18]:>20}" for n in fork_names)
        print(header)
        print("-" * len(header))
        for entry in result.entries:
            scores = {f["name"]: f["score"] for f in entry.forks}
            row = f"{entry.window_end:<14}" + "".join(
                f"{scores.get(n, float('nan')):>+20.2f}" for n in fork_names
            )
            print(row)
        print()
        for name in fork_names:
            print(f"  {name}: {result.trend(name)}")
        return

    if not args.windows:
        print("Provide --windows for one-shot mode or --rolling for rolling mode.", file=sys.stderr)
        sys.exit(1)
    try:
        windows = _parse_windows(args.windows)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"Fork-eval: {len(forks)} variant(s) of '{args.strategy}' "
          f"across {len(windows)} window(s)...")
    result = fork_and_eval(
        forks, args.provider, home, args.ticker, windows,
        interval=args.interval, account_balance=args.account,
        risk_pct=args.risk_pct,
    )
    print(f"\n{'Rank':<5} {'Name':<40} {'Score':>8} {'Trades':>8} {'Win%':>7} {'P&L':>12}")
    print("-" * 82)
    for i, fr in enumerate(result.ranked(), 1):
        s = fr.summary
        print(f"{i:<5} {fr.name:<40} {fr.score:>+8.2f} "
              f"{s.get('total_trades', 0):>8} "
              f"{s.get('overall_win_rate', 0):>6.1%} "
              f"{s.get('total_pnl', 0):>12.2f}")
    if result.winner:
        print(f"\nWinner: {result.winner.name}  params={result.winner.params}")

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(home, "sessions", f"fork_eval_{args.strategy}_{ts}.json")
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    print(f"Full results written to {out_path}")


def cmd_rankings(args):
    from src.agents.forker import load_all_rolling
    home = get_home(args.data_dir)
    all_results = load_all_rolling(home)
    if not all_results:
        print("No rolling evaluation files found. Run `fork-eval --rolling ...` first.")
        return
    for r in all_results:
        if not r.entries:
            continue
        print(f"\n{'='*60}")
        print(f"  {r.strategy}  [{r.ticker}]  —  {len(r.entries)} window(s)")
        print(f"{'='*60}")
        fork_names = r.fork_names()
        header = f"{'Window end':<14}" + "".join(f"{n[:16]:>18}" for n in fork_names)
        print(header)
        print("-" * len(header))
        for entry in r.entries:
            scores = {f["name"]: f["score"] for f in entry.forks}
            row = f"{entry.window_end:<14}" + "".join(
                f"{scores.get(n, float('nan')):>+18.2f}" for n in fork_names
            )
            print(row)
        print()
        for name in fork_names:
            trend = r.trend(name)
            traj = r.score_trajectory(name)
            latest = f"{traj[-1][1]:+.2f}" if traj else "n/a"
            print(f"  {name:<38}  latest={latest:>8}  trend={trend}")


def cmd_evolve(args):
    from src.agents.evolution import evolve
    home = get_home(args.data_dir)
    strategies = load_strategies(home)
    strategy_cls = strategies.get(args.strategy)
    if not strategy_cls:
        print(f"Unknown strategy '{args.strategy}'. Run `strategies` to list options.", file=sys.stderr)
        sys.exit(1)
    try:
        windows = _parse_windows(args.windows)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    start_params = dict(strategy_cls.params())
    if args.param:
        overrides = _parse_param_overrides(args.param, strategy_cls)
        start_params.update(overrides)

    print(f"Evolving '{args.strategy}' for up to {args.generations} generation(s) "
          f"across {len(windows)} window(s)...")
    result = evolve(
        strategy_cls=strategy_cls, provider_name=args.provider, home=home,
        ticker=args.ticker, windows=windows, start_params=start_params,
        max_generations=args.generations, perturbation_pct=args.perturbation,
        interval=args.interval, account_balance=args.account, risk_pct=args.risk_pct,
        verbose=True,
    )
    print(f"\nEvolution complete. Ran {result.generations_run} generation(s).")
    print(f"Best score: {result.best_score:+.2f}")
    print(f"Best params: {result.best_params}")

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(home, "sessions", f"evolve_{args.strategy}_{ts}.json")
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    print(f"Full results written to {out_path}")


# --------------------------------------------------------------------------
# strategy install / upgrade
# --------------------------------------------------------------------------

def cmd_install_strategies(args):
    from src.installer import install_strategies, print_install_result
    home = get_home(args.data_dir)
    result = install_strategies(home, force=getattr(args, "force", False))
    print_install_result(result)


def cmd_upgrade_strategies(args):
    from src.installer import install_strategies, print_install_result
    home = get_home(args.data_dir)
    result = install_strategies(home, force=args.force)
    print_install_result(result)


def cmd_upgrade(args):
    from src.installer import run_upgrade
    home = get_home(args.data_dir)
    run_upgrade(home)


# --------------------------------------------------------------------------
# server
# --------------------------------------------------------------------------

def cmd_server(args):
    from src.server import run_server
    run_server(get_home(args.data_dir), args.host, args.port)


# --------------------------------------------------------------------------
# CLI wiring
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="moneymaker", description="Provider-agnostic paper/live trading engine.")
    parser.add_argument("--data-dir", default=None,
                         help="Override data directory (default: $MONEYMAKER_HOME or .data/ in the repo root)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_strat = sub.add_parser("strategies", help="List available strategies.")
    p_strat.set_defaults(func=cmd_strategies)

    p_prov = sub.add_parser("providers", help="List available execution providers.")
    p_prov.set_defaults(func=cmd_providers)

    # accounts
    p_acct = sub.add_parser("accounts", help="Manage accounts.")
    acct_sub = p_acct.add_subparsers(dest="accounts_command", required=True)

    p_acct_list = acct_sub.add_parser("list", help="List accounts.")
    p_acct_list.add_argument("--provider", default=None)
    p_acct_list.set_defaults(func=cmd_accounts_list)

    p_acct_create = acct_sub.add_parser("create", help="Create an account.")
    p_acct_create.add_argument("--name", required=True)
    p_acct_create.add_argument("--provider", default="simulated")
    p_acct_create.add_argument("--currency", default="USD")
    p_acct_create.add_argument("--balance", type=float, default=10000.0)
    p_acct_create.add_argument("--live", action="store_true",
                                help="Mark as a live/real-money account (bookkeeping only — "
                                     "does not itself enable real trading).")
    p_acct_create.set_defaults(func=cmd_accounts_create)

    p_acct_delete = acct_sub.add_parser("delete", help="Delete an account.")
    p_acct_delete.add_argument("--account-id", required=True)
    p_acct_delete.set_defaults(func=cmd_accounts_delete)

    # credentials
    p_cred = sub.add_parser("credentials", help="Manage provider credentials.")
    cred_sub = p_cred.add_subparsers(dest="credentials_command", required=True)

    p_cred_set = cred_sub.add_parser("set", help="Register a credential.")
    p_cred_set.add_argument("--provider", required=True)
    p_cred_set.add_argument("--key", required=True, help="e.g. api_key, api_token")
    p_cred_set.add_argument("--env-var", default=None, help="Name of env var holding the secret (recommended).")
    p_cred_set.add_argument("--value", default=None, help="Store the secret directly on disk instead.")
    p_cred_set.set_defaults(func=cmd_credentials_set)

    p_cred_list = cred_sub.add_parser("list", help="List registered credentials (masked).")
    p_cred_list.set_defaults(func=cmd_credentials_list)

    p_cred_clear = cred_sub.add_parser("clear", help="Clear credentials for a provider.")
    p_cred_clear.add_argument("--provider", required=True)
    p_cred_clear.add_argument("--key", default=None, help="Omit to clear all keys for the provider.")
    p_cred_clear.set_defaults(func=cmd_credentials_clear)

    # backtest / live / log
    p_back = sub.add_parser("backtest", help="Run a strategy against historical data.")
    p_back.add_argument("--strategy", required=True)
    p_back.add_argument("--ticker", required=True, help='e.g. "ES=F", "AAPL", "EURUSD=X"')
    p_back.add_argument("--start", required=True, help="YYYY-MM-DD")
    p_back.add_argument("--end", required=True, help="YYYY-MM-DD")
    p_back.add_argument("--interval", default="5m", help="1m/5m/15m/1h/1d (intraday limited to ~60 days history)")
    p_back.add_argument("--account", type=float, default=10000.0, help="Starting balance if auto-creating an account")
    p_back.add_argument("--account-id", default=None, help="Use a specific existing account instead of auto-selecting")
    p_back.add_argument("--risk-pct", type=float, default=0.01)
    p_back.add_argument("--provider", default="simulated", help=f"one of {list(PROVIDERS)}")
    p_back.add_argument("--data-provider", default="yfinance", metavar="NAME",
                        help=f"Market data source: {list(DATA_PROVIDERS)}")
    p_back.add_argument("--data-provider-path", default=None, metavar="PATH",
                        help="For --data-provider csv: path to a CSV or Parquet file.")
    p_back.add_argument("--param", action="append", metavar="KEY=VALUE",
                        help="Override a strategy parameter, e.g. --param min_spike_pct=0.001. Repeatable.")
    p_back.set_defaults(func=cmd_backtest)

    p_live = sub.add_parser("live", help="Run a strategy live against real-time prices (paper only, unless a live provider is wired up).")
    p_live.add_argument("--strategy", required=True)
    p_live.add_argument("--ticker", required=True)
    p_live.add_argument("--account", type=float, default=10000.0)
    p_live.add_argument("--account-id", default=None)
    p_live.add_argument("--risk-pct", type=float, default=0.01)
    p_live.add_argument("--poll-seconds", type=int, default=30)
    p_live.add_argument("--end-time", default="11:00", help="HH:MM local time to stop the session")
    p_live.add_argument("--provider", default="simulated", help=f"one of {list(PROVIDERS)}")
    p_live.add_argument("--data-provider", default="yfinance", metavar="NAME",
                        help=f"Live price source: {[k for k, v in DATA_PROVIDERS.items() if v.is_live]}")
    p_live.add_argument("--data-provider-path", default=None, metavar="PATH",
                        help="For --data-provider csv (not applicable to live mode).")
    p_live.add_argument("--param", action="append", metavar="KEY=VALUE",
                        help="Override a strategy parameter, e.g. --param stop_pct=0.003. Repeatable.")
    p_live.set_defaults(func=cmd_live)

    p_log = sub.add_parser("log", help="Print trade log/stats for a past session.")
    p_log.add_argument("--session", required=True, help="Session name or path to CSV")
    p_log.set_defaults(func=cmd_log)

    # multi-window backtest
    p_mw = sub.add_parser("backtest-multi", help="Run a strategy across several historical windows and aggregate results.")
    p_mw.add_argument("--strategy", required=True)
    p_mw.add_argument("--ticker", required=True)
    # Manual window list (mutually exclusive with --walk-forward)
    p_mw.add_argument("--windows", default=None,
                       help="Comma-separated START:END pairs, e.g. '2026-06-01:2026-07-01,2026-07-01:2026-08-01'")
    # Auto walk-forward (alternative to --windows)
    p_mw.add_argument("--walk-forward", type=int, default=None, metavar="N",
                      help="Auto-split --wf-start:--wf-end into N equal windows (alternative to --windows).")
    p_mw.add_argument("--wf-start", default=None, metavar="DATE", help="Start date for walk-forward, YYYY-MM-DD")
    p_mw.add_argument("--wf-end", default=None, metavar="DATE", help="End date for walk-forward, YYYY-MM-DD")
    p_mw.add_argument("--interval", default="5m")
    p_mw.add_argument("--account", type=float, default=10000.0)
    p_mw.add_argument("--risk-pct", type=float, default=0.01)
    p_mw.add_argument("--provider", default="simulated", help=f"one of {list(PROVIDERS)}")
    p_mw.add_argument("--data-provider", default="yfinance", metavar="NAME",
                      help=f"Market data source: {list(DATA_PROVIDERS)}")
    p_mw.add_argument("--data-provider-path", default=None, metavar="PATH",
                      help="For --data-provider csv: path to data file.")
    p_mw.add_argument("--param", action="append", metavar="KEY=VALUE",
                      help="Override a strategy parameter. Repeatable.")
    p_mw.set_defaults(func=cmd_backtest_multi)

    # optimize ("training")
    p_opt = sub.add_parser("optimize", help="Grid search a strategy's parameters with a train/test window split.")
    p_opt.add_argument("--strategy", required=True)
    p_opt.add_argument("--ticker", required=True)
    p_opt.add_argument("--param-grid", required=True,
                        help='JSON dict of param -> list of candidate values, e.g. '
                             '\'{"stop_pct": [0.003, 0.0045], "min_surprise_ratio": [1.5, 2.0]}\'')
    p_opt.add_argument("--train-windows", required=True, help="Same format as --windows on backtest-multi")
    p_opt.add_argument("--test-windows", default=None,
                        help="Held-out windows never used for scoring, to check for overfitting. Strongly recommended.")
    p_opt.add_argument("--interval", default="5m")
    p_opt.add_argument("--account", type=float, default=10000.0)
    p_opt.add_argument("--risk-pct", type=float, default=0.01)
    p_opt.add_argument("--provider", default="simulated", help=f"one of {list(PROVIDERS)}")
    p_opt.add_argument("--top", type=int, default=5, help="How many top candidates to print")
    p_opt.set_defaults(func=cmd_optimize)

    # fork-eval / evolve
    p_fe = sub.add_parser("fork-eval",
                          help="Compare strategy FORKS over identical windows and rank by objective score.")
    p_fe.add_argument("--strategy", required=True)
    p_fe.add_argument("--ticker", required=True)
    p_fe.add_argument("--windows", default=None,
                      help="Comma-separated START:END pairs (one-shot mode). Omit for --rolling mode.")
    p_fe.add_argument("--rolling", action="store_true",
                      help="Slide a window forward and accumulate score trajectories (P011).")
    p_fe.add_argument("--rolling-start", default=None, metavar="DATE",
                      help="Start of the rolling range (YYYY-MM-DD). Required with --rolling.")
    p_fe.add_argument("--rolling-end", default=None, metavar="DATE",
                      help="End of the rolling range (YYYY-MM-DD). Required with --rolling.")
    p_fe.add_argument("--rolling-window", type=int, default=30, metavar="DAYS",
                      help="Size of each evaluation window in days (default 30).")
    p_fe.add_argument("--rolling-step", type=int, default=7, metavar="DAYS",
                      help="Step size between windows in days (default 7).")
    p_fe.add_argument("--interval", default="5m")
    p_fe.add_argument("--account", type=float, default=10000.0)
    p_fe.add_argument("--risk-pct", type=float, default=0.01)
    p_fe.add_argument("--provider", default="simulated", help=f"one of {list(PROVIDERS)}")
    p_fe.set_defaults(func=cmd_fork_eval)

    p_rank = sub.add_parser("rankings",
                             help="Show score trajectories for all rolling fork-eval results (P011).")
    p_rank.set_defaults(func=cmd_rankings)

    p_ev = sub.add_parser("evolve",
                          help="Hill-climb a strategy's numeric parameters across windows to find a better configuration.")
    p_ev.add_argument("--strategy", required=True)
    p_ev.add_argument("--ticker", required=True)
    p_ev.add_argument("--windows", required=True,
                      help="Comma-separated START:END pairs (same format as backtest-multi)")
    p_ev.add_argument("--interval", default="5m")
    p_ev.add_argument("--account", type=float, default=10000.0)
    p_ev.add_argument("--risk-pct", type=float, default=0.01)
    p_ev.add_argument("--provider", default="simulated", help=f"one of {list(PROVIDERS)}")
    p_ev.add_argument("--generations", type=int, default=20, help="Max hill-climbing generations (default 20)")
    p_ev.add_argument("--perturbation", type=float, default=0.20,
                      help="Fractional step size for parameter perturbation (default 0.20 = ±20%%)")
    p_ev.add_argument("--param", action="append", metavar="KEY=VALUE",
                      help="Override starting parameter values before evolving. Repeatable.")
    p_ev.set_defaults(func=cmd_evolve)

    p_inst = sub.add_parser("install-strategies",
                             help="Copy bundled strategies to the home strategies/ dir (first-time setup).")
    p_inst.set_defaults(func=cmd_install_strategies)

    p_up_strat = sub.add_parser("upgrade-strategies",
                                 help="Sync updated bundled strategies to home dir. "
                                      "Skips locally modified files unless --force.")
    p_up_strat.add_argument("--force", action="store_true",
                             help="Overwrite locally modified strategies without prompting.")
    p_up_strat.set_defaults(func=cmd_upgrade_strategies)

    p_upgrade = sub.add_parser("upgrade",
                                help="Pull the latest version from the repo, reinstall, "
                                     "and sync bundled strategies.")
    p_upgrade.set_defaults(func=cmd_upgrade)

    p_server = sub.add_parser("server", help="Run the HTTP+JSON API server.")
    p_server.add_argument("--host", default="127.0.0.1")
    p_server.add_argument("--port", type=int, default=8787)
    p_server.set_defaults(func=cmd_server)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
