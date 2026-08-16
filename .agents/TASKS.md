# Tasks

Current session working list. Updated as work progresses.
Completed tasks are marked `[x]`. Stale tasks removed at session end.

Session: 2026-08-16 — Scaffolding + conventions + strategy signal quality

---

## Phase 1: Scaffolding + conventions [complete]

- [x] Fix README (renamed files: PROJECT_HISTORY.md → CONTEXT.md, AGENT_PROMPT.md → HANDOFF.md)
- [x] Update README project layout (new modules, strategies, docs)
- [x] Create AGENTS.md
- [x] Create PLAN.md
- [x] Create PRD.md
- [x] Create QUESTIONS.md
- [x] Create PROPOSALS.md (engine review + architectural proposals)
- [x] Create TASKS.md (this file)
- [x] Create GitHub Actions CI (.github/workflows/ci.yml)
- [x] Test suite gaps: add missing coverage (see PROPOSALS.md P006, P003)
- [x] Commit + push Phase 1

## Phase 2: Strategy signal quality [complete — 2026-08-16]

- [x] Calibrate min_spike_pct: identify actual retail sales release dates in backtest window
- [x] Run backtest with min_spike_pct ≥ 0.10% (gate out noise)
- [x] Evaluate: trade count, win rate, P&L vs baseline
- [x] Finding: 0% win rate on real release days — spike FADES, continuation approach is wrong
- [x] Commit + push Phase 2 with CONTEXT.md + PROPOSALS.md update (fade approach P008a)

## Phase 3: Strategy install + versioning [complete — 2026-08-16]

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

## Phase 4: Agent capabilities + fork system [complete — 2026-08-16]

- [x] Create .agents/ directory; git mv all docs there except README
- [x] Create .agents/BLOCKERS.md and .agents/DEFERRED.md
- [x] Strategy.params() classmethod (inspect.signature → {param: default})
- [x] Strategy.from_params() classmethod (ignores unknown keys)
- [x] Strategy.FORKS class variable (list of (label, strategy_name, params_dict))
- [x] engine/agents/__init__.py
- [x] engine/agents/forker.py — ForkResult, ForkSetResult, fork_and_eval()
- [x] engine/agents/evolution.py — EvolutionResult, evolve() hill-climbing
- [x] CLI: --param KEY=VALUE for backtest and live (with type coercion from signature)
- [x] CLI: fork-eval subcommand (resolves strategy names via load_strategies)
- [x] CLI: evolve subcommand
- [x] strategies/retail_sales_spike_fade.py — fade strategy with FORKS wiring
- [x] FORKS wiring in retail_sales_spike_filtered.py
- [x] tests/test_agents.py — 12 tests: params, from_params, FORKS, fork_and_eval, evolve
- [x] Update README project layout
- [x] Update CONTEXT.md, PLAN.md, TASKS.md
- [x] Commit + push
