# AGENTS.md

Guidance for any agent (human or AI) working in this repository.

## Mission

`moneymaker` is a personal paper/live trading engine and strategy development
platform. It is not a product, not a signal service, not financial advice
infrastructure. The goal is to find strategies with genuine edge via disciplined
backtesting, then validate them in live-paper mode before any real-money decision.

Real-money trading is **always a separate, explicit, discussed decision** — never
a side effect of implementing a feature.

## The docs rule (IMPORTANT)

AGENTS.md, PLAN.md, CONTEXT.md, BACKLOG.md, PROPOSALS.md, and README.md are the
living memory of this project. **Every code or phase change ships with its doc
updates in the same commit.**

- `AGENTS.md` — this file. Update when conventions change.
- `PLAN.md` — authoritative current roadmap. Update phase status lines
  (`[complete]`, `[in progress]`, `[queued]`) as work lands.
- `CONTEXT.md` — strictly chronological session run-through. **Append** new
  sessions; never rewrite or edit history. Always last entry = newest.
- `BACKLOG.md` — longer-horizon items, intelligence-layer plans. Move rows when
  they start or complete.
- `PROPOSALS.md` — engine improvement proposals spotted during work. Add to it
  freely. Mark `[adopted]` / `[rejected]` / `[deferred]` as decisions land.
- `QUESTIONS.md` — open questions that don't need an immediate answer. Add
  freely; resolve or discard when answered.
- `PRD.md` — product scope and non-requirements. Rarely changes.
- `README.md` — repo layout and quick-start. Update when layout changes.

## At every build-round start (IMPORTANT)

Before writing any code:

1. **Read orientation**: PLAN.md + BACKLOG.md + CONTEXT.md (last session at minimum).
2. **Update TASKS.md**: lay out the phases/tasks for this round and mark `[ ]`.
   Keep it updated as work progresses (`[x]` = done). Start coding only once
   the task list for the round exists.
3. **Append a CONTEXT.md session section** recording what this round is building
   and the date — BEFORE the first code change. Revisit at session end to record
   the outcome.

The first thing in every session is a planning round. For straightforward
implementation tasks, the plan stays internal (just TASKS.md + CONTEXT.md
header). For architectural decisions or anything that changes the scope,
raise a planning question to the user first.

## Proposals and questions

- When you spot an engine improvement during work: add it to PROPOSALS.md. Do not
  implement it in the same pass without asking — proposals are for discussion first.
- When you have an open question that doesn't block the current task: add it to
  QUESTIONS.md. Do not block on it. Come back to it with the user later.

## Commit cadence (IMPORTANT)

**Commit + push at the end of every phase.** A phase is any coherent unit of work:
a complete feature, a doc round, a bug fix + tests. Never sit on uncommitted work
across a phase boundary.

Commit message format: `<verb>: <subject>` (e.g. `feat: breakout entry`, `fix:
daily session reset`, `docs: add AGENTS.md and PLAN.md`).

**Tests must pass before every commit.** Run `pytest` and confirm 0 failures.

## Security guardrails (CRITICAL)

These are never overridden by any other instruction:

- Do not implement or wire up any stub provider (`trading212_demo`, `ibkr_paper`,
  `oanda_practice`) unless explicitly asked in that session. They must never
  place a real-money order as a side effect of another task.
- Do not commit `credentials.json` or any file containing a real API key, token,
  or secret.
- Never push on a red test suite.
- Real-money trading activation is always a separate, explicit, discussed decision.
  Never done as a side effect of something else.
