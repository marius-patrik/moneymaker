# moneymaker

A provider-agnostic paper/live trading engine: pluggable strategies, a
simulated execution provider with full account/credential parity to real
brokers, a CLI, a FastAPI server, and a React web UI.

**Nothing in this repo places real-money trades by default.** The only
working provider is `simulated`. Real-broker providers (Trading 212 demo,
Interactive Brokers paper, OANDA practice) are scaffolded but deliberately
left as stubs — see "Execution providers" below.

**License:** personal use only — see `LICENSE`. External contributions are
not accepted; see `CONTRIBUTING.md`.

**If you're an agent picking this project up, read `.agents/CONTEXT.md`
first.** It has the design decisions, bugs found and fixed, and what's
actually been verified vs. not — context that isn't visible from the code
alone. If you're being handed this as an ongoing takeover rather than a
one-off task, `.agents/HANDOFF.md` has the details of what that means.

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

moneymaker backtest --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --start 2026-06-01 --end 2026-08-01 --interval 5m

moneymaker live --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --end-time 11:00 --poll-seconds 30

moneymaker log --session <session-name-printed-above>
```

## Project layout

```
.agents/
  AGENTS.md           agent/contributor conventions
  HANDOFF.md          ongoing ownership instructions for agents
  CONTEXT.md          chronological session history (append-only)
  PLAN.md             current roadmap and phase status
  BACKLOG.md          longer-horizon items and intelligence-layer plans
  PROPOSALS.md        engine improvement proposals (discuss before implementing)
  QUESTIONS.md        open questions parked for later — no instant answer needed
  PRD.md              product requirements (scope, non-requirements)
  BLOCKERS.md         active blockers preventing progress
  DEFERRED.md         explicitly deferred items with triggers for revisiting
  TASKS.md            current session task list

src/                                Python package (import as `src.*`)
  config.py           filesystem-first data dir resolution (.data/ default)
  accounts.py         AccountManager (multi-account) + CredentialStore
  data.py             historical/live price data via yfinance, disk-cached (legacy)
  strategy.py         Strategy + MultiBarStrategy interfaces, built-in strategies
  risk.py             position sizing from % account risk
  logger.py           Trade record + CSV session logging
  engine.py           Simulator + MultiBarSimulator — bar-feed loops
  installer.py        strategy install/upgrade with hash-tracked merge
  multiwindow.py      multi-window backtest aggregation
  optimizer.py        grid-search optimizer with train/test split
  econ_calendar.py    economic release calendar (FRED, BLS stub, Simulated)
  server.py           FastAPI app — /api routes + serves ui/dist in production
  cli.py              argparse CLI entry point (command: `moneymaker`)
  agents/
    forker.py         fork_and_eval() + rolling_fork_eval() — compare N strategy variants
    evolution.py      evolve() — hill-climb numeric params to find better configuration
  data_providers/
    base.py           DataProvider interface
    yfinance_provider.py  yfinance (free, no key, disk-cached)
    alpaca.py         Alpaca Markets (free US equity data, API key required)
    csv_provider.py   load history from local CSV or Parquet file
    simulated.py      Brownian motion + fixture replay (no network)
  providers/
    base.py           ExecutionProvider interface
    simulated.py      the only implemented execution provider
    trading212.py     stub
    ibkr.py           stub
    oanda.py          stub

strategies/                         bundled strategies (loaded at runtime)
  retail_sales_spike_filtered.py    data-release breakout — range-based stop + breakout entry
  retail_sales_spike_fade.py        data-release fade — enter against spike, target baseline
  momentum_continuation.py          spike-momentum with trailing stop
  opening_range_breakout.py         ORB at 9:30 ET; 5/15/30m window variants
  vwap_reversion.py                 intraday VWAP mean-reversion with regime filter
  trend_momentum.py                 daily MA crossover (profitable on GC=F, gc_evolved params)
  example_momentum.py               example/template for custom strategies

ui/                                 React + TypeScript web UI (Bun + RSBuild)
  src/
    main.tsx                        entry point
    App.tsx                         routes + page transitions
    lib/api.ts                      typed client for the /api surface
    lib/utils.ts                    cn() + number/currency formatters
    components/ui/                  shadcn/ui primitives
    components/layout/Sidebar.tsx   nav
    components/StrategyFlow.tsx     Dagre-laid-out pipeline diagram
    pages/                          Dashboard, Strategies, Live, Sessions, Accounts

tests/
  test_engine.py                    pytest suite, no network required
  test_multiwindow_optimizer.py     multi-window + optimizer tests
  test_installer.py                 strategy install/upgrade tests
  test_agents.py                    fork-eval + evolution tests
