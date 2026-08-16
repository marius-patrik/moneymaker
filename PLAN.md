# Plan

## Current state (as of 2026-08-16)

- **Engine**: backtest, live-paper, multi-window backtest, grid-search optimizer. Simulated provider with full account parity. HTTP+JSON API server.
- **Strategies**: `retail_sales_spike` (v1, fixed-% stop), `retail_sales_spike_filtered` (v2, breakout + range-based stop). Stubs: `momentum_continuation`, `opening_range_breakout`, `vwap_reversion`.
- **Tests**: 23 tests, all passing, entirely synthetic data (no network).
- **Version**: 0.2.0

## Active phase

### Phase 1: Scaffolding + conventions [in progress]
Apply agents-superproject doc conventions. Create AGENTS.md, PLAN.md, PRD.md,
QUESTIONS.md, PROPOSALS.md, TASKS.md. Fix README to match current file names.
Add GitHub Actions CI. Review codebase and populate PROPOSALS.md.

### Phase 2: Strategy signal quality [queued]
`retail_sales_spike_filtered` currently fires ~40× in 60 days on noise spikes;
retail sales releases only once monthly. Fix: calibrate `min_spike_pct` to actual
release sizes (≥0.10–0.15% vs median noise 0.03%), or add a release-date filter.
Target: ≤3 trades per 60-day window on real release events only. Run backtest,
document findings in CONTEXT.md.

## Roadmap

### Phase 3: Strategy install + versioning system [design pending]
Bundled strategies installed to `~/.moneymaker/strategies/` on first install,
not loaded live from the repo dir. Merge mechanism on upgrade: skip user-modified
files, update unchanged ones. Version tracking in home dir; `moneymaker upgrade`
command. See PROPOSALS.md P-INSTALL for design options.
**Requires design approval before implementation.**

### Phase 4: CI + test suite [queued after Phase 1]
GitHub Actions workflow (pytest on push). Additional test coverage for:
- CLI entry points (smoke tests)
- `load_strategies` two-tier loading
- DataFeed cache behavior
- Dangling-position detection at backtest end
- Bar deduplication in live mode
See PROPOSALS.md for full gap list.

### Phase 5: Stub provider implementation [requires explicit decision]
Each of `trading212_demo`, `ibkr_paper`, `oanda_practice` requires a separate,
explicit session discussion before wiring real API calls. Never done as a side
effect. Only begin once a specific provider is named and confirmed in session.

### Phase 6: Intelligence layer [backlog]
ML evolution engine (Optuna + walk-forward), deterministic strategy finder
(predicate enumeration + bootstrap significance). See BACKLOG.md.
