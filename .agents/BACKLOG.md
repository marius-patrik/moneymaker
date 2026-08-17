# Backlog

Items grouped by type. Planned = agreed direction but not started.
In-progress items live in CONTEXT.md's current session section.

---

## Strategy improvements

### retail_sales_spike_fade — spike-fade strategy (DONE 2026-08-16, Phase 4)
Empirical finding (2026-08-16): on real release days (spike ≥ 0.10%), ES
systematically fades the initial spike — breakout-continuation gets 0% win rate.
Implemented in `strategies/retail_sales_spike_fade.py`. FORKS wired with continuation.

### retail_sales_spike_filtered — R:R fix (DONE 2026-08-16)
Switched from fixed-% stop to basing-range stop + breakout entry.
Stop distance now ≈ 3–5 pts (basing range width + buffer) vs prior 34 pts.
Target set at 2:1 R:R relative to stop distance.

### trend_momentum — PROFITABLE strategy (DONE 2026-08-16, Phase 5)
Daily MA crossover on GC=F (gold futures). Evolved params: fast=5, slow=25,
stop_pct=0.0053, long_only=True. 100% window profitability on 4-year walk-forward
(2022, 2023, 2024, 2025-2026), +72% total return on $10k capital over 4 years.
Mechanism: 0.53% tight stop exits false crossovers quickly; real gold trends
run for months. 8.3:1 realized R:R. Named fork `gc_evolved` in FORKS.

### Stub strategies — all implemented (DONE 2026-08-16, Phase 5)
- `momentum_continuation` — follows spike direction on large surprises with
  trailing stop once profitable. 4 FORKS: mom_quick/base/strong/tight.
- `opening_range_breakout` — ORB at 9:30 ET; 5/15/30m window variants.
  R:R bug fixed (target uses stop_dist, not orb_width). max_entry_slippage_pct filter.
- `vwap_reversion` — intraday VWAP mean-reversion. Fully implemented.
  Prior-day range regime filter reduces losses 98% on SPY. 4 FORKS.

### Pre-release volatility filter (DONE 2026-08-16, Phase 6)
`max_pre_range_pct` param on both spike strategies. If the pre-release baseline
window is noisier than the threshold, stand down for the session. Default 0.0
(disabled). Recommended starting value ~0.0020 (0.20%).

### Multi-symbol confirmation (DONE 2026-08-16, Phase 6)
`MultiBarStrategy` base class in src/strategy.py; `MultiBarSimulator` in
src/engine.py. Strategies declare `tickers = [primary, secondary, ...]` and
implement `on_secondary_bar(ctx, bar, ticker)` to accumulate confirmation signals.

### Other strategy ideas
- **News-sentiment overlay**: use a real-time news API to weight entry direction
  based on sentiment of the release headline (requires external data feed)
- **ES/NQ confirmation strategy**: concrete implementation of MultiBarStrategy
  for the ES entry + NQ confirmation use case

---

## Engine / infrastructure

### Scratch-account spam (DONE 2026-08-16)
`run_multi_window_backtest` persisted one account per window, so grid search
and fork-eval (which call it in a loop) left 564 `mw_*` entries in
accounts.json. `AccountManager(ephemeral=True)` keeps scratch accounts in
memory; `make_provider(..., ephemeral=True)` opts in. `accounts prune`
(CLI + API + UI button) cleans up what older versions wrote. Covered by
three regression tests.

### Service manager (DONE 2026-08-16)
`moneymaker service install|start|stop|restart|status|uninstall` wraps
launchd (macOS) and systemd user units (Linux). Templates in `deploy/`;
install renders absolute paths for this machine. Runs `serve --prod`.
User-level only — no sudo. Auto-restart verified by killing the process.

### Data directory default (DONE 2026-08-16)
Default data home is `.data/` under the repo root (gitignored, contents excluded via
`.data/*` + `!.data/.gitkeep`). `MONEYMAKER_HOME` env var or `--data-dir` CLI flag
override it. `~/.moneymaker` is no longer a fallback — users who want a shared dir
across clones must set `MONEYMAKER_HOME` explicitly.

### Volume support in Bar (DONE 2026-08-16, P002)
`Bar.volume: float = 0.0` added. Simulator passes `row["Volume"]` when present.

### ctx.bars ring buffer (DONE 2026-08-16, P005)
`StrategyContext.max_bars: int = 0` (0 = unlimited). Simulator trims bars list
after each append. Strategies set `max_bars` to cap memory use.

### Data provider abstraction (DONE 2026-08-16, P014)
`src/data_providers/` package with DataProvider ABC. yfinance, Alpaca, CSV,
Simulated providers. `--data-provider` and `--data-provider-path` CLI flags.

### Economic release calendar (DONE 2026-08-16, P008)
`src/econ_calendar.py` with FRED, BLS stub, and Simulated implementations.
Named aliases, local caching, fail-open behavior. `calendar_series` param on
spike strategies.

### Stub provider implementation
Three broker stubs (`trading212_demo`, `ibkr_paper`, `oanda_practice`) need
real API calls wired. Decision to implement ANY of these is always a separate,
explicit discussion — never done as a side effect of another task.

