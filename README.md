# moneymaker

A provider-agnostic paper/live trading engine: pluggable strategies, a
simulated execution provider with full account/credential parity to real
brokers, a CLI, and a local HTTP+JSON API server.

**Nothing in this repo places real-money trades by default.** The only
working provider is `simulated`. Real-broker providers (Trading 212 demo,
Interactive Brokers paper, OANDA practice) are scaffolded but deliberately
left as stubs — see "Execution providers" below.

**If you're an agent picking this project up, read `CONTEXT.md`
first.** It has the design decisions, bugs found and fixed, and what's
actually been verified vs. not — context that isn't visible from the code
alone. If you're being handed this as an ongoing takeover rather than a
one-off task, `HANDOFF.md` has the details of what that means.

## Install

```
git clone <this-repo>
cd moneymaker
pip install -e ".[dev]"
```

or without editable install:
```
pip install -r requirements.txt
```

## Quick start

```
moneymaker strategies
moneymaker providers
moneymaker accounts create --name "main" --balance 10000
moneymaker accounts list

moneymaker backtest --strategy retail_sales_spike --ticker "ES=F" \
    --start 2026-06-01 --end 2026-08-01 --interval 5m

moneymaker live --strategy retail_sales_spike --ticker "ES=F" \
    --end-time 11:00 --poll-seconds 30

moneymaker log --session <session-name-printed-above>
```

## Project layout

```
AGENTS.md           agent/contributor conventions
HANDOFF.md          ongoing ownership instructions for agents
CONTEXT.md          chronological session history (append-only)
PLAN.md             current roadmap and phase status
BACKLOG.md          longer-horizon items and intelligence-layer plans
PROPOSALS.md        engine improvement proposals (discuss before implementing)
QUESTIONS.md        open questions parked for later — no instant answer needed
PRD.md              product requirements (scope, non-requirements)

moneymaker/
  config.py          filesystem-first data dir resolution (~/.moneymaker by default)
  accounts.py        AccountManager (multi-account) + CredentialStore
  data.py            historical/live price data via yfinance, disk-cached
  strategy.py        Strategy interface, built-in strategies, drop-in loading
  risk.py            position sizing from % account risk
  logger.py          Trade record + CSV session logging
  engine.py          Simulator — the loop shared by backtest & live modes
  multiwindow.py     multi-window backtest aggregation
  optimizer.py       grid-search optimizer with train/test split
  server.py          HTTP+JSON API (stdlib only, no extra deps)
  cli.py             argparse CLI entry point
  providers/
    base.py          ExecutionProvider interface
    simulated.py     the only implemented provider
    trading212.py    stub
    ibkr.py          stub
    oanda.py         stub

strategies/                         bundled strategies (loaded at runtime)
  retail_sales_spike_filtered.py    data-release breakout with range-based stops
  momentum_continuation.py          stub — follow spike on large surprises
  opening_range_breakout.py         stub — ORB at 9:30 ET
  vwap_reversion.py                 stub — VWAP mean reversion (needs volume in Bar)
  example_momentum.py               example/template for custom strategies

tests/
  test_engine.py                    pytest suite, no network required
  test_multiwindow_optimizer.py     multi-window + optimizer tests
```

## Data directory

Everything the engine persists lives under `~/.moneymaker` by default.
Override with `--data-dir` or the `MONEYMAKER_HOME` env var.

```
~/.moneymaker/
  strategies/       drop-in .py files — any Strategy subclass auto-loads
  sessions/          trade log CSVs, one per backtest/live run
  data_cache/          cached historical bars (parquet)
  credentials/           credentials.json, permissions locked to owner
  accounts.json             multi-account registry
```

## Accounts and credentials

Multiple named accounts are supported per provider — e.g. two simulated
paper accounts with different starting balances, or (once a real provider
is implemented) multiple broker accounts.

```
moneymaker accounts create --name "aggressive" --balance 5000
moneymaker accounts create --name "conservative" --balance 50000 --provider simulated
moneymaker accounts list
moneymaker accounts delete --account-id <id>
```

Credentials are never stored in plaintext by default:

```
# Recommended: register a reference to an env var. The secret itself
# never touches disk.
export OANDA_API_TOKEN=xxxxx
moneymaker credentials set --provider oanda_practice --key api_token --env-var OANDA_API_TOKEN

# Or store the value directly (file is chmod 600, but it is still
# plaintext on disk — treat it like a password vault).
moneymaker credentials set --provider trading212_demo --key api_key --value xxxxx

moneymaker credentials list   # always masked, never prints secret values
moneymaker credentials clear --provider oanda_practice
```

## Execution providers

Where fills and account data come from is abstracted behind
`ExecutionProvider` (`moneymaker/providers/base.py`). Strategy logic, risk
sizing, and trade logging never know or care which provider is in use.

```
moneymaker providers
```

