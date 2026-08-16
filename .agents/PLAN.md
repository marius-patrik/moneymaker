# Plan

## Current state (as of 2026-08-16)

- **Engine**: backtest, live-paper, multi-window backtest, grid-search optimizer.
  Simulated execution provider with full account parity. HTTP+JSON API server.
  Fork-eval + hill-climbing evolution (src/agents/). Rolling fork-eval with
  score trajectory tracking. MultiBarSimulator for multi-ticker strategies.
- **Data providers**: yfinance (default), Alpaca, CSV, Simulated (Brownian + fixture).
  DataProvider ABC in src/data_providers/. --data-provider CLI flag.
- **Economic calendar**: FRED vintage dates API, SimulatedCalendar, BLSCalendar stub.
  Named aliases (us_retail_sales → FRED RSXFS, etc.). Cached locally.
- **Strategies**: `retail_sales_spike` (v1), `retail_sales_spike_filtered` (v2,
  breakout + range stop), `retail_sales_spike_fade` (v3, fade against spike).
  `momentum_continuation`, `opening_range_breakout`, `vwap_reversion` (all fully
  implemented). `trend_momentum` (daily MA crossover, profitable on GC=F).
- **Tests**: 45 tests, all passing, entirely synthetic data (no network). CI on
  GitHub Actions (ubuntu-latest, Python 3.11 + 3.12).
- **Version**: 0.3.0
- **License**: personal use only (see LICENSE).

## Roadmap

### Phase 1: Scaffolding + conventions [complete — 2026-08-16]
Agents-superproject doc conventions applied. README fixed. CI added.
Docs moved to .agents/. BLOCKERS.md and DEFERRED.md added.

### Phase 2: Strategy signal quality [complete — 2026-08-16]
Finding: large spikes systematically FADE. Breakout-continuation gets 0% win rate
on real release days. Fade strategy implemented. See CONTEXT.md.

### Phase 3: Strategy install + versioning system [complete — 2026-08-16]
Hash-tracked install/upgrade. Version tracking. upgrade-strategies, upgrade commands.

### Phase 4: Agent capabilities + fork system [complete — 2026-08-16]
- Docs moved to .agents/; BLOCKERS.md + DEFERRED.md added.
- Strategy.params(), from_params(), FORKS class variable.
- src/agents/forker.py: fork_and_eval() — run N strategy variants, rank by score.
- src/agents/evolution.py: evolve() — hill-climb numeric params.
- CLI: --param KEY=VALUE on backtest/live; fork-eval and evolve subcommands.
- retail_sales_spike_fade.py: fade strategy with FORKS wiring to continuation variant.
- 12 new tests in tests/test_agents.py.

### Phase 5: Profitable strategy + engine overhaul [complete — 2026-08-16]
- trend_momentum on GC=F: 100% 4-year walk-forward consistency, gc_evolved params.
- All strategy stubs implemented: momentum_continuation, opening_range_breakout, vwap_reversion.
- Engine proposals adopted: P002 (Bar.volume), P003 (dedup), P004 (cache TTL), P006 (dangling position).
- fork-eval and evolve validated on real tickers (CL=F, ZN=F, SPY).
- P009: --walk-forward N on backtest-multi.
- P010: open P&L in session summary.
- vwap_reversion: prior-day range regime filter (98% loss reduction).

### Phase 6: Data abstraction + engine proposals [complete — 2026-08-16]
- P005: StrategyContext.max_bars ring buffer.
- P011: rolling fork-eval + rankings CLI command.
- P013: max_pre_range_pct volatility filter on spike strategies.
- P014: DataProvider abstraction (yfinance, Alpaca, CSV, Simulated); --data-provider flag.
- P008: EconCalendar service (FRED + SimulatedCalendar + BLS stub); calendar_series strategy param.
- P012: MultiBarStrategy base class + MultiBarSimulator.
- Branch renamed master → main.
- LICENSE (personal use only) + CONTRIBUTING.md added.

### Phase 7: Stub provider implementation [requires explicit decision]
Each of `trading212_demo`, `ibkr_paper`, `oanda_practice` requires a separate,
explicit session discussion before wiring real API calls. Never done as a side
effect. Only begin once a specific provider is named and confirmed in session.

### Phase 8: Intelligence layer [backlog]
ML evolution engine (Optuna + walk-forward), deterministic strategy finder
(predicate enumeration + bootstrap significance). See BACKLOG.md.