### Live data feed beyond yfinance
yfinance is best-effort / 15-second delayed. Alpaca is now available as a data
provider for US equities. For futures (ES=F, GC=F), a dedicated futures data
feed (Rithmic, CQG, IB TWS) is needed for real-money live mode.
Currently acceptable for strategy development; not acceptable for real-money.

---

## Intelligence layer

### [PLANNED] ML strategy evolution engine
Automated strategy parameter search beyond grid search:
- **Bayesian optimization** (e.g., Optuna): smarter than grid search; models
  the objective function and proposes parameter combos that are likely to improve
  it, rather than trying all combinations exhaustively.
- **Genetic / evolutionary algorithms**: evolve a population of strategy
  configurations across generations, selecting for robustness across multiple
  windows rather than a single score.
- **Walk-forward validation**: required companion to any ML search — train on
  window N, test on window N+1, repeat. A parameter set that's robust across
  all walk-forward folds is far more trustworthy than one optimized on a single
  held-out window.
- Key constraint: with only ~12 independent monthly data release events per year
  for any given release, sample size is tiny. Overfitting is near-certain with
  more than 2–3 free parameters. Any ML search must penalize complexity
  (fewer parameters = better, all else equal).
- Suggested first implementation: Optuna study wrapping the existing
  `run_multi_window_backtest` as the objective, with walk-forward splits and
  a pruner that kills trials early if the first window is strongly negative.

### [PLANNED] Deterministic strategy finding engine
Systematic rule enumeration across historical data:
- Define a vocabulary of atomic signal predicates (price > VWAP, spread vs
  yesterday's close > X%, consecutive up-closes ≥ N, etc.) and entry/exit
  rules (stop at N%, target at M%, time-box at T).
- Enumerate combinations of predicates and rules, backtest each, filter for
  statistical significance.
- The hard problem: with 60 days of 5m data, the number of bars is large but
  the number of INDEPENDENT trade opportunities is small (~40 for a daily
  data-release strategy). Any rule that produces fewer than 20 trades should
  be treated as statistically uninterpretable regardless of reported win rate.
- Suggested approach: enumerate predicate combinations, run them through the
  existing `grid_search` / `run_multi_window_backtest` machinery with
  walk-forward splits, and only surface rules where the test-window P&L is
  positive AND the 95% CI of per-trade P&L excludes zero (bootstrap resampling
  of the trades, not the bars).

---

## Operational

### GitHub repo visibility — CONFIRMED PRIVATE (2026-08-16)
Confirmed via `gh repo view marius-patrik/moneymaker --json visibility`.

### CI / automated testing — ACTIVE (2026-08-16)
GitHub Actions workflow at `.github/workflows/ci.yml`. Runs `pytest` on every
push. 45 tests pass on ubuntu-latest, Python 3.11 and 3.12.

### Background jobs for long operations (DONE 2026-08-16)
fork-eval, evolve and optimize each run many full backtests and were holding
the HTTP request open for minutes. `src/jobs.py` runs them in daemon threads
and returns a job id; clients poll `/api/jobs/<id>`. `?background=false`
still blocks for curl use. Jobs are in-memory by design — the durable output
already lands in sessions/ and evaluations/. Cancellation is cooperative.
UI has a Jobs tab and per-panel status badges. 7 tests.

### Mobile-first responsive UI (DONE 2026-08-16)
One implementation, not a separate mobile build. Below `md` the sidebar
becomes a slide-over drawer behind a top-bar hamburger; grids collapse,
wide tables scroll in-container, dialogs are viewport-bounded with dvh.

### serve --prod rebuild skip (DONE 2026-08-16)
`_dist_is_fresh()` compares ui/dist against every build input, so a service
restart with an unchanged UI skips the bundle step: ~35s → 5s.
`--force-build` overrides.

### Trading-desk UI (DONE 2026-08-16)
Live → Trade: manual order ticket (POST /api/orders, GET /api/quote),
strategy launch, and open positions. Strategy cards also gained "Go live".
Sessions merged into Accounts as a tab. Dashboard driven by GET /api/stats.
Strategy creation from the UI (POST /api/strategies) compiles and load-checks
the source before saving. Providers grouped data/news/execution with stubs
hidden. Data directory settable from Settings, applied on restart.

Bugs fixed along the way: balances read `starting_balance` where the record
stores `balance` (dashboard showed NaN, cards 0 — no data was lost); the
`popover` colour was defined in CSS but never registered in tailwind.config,
so every dropdown rendered transparent.

### Visual system rebuild (DONE 2026-08-16)
Frosted glass only reads as glass when content moves under it, so the
foundation was rebuilt around layered surfaces: an ambient radial wash on the
page, cards elevated above it, and sticky per-page headers plus the sidebar
frosted over the top. Glass classes use @apply so Tailwind emits both
backdrop-filter spellings — a hand-written one is minified to the -webkit-
prefix alone and silently stops working.

Also: profit/loss became theme tokens (they were hardcoded and dim against
dark), radius 0.875rem, elevation with a top highlight in dark, tabular
figures, uppercase metric labels, an equity-curve chart on the dashboard
(GET /api/equity), and denser metric cards.

Gotcha worth remembering: a component-layer class loses to a utility class,
so `.metric-label` on a `CardTitle` was overridden by its `text-2xl`.

### Trading desk (DONE 2026-08-16)
The Trade tab was a full-width form with a dead lower half. Rebuilt as a
two-column desk: price chart (GET /api/history) with last price, change,
session high/low, beside a compact ticket that quotes automatically as the
ticker is typed and shows notional against buying power.

### Strategy list density + provenance (DONE 2026-08-16)
Collapsed rows were tall cards holding two lines; they are now single dense
rows. `source` distinguished only built-in from custom, so every strategy
shipping with the repo was labelled as the user's own — it now reports
built-in / bundled / custom by checking the bundled strategies directory.
Pipeline diagram nodes overlapped because Dagre was told 150px while the
node had no fixed width; both agree now and the labels truncate.

### Zero P&L was coloured as a win (DONE 2026-08-16)
pnlColor used `n >= 0`, so a session that took no trades rendered $0.00 in
profit green. Zero and null are neutral now; only a genuine gain is green.

### UI reinvented as a terminal (DONE 2026-08-16)
Replaced the card-dashboard layout with terminal chrome: a global context bar
(equity / P&L / win rate / trades / live dot / clock), a bottom status strip,
a Panel + Stat + DataTable primitive set, and a ⌘K command palette. Pages are
panels of dense tables rather than stacks of floating cards.

AnimatedIcon was rewritten: variant propagation from a parent whose `animate`
prop pinned children to rest meant the icons never moved. It now tracks hover
on the nearest interactive ancestor via animation controls — verified by
measuring the transform matrix before and after hover.

### Panel language applied app-wide (DONE 2026-08-16)
Research, Accounts, Trade and the Dashboard all use Panel/Stat/DataTable now,
so no page still shows the old floating-card treatment. Accounts and sessions
render as tables; duplicated header lines were folded into panel titles and
actions.

### Strategy list folded into one panel (DONE 2026-08-16)
Rows were individual floating cards with gaps between them; they are now
divided rows inside a single panel, matching every other list in the app.
Expanded content flows inline on a tinted ground rather than inside a nested
card. TopBar metrics drop out at breakpoints rather than clipping mid-digit.

### IA restructured around the workspace (DONE 2026-08-16)
Strategies, Research and Trade were three destinations for one workflow.
They are now tabs over a selected system inside a Workspace, with the systems
list as the sidebar's actual content. Five sections became three (Overview /
Workspace / Portfolio). The nav rail collapses to icons and widens on hover;
mobile gets a bottom tab bar instead of a drawer.