- **`simulated`** (ready) — no broker involved. Fills against the
  reference price with configurable slippage, tracks real per-account
  paper balances, full parity with the account/credential surface a real
  provider would have.
- **`trading212_demo`, `ibkr_paper`, `oanda_practice`** — stubs. Each
  class's docstring in `moneymaker/providers/*.py` documents exactly what
  API calls are needed to finish it. They correctly raise
  `NotImplementedError` (after a real credential-presence check) rather
  than silently pretending to trade.

**Adding a real provider:** subclass `ExecutionProvider`, implement
`authenticate()`, `list_accounts()`, `get_account()`, `create_account()`,
`execute_order()`, and `get_account_balance()` against the broker's real
API, then register the class in `moneymaker/providers/__init__.py`'s
`PROVIDERS` dict. Everything else — CLI, server, risk sizing, logging —
needs zero changes.

`is_live` must be `True` on any provider that can place real-money
orders. `make_provider()` refuses to auto-construct those — wiring one up
for real is always a deliberate, explicit step, never a side effect of a
name string.

## Adding a strategy

Drop a `.py` file into `<home>/strategies/` (see `strategies/example_momentum.py`
for the pattern):

```python
from moneymaker.strategy import Strategy, StrategyContext, Bar

class MyStrategy(Strategy):
    """One-line description shown in `strategies` list."""
    name = "my_strategy"

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        ...  # mutate ctx to open/close positions
```

It's auto-discovered next time you run `strategies`, `backtest`, or `live`.

## API server

```
moneymaker server --port 8787
```

```
GET  /strategies
GET  /providers
GET  /accounts                POST /accounts  {name, provider?, currency?, starting_balance?, is_live?}
GET  /accounts/<id>
GET  /credentials             POST /credentials  {provider, key, env_var?|value?}
POST /backtest        {strategy, ticker, start, end, interval?, provider?, account_id?, account?, risk_pct?}
POST /live/start       {strategy, ticker, provider?, account_id?, account?, risk_pct?, end_time?, poll_seconds?}
GET  /live/<id>/status         POST /live/<id>/stop
GET  /live/list
GET  /sessions                  GET /sessions/<filename>
```

Stdlib-only (no Flask/FastAPI). Live sessions run as background threads,
so you can start one and poll `/status` from a web UI or TUI while it runs.

## Testing

```
pytest
```

The test suite runs entirely against synthetic price data — no network
calls, no live yfinance requests. `backtest`/`live` against real tickers
does need network access to Yahoo Finance and hasn't been exercised
against live data as part of this repo's own test suite; see
`HANDOFF.md` if you're having an agent verify that end of things
locally.

## Known limitations

- yfinance can lag real-time by 15+ seconds and occasionally gaps data —
  fine for evaluating a strategy, not a substitute for a real broker feed.
- The `simulated` provider is the only one that actually works end to end.
- `RiskManager` position sizing assumes CFD/futures-style fractional
  sizing; adapt `position_size()` if you need whole-share constraints for
  equities.

## Testing across multiple windows

A strategy that looks good on one day tells you very little. `backtest-multi`
runs the same strategy across several independent historical windows and
aggregates the results — total P&L, but also consistency (% of windows
profitable, P&L standard deviation across windows) so one lucky or unlucky
window can't dominate the picture.

```
moneymaker backtest-multi --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --windows "2026-06-01:2026-06-15,2026-06-15:2026-07-01,2026-07-01:2026-07-15,2026-07-15:2026-08-01" \
    --interval 5m
```

Windows that fail (bad ticker, no data available, etc.) are reported
individually and excluded from the aggregate stats — one bad window
doesn't crash the whole run.

## Parameter optimization ("training")

`optimize` grid-searches a strategy's parameters, scored via multi-window
backtests, with an explicit train/test split.

**Important framing:** this is not machine learning, and nothing here
learns from live trading. It's systematic grid search — try every
combination of the values you give it, score each on the training
windows, then separately check the winners against held-out test windows
they never touched during scoring. That split exists specifically to
catch overfitting.

```
moneymaker optimize --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --param-grid '{"stop_pct": [0.003, 0.0045, 0.006], "min_surprise_ratio": [1.5, 2.0, 3.0]}' \
    --train-windows "2026-05-01:2026-06-01,2026-06-01:2026-07-01" \
    --test-windows "2026-07-01:2026-08-01" \
    --top 5
```

Always pass `--test-windows`. Without it you're only seeing train
performance, which is exactly the number most prone to overfitting. The
CLI flags any candidate that's profitable on train but losing on test —
treat those with real suspicion, not just a shrug.

With a realistic number of historical event days available (a monthly
release, say), the amount of independent data to search over is small.
Overfitting risk is real regardless of the train/test split. Treat
optimizer output as a starting point for further live-paper validation,
not a finished, trustworthy strategy.

Both commands are also available via the API server:
`POST /backtest-multi` and `POST /optimize` (see server section above).
