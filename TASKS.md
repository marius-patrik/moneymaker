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

## Phase 2: Strategy signal quality [complete]

- [x] Calibrate min_spike_pct: identify actual retail sales release dates in backtest window
- [x] Run backtest with min_spike_pct ≥ 0.10% (gate out noise)
- [x] Evaluate: trade count, win rate, P&L vs baseline
- [x] Finding: 0% win rate on real release days — spike FADES, continuation approach is wrong
- [x] Commit + push Phase 2 with CONTEXT.md + PROPOSALS.md update (fade approach P008a)

## Phase 3: Strategy install + versioning [in progress]

Design approved (2026-08-16):
- Merge on conflict: skip modified files, report them, user decides → context-dependent
- Repo can be public for upgrade command

- [x] Rename moneymaker/ → engine/ (package dir); update all imports + pyproject.toml
- [x] engine/__init__.py — __version__ via importlib.metadata
- [x] engine/installer.py — hash-tracked install/upgrade logic + manifest
- [x] engine/config.py — version tracking, notice on version change
- [x] engine/cli.py — install-strategies, upgrade-strategies (--force), upgrade commands
- [x] pyproject.toml — declare bundled strategies as package-data; bump to 0.3.0
- [x] tests/test_installer.py — 8 tests: install, idempotent, conflict, force, new-file
- [x] Update CONTEXT.md + PLAN.md
- [x] Commit + push