Added: instrument search (GET /api/search via yfinance), trade-P&L
distribution (GET /api/pnl-distribution), self-hosted Inter + JetBrains Mono,
and full trade tables (instrument, side, open/close, size, prices, reason).

useResource replaces the `.catch(() => {})` pattern that rendered a failed
request as an empty list — which is why accounts sometimes showed "none".

### Sections split by subject (DONE 2026-08-16)
Trade is instrument-first (watchlist + chart + ticket); Strategies is
system-first (systems sidebar, Backtest and Lab tabs, name-as-picker).
Portfolio shows open positions and trade history with an account filter
(GET /api/positions). Account administration moved to Settings, which is now
a page rather than a modal.

Trade records gained a `ticker` field — the log did not record what was
traded, so every instrument column was empty.

### Manual positions, TradingView charts, per-strategy metrics (DONE 2026-08-16)
Placing an order adjusted the balance and left no record, so it genuinely
looked like nothing happened. src/book.py persists open manual positions and
appends closed ones to a session log, so they join the same history as
strategy trades. Positions are inspectable (marked to market) and closeable.

Charts are lightweight-charts (TradingView's own library): candles or line,
5m–1wk, crosshair with OHLC readout, zoom and pan. /api/history returns OHLCV.

Strategies list and header now show realised P&L, win rate, profit factor,
trades and runs per system (GET /api/strategies/stats). Provenance badges
removed — every strategy is the user's to edit, and any can be duplicated.

### Indicator overlays (DONE 2026-08-17)
SMA, EMA, VWAP and RSI in src/indicators.py, exposed via /api/indicators and
/api/indicator/<kind>/<ticker>. Computed server-side deliberately: strategies
already reason about these, and one implementation cannot drift from another.
VWAP falls back to an unweighted mean when the feed reports no volume, which
yfinance futures do. 12 tests.

### Limit/stop orders, news, universal search (DONE 2026-08-17)
src/orders.py holds resting orders; a 20s monitor sweeps and fills them.
Protective exits attach to a position and are cancelled with it — a
stop-loss outliving its position would open a new one in the opposite
direction. 20 tests.

Instrument search gained aliases: Yahoo carries no spot metals, so "XAUUSD"
returned nothing. It now maps to GC=F / PAXG-USD / GLD with a note saying
why, and a literal symbol is probed when the index misses it.

/api/news for headlines, /api/quick-search across instruments, systems,
accounts and runs — the palette searched only page names before.