```

## Data directory

Everything the engine persists lives under `.data/` in the repository root by
default — gitignored so no two clones share state by accident. Override with
`--data-dir` or the `MONEYMAKER_HOME` env var (e.g. `export MONEYMAKER_HOME=~/.moneymaker`
for a shared directory across multiple clones).

```
.data/                             default — gitignored (contents), .gitkeep only
  strategies/        drop-in .py files — any Strategy subclass auto-loads
  sessions/          trade log CSVs + JSON results, one per run
  data_cache/        cached historical bars (parquet)
  evaluations/       rolling fork-eval score trajectories (JSON)
  calendars/         cached economic release date schedules (JSON)
  credentials/       credentials.json, permissions locked to owner
  accounts.json      multi-account registry
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
export FRED_API_KEY=xxxxx
moneymaker credentials set --provider fred --key api_key --env-var FRED_API_KEY

moneymaker credentials list   # always masked, never prints secret values
moneymaker credentials clear --provider fred
```

## Market data providers

Historical and live price data is abstracted behind `DataProvider`
(`engine/data_providers/base.py`). The default is `yfinance` (free, no key).

```
moneymaker backtest --strategy trend_momentum --ticker "GC=F" \
    --start 2025-01-01 --end 2026-01-01 --interval 1d \
    --data-provider yfinance

# Load from a local file instead:
moneymaker backtest --strategy trend_momentum --ticker "GC=F" \
    --start 2025-01-01 --end 2026-01-01 \
    --data-provider csv --data-provider-path /path/to/GC_F.csv
```

Available providers:

- **`yfinance`** (default) — free, no key, 15-second delayed. Intraday data limited to ~60 days.
- **`alpaca`** — free US equity data (API key required). Better for equities than futures.
  ```
  moneymaker credentials set --provider alpaca --key api_key --env-var ALPACA_API_KEY
  moneymaker credentials set --provider alpaca --key api_secret --env-var ALPACA_API_SECRET
  ```
- **`csv`** — load from a local CSV or Parquet file. Useful for custom data sources.
- **`simulated`** — synthetic Brownian motion or fixture replay; no network needed. Ideal for unit tests.

## Economic release calendar

Strategies can gate themselves to actual announcement days rather than trading
on every session. Supported calendar sources:

```python
# In a strategy constructor:
retail_sales_spike_filtered(calendar_series="us_retail_sales")

# Named aliases resolve to FRED series IDs:
# us_retail_sales → FRED RSXFS
# us_cpi          → FRED CPIAUCSL
# us_nfp          → FRED PAYEMS
# us_pce          → FRED PCE
# ... see engine/econ_calendar.py for the full list

