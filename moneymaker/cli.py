#!/usr/bin/env python3
"""moneymaker CLI. Run `moneymaker --help` (or `python3 -m moneymaker.cli --help`)
after install for full usage."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys

from moneymaker.accounts import AccountManager, CredentialStore
from moneymaker.config import get_home
from moneymaker.data import DataFeed
from moneymaker.engine import Simulator
from moneymaker.logger import TradeLogger
from moneymaker.providers import PROVIDERS, make_provider
from moneymaker.providers.simulated import SimulatedExecutionProvider
from moneymaker.risk import RiskManager
from moneymaker.strategy import BUILTIN_STRATEGIES, load_strategies


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


def cmd_backtest(args):
    home = get_home(args.data_dir)
    strategies = load_strategies(home)
    strategy_cls = strategies.get(args.strategy)
    if not strategy_cls:
        print(f"Unknown strategy '{args.strategy}'. Run `strategies` to list options.", file=sys.stderr)
        sys.exit(1)
    feed = DataFeed(home)
    df = feed.get_historical(args.ticker, args.start, args.end, interval=args.interval)
    strategy = strategy_cls()
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
    strategy = strategy_cls()
    provider = make_provider(args.provider, home)
    account_id = _resolve_account(home, provider, args)
    risk = RiskManager(risk_pct=args.risk_pct)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = TradeLogger(home, f"live_{args.strategy}_{ts}")
    sim = Simulator(strategy, provider, account_id, risk, logger, ticker=args.ticker)
    end_time = dt.datetime.strptime(args.end_time, "%H:%M").time()
    sim.run_live(args.ticker, args.poll_seconds, end_time)


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
# server
# --------------------------------------------------------------------------

def cmd_server(args):
    from moneymaker.server import run_server
    run_server(get_home(args.data_dir), args.host, args.port)


# --------------------------------------------------------------------------
# CLI wiring
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="moneymaker", description="Provider-agnostic paper/live trading engine.")
    parser.add_argument("--data-dir", default=None,
                         help="Override data directory (default: $MONEYMAKER_HOME or ~/.moneymaker)")
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
    p_live.set_defaults(func=cmd_live)

    p_log = sub.add_parser("log", help="Print trade log/stats for a past session.")
    p_log.add_argument("--session", required=True, help="Session name or path to CSV")
    p_log.set_defaults(func=cmd_log)

    p_server = sub.add_parser("server", help="Run the HTTP+JSON API server.")
    p_server.add_argument("--host", default="127.0.0.1")
    p_server.add_argument("--port", type=int, default=8787)
    p_server.set_defaults(func=cmd_server)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
