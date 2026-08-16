# Plan

## Current state (as of 2026-08-16)

- **Engine**: backtest, live-paper, multi-window backtest, grid-search optimizer.
  Simulated provider with full account parity. HTTP+JSON API server.
  Fork-eval + hill-climbing evolution (engine/agents/).
- **Strategies**: `retail_sales_spike` (v1, fixed-% stop), `retail_sales_spike_filtered`
  (v2, breakout + range-based stop), `retail_sales_spike_fade` (v3, fade against spike).
  Stubs: `momentum_continuation`, `opening_range_breakout`, `vwap_reversion`.
- **Tests**: 45 tests, all passing, entirely synthetic data (no network).
- **Version**: 0.3.0

## Roadmap

### Phase 1: Scaffolding + conventions [complete — 2026-08-16]
Agents-superproject doc conventions applied. README fixed. CI added.
Docs moved to .agents/. BLOCKERS.md and DEFERRED.md added.

### Phase 2: Strategy signal quality [complete — 2026-08-16]
Finding: large spikes systematically FADE. Breakout-continuation gets 0% win rate
on real release days. See CONTEXT.md.

### Phase 3: Strategy install + versioning system [complete — 2026-08-16]
Hash-tracked install/upgrade. Version tracking. upgrade-strategies, upgrade commands.

### Phase 4: Agent capabilities + fork system [complete — 2026-08-16]
- Docs moved to .agents/; BLOCKERS.md + DEFERRED.md added.
- Strategy.params(), from_params(), FORKS class variable.
- engine/agents/forker.py: fork_and_eval() — run N strategy variants, rank by score.
- engine/agents/evolution.py: evolve() — hill-climb numeric params.
- CLI: --param KEY=VALUE on backtest/live; fork-eval and evolve subcommands.
- retail_sales_spike_fade.py: fade strategy with FORKS wiring to continuation variant.
- 12 new tests in tests/test_agents.py.

### Phase 5: Fade strategy validation [active]
Run `fork-eval` to empirically test fade vs continuation on real data.
Expected: fade scores better on real release days (≥0.10% spike).
If confirmed: tune fade parameters via `evolve`.

### Phase 6: Stub provider implementation [requires explicit decision]
Each of `trading212_demo`, `ibkr_paper`, `oanda_practice` requires a separate,
explicit session discussion before wiring real API calls. Never done as a side
effect. Only begin once a specific provider is named and confirmed in session.

### Phase 7: Intelligence layer [backlog]
ML evolution engine (Optuna + walk-forward), deterministic strategy finder
(predicate enumeration + bootstrap significance). See BACKLOG.md.