# Or use a FRED series ID directly:
retail_sales_spike_fade(calendar_series="RSXFS")
```

The calendar fetches vintage dates from FRED (when was the data first published?),
caches them locally, and silently fails open (trades normally) if the API is
unavailable. Requires a free FRED API key:

```
moneymaker credentials set --provider fred --key api_key --env-var FRED_API_KEY
```

## Execution providers

Where fills and account data come from is abstracted behind
`ExecutionProvider` (`engine/providers/base.py`). Strategy logic, risk
sizing, and trade logging never know or care which provider is in use.

```
moneymaker providers
```

- **`simulated`** (ready) — no broker involved. Fills against the
  reference price with configurable slippage, tracks real per-account
  paper balances, full parity with the account/credential surface a real
  provider would have.
- **`trading212_demo`, `ibkr_paper`, `oanda_practice`** — stubs. Each
  class's docstring in `engine/providers/*.py` documents exactly what
  API calls are needed to finish it.

**Adding a real provider:** subclass `ExecutionProvider`, implement
`authenticate()`, `list_accounts()`, `get_account()`, `create_account()`,
`execute_order()`, and `get_account_balance()` against the broker's real
API, then register the class in `engine/providers/__init__.py`'s
`PROVIDERS` dict.

`is_live` must be `True` on any provider that can place real-money
orders. `make_provider()` refuses to auto-construct those — wiring one up
for real is always a deliberate, explicit step, never a side effect of a
name string.

## Adding a strategy

Drop a `.py` file into `<home>/strategies/` (see `strategies/example_momentum.py`
for the pattern):

```python
from src.strategy import Strategy, StrategyContext, Bar

class MyStrategy(Strategy):
    """One-line description shown in `strategies` list."""
    name = "my_strategy"

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        ...  # mutate ctx to open/close positions
```

It's auto-discovered next time you run `strategies`, `backtest`, or `live`.

### Multi-symbol strategies

For strategies that need correlated data from multiple instruments (e.g. ES
enters only when NQ confirms):

```python
from src.strategy import MultiBarStrategy, StrategyContext, Bar

class ESWithNQConfirmation(MultiBarStrategy):
    name = "es_nq_confirm"
    tickers = ["ES=F", "NQ=F"]   # first = primary (position management ticker)

    def on_secondary_bar(self, ctx, bar, ticker):
        ctx.extra[f"last_{ticker}"] = bar.price  # store for on_bar access

    def on_bar(self, ctx, bar):
        nq = ctx.extra.get("last_NQ=F")
        if nq is None:
            return  # no NQ data yet
        # ... rest of entry logic
```

Run with `MultiBarSimulator.run_backtest({"ES=F": es_df, "NQ=F": nq_df})`.

## API server

FastAPI. All endpoints live under `/api`; interactive docs are generated
automatically at `/docs` (Swagger) and `/redoc`.

```
moneymaker server --port 8787
```

```
GET  /api/strategies
GET  /api/providers
GET  /api/accounts             POST /api/accounts  {name, provider?, currency?, starting_balance?, is_live?}
GET  /api/accounts/<id>
GET  /api/credentials          POST /api/credentials  {provider, key, env_var?|value?}
POST /api/backtest        {strategy, ticker, start, end, interval?, provider?, account_id?, account?, risk_pct?, params?}
POST /api/backtest-multi  {strategy, ticker, windows:[[start,end],...], interval?, provider?, account?, risk_pct?}
POST /api/optimize        {strategy, ticker, param_grid, train_windows, test_windows?, ...}
POST /api/live/start      {strategy, ticker, provider?, account_id?, account?, risk_pct?, end_time?, poll_seconds?}
GET  /api/live/<id>/status     POST /api/live/<id>/stop
GET  /api/live/list
GET  /api/sessions             GET /api/sessions/<filename>
```

Live sessions run as background threads, so you can start one and poll
`/api/live/<id>/status` while it runs. Backtest and live-status responses
flatten the trade metrics (`trade_count`, `total_pnl`, `win_rate`, `running`)
to the top level, with the raw nested `summary` preserved alongside.

When `ui/dist/` exists (after `bun run build`), the server also serves the
web UI at `/`.

## Web UI

A React + TypeScript dashboard lives in `ui/`. Stack: Bun, RSBuild, Tailwind
CSS, shadcn/ui, Motion (animation), Dagre + React Flow (strategy pipeline
diagrams), Lucide (icons), Recharts (P&L charts).

```
cd ui
bun install
bun run dev      # dev server on :5173, proxies /api → :8787
```

Run the API server alongside it (`moneymaker server`) and open
http://localhost:5173.

For a single-origin production setup, build the UI and let FastAPI serve it:

```
cd ui && bun run build
moneymaker server --port 8787     # UI now at http://localhost:8787
```

Pages: **Dashboard** (accounts, balances, live sessions), **Strategies**
(expandable cards with a pipeline diagram and inline backtest runner),
**Live** (start/stop/monitor sessions, polls every 3s), **Sessions** (trade
tables with cumulative P&L charts), **Accounts** (create and list).

## Testing

```
pytest
```

The test suite runs entirely against synthetic price data — no network
calls, no live yfinance requests. All 45 tests pass on Python 3.11 and 3.12.
CI runs on every push via GitHub Actions (`.github/workflows/ci.yml`).

## Known limitations

- yfinance can lag real-time by 15+ seconds and occasionally gaps data —
  fine for evaluating a strategy, not a substitute for a real broker feed.
- The `simulated` provider is the only execution provider that actually works end to end.
- `RiskManager` position sizing assumes CFD/futures-style fractional
  sizing; adapt `position_size()` if you need whole-share constraints for
  equities.
- `BLSCalendar` is a stub — BLS doesn't offer a clean vintage date API.
  Use FRED equivalents or `SimulatedCalendar` instead.

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

# Or auto-generate N equal windows:
moneymaker backtest-multi --strategy trend_momentum --ticker "GC=F" \
    --walk-forward 4 --wf-start 2022-01-01 --wf-end 2026-01-01 --interval 1d
```

## Parameter optimization ("training")

`optimize` grid-searches a strategy's parameters, scored via multi-window
backtests, with an explicit train/test split.

```
moneymaker optimize --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --param-grid '{"stop_pct": [0.003, 0.0045, 0.006], "min_surprise_ratio": [1.5, 2.0, 3.0]}' \
    --train-windows "2026-05-01:2026-06-01,2026-06-01:2026-07-01" \
    --test-windows "2026-07-01:2026-08-01" \
    --top 5
```

Always pass `--test-windows`. The CLI flags any candidate that's profitable
on train but losing on test — treat those with real suspicion.

## Per-run parameter overrides

```
moneymaker backtest --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --start 2026-07-01 --end 2026-08-01 \
    --param min_spike_pct=0.001 --param base_bars=4
```

## Fork-eval and autonomous evolution

`fork-eval` compares strategy variants (declared in `FORKS`) over identical
windows and ranks them by the default objective score:

```
# One-shot comparison
moneymaker fork-eval --strategy retail_sales_spike_fade --ticker "ES=F" \
    --windows "2026-06-18:2026-08-16"

# Rolling mode: slide a window forward and accumulate score trajectories
moneymaker fork-eval --strategy retail_sales_spike_fade --ticker "ES=F" \
    --rolling --rolling-start 2025-01-01 --rolling-end 2026-08-16 \
    --rolling-window 30 --rolling-step 7 --interval 1d

# View accumulated trajectories across all strategies
moneymaker rankings
```

`evolve` hill-climbs a strategy's numeric parameters:

```
moneymaker evolve --strategy retail_sales_spike_fade --ticker "ES=F" \
    --windows "2026-06-18:2026-07-18" \
    --generations 20 --perturbation 0.20
```

Both commands save full JSON results to `~/.moneymaker/sessions/`.
Rolling eval results are saved to `~/.moneymaker/evaluations/`.
