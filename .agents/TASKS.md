# Tasks

Current session working list. Updated as work progresses.
Completed tasks are marked `[x]`. Stale tasks removed at session end.

Session: 2026-08-16 — Phase 6: data abstraction + engine proposals + doc alignment

---

## Phase 6: Engine proposals + data abstraction [complete — 2026-08-16]

- [x] P005: StrategyContext.max_bars ring buffer; Simulator trims after append
- [x] P011: rolling_fork_eval() + rankings CLI command; score trajectories in evaluations/
- [x] P013: max_pre_range_pct volatility filter on both spike strategies (default 0.0)
- [x] P014: DataProvider ABC; yfinance/Alpaca/CSV/Simulated providers; --data-provider CLI flag
- [x] P008: EconCalendar (FRED vintage dates + SimulatedCalendar + BLS stub); calendar_series param
- [x] P012: MultiBarStrategy base class + MultiBarSimulator
- [x] Branch renamed master → main
- [x] LICENSE (personal use only) + CONTRIBUTING.md
- [x] Docs alignment: README, PLAN, BACKLOG, QUESTIONS, TASKS, CONTEXT
- [x] Commit + push

## All proposals status

| ID | Title | Status |
|----|-------|--------|
| P001 | CLI --param injection | adopted |
| P002 | Bar.volume field | adopted |
| P003 | Bar dedup in live mode | adopted |
| P004 | DataFeed cache TTL | adopted |
| P005 | ctx.bars ring buffer | adopted |
| P006 | Dangling position at backtest end | adopted |
| P007 | Strategy params() classmethod | adopted |
| P008 | EconCalendar integration | adopted |
| P008a | Spike-fade strategy | adopted |
| P009 | Walk-forward auto-windows | adopted |
| P010 | Open P&L in session summary | adopted |
| P011 | Rolling eval + rankings | adopted |
| P012 | MultiBarStrategy | adopted |
| P013 | Pre-release volatility filter | adopted |
| P014 | DataProvider abstraction | adopted |
| P-INSTALL | Strategy install system | adopted |
| P-VERSION | Version tracking + upgrade | adopted |
