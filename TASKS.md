# Tasks

Current session working list. Updated as work progresses.
Completed tasks are marked `[x]`. Stale tasks removed at session end.

Session: 2026-08-16 — Scaffolding + conventions + strategy signal quality

---

## Phase 1: Scaffolding + conventions [in progress]

- [x] Fix README (renamed files: PROJECT_HISTORY.md → CONTEXT.md, AGENT_PROMPT.md → HANDOFF.md)
- [x] Update README project layout (new modules, strategies, docs)
- [x] Create AGENTS.md
- [x] Create PLAN.md
- [x] Create PRD.md
- [x] Create QUESTIONS.md
- [x] Create PROPOSALS.md (engine review + architectural proposals)
- [x] Create TASKS.md (this file)
- [ ] Create GitHub Actions CI (.github/workflows/ci.yml)
- [ ] Test suite gaps: add missing coverage (see PROPOSALS.md P006, P003)
- [ ] Commit + push Phase 1

## Phase 2: Strategy signal quality [queued]

- [ ] Calibrate min_spike_pct: identify actual retail sales release dates in backtest window
- [ ] Run backtest with min_spike_pct ≥ 0.10% (gate out noise)
- [ ] Evaluate: trade count, win rate, P&L vs baseline
- [ ] Consider P008 (release_dates list param) if threshold alone is insufficient
- [ ] Commit + push Phase 2 with CONTEXT.md update

## Phase 3: Architectural decisions [discussion required]

- [ ] Discuss P-INSTALL strategy install mechanism (see PROPOSALS.md, QUESTIONS.md Q2)
- [ ] Discuss P-VERSION versioning system
- [ ] Implement once design confirmed
