# Handoff

**Updated at the end of every working round.** If the date below is older
than the last commit, this file is stale and the person who committed
skipped a step.

Last updated: 2026-08-17

---

## What this is

A provider-agnostic trading engine with a web terminal. Strategies are
Python files; the engine backtests, optimises and runs them, and the UI is
how you drive it. Nothing places real-money orders — `make_provider` refuses
to construct a live provider, and enabling one is a separate, explicit
decision that has never been taken.

## Start here

```
moneymaker serve            # API + UI, hot reload, one command
moneymaker hooks install    # doc/secret/test guards (do this first)
moneymaker service install  # run it permanently, starts at login
```

Data lives in `.data/` beside the repo. Override with `MONEYMAKER_HOME`,
`--data-dir`, or the field in Settings.

## The documents, and what each is for

| File | Holds |
|---|---|
| `PRD.md` | What the product is and is not meant to do |
| `PLAN.md` | Phases, and where the current one stands |
| `CONTEXT.md` | Chronological record — decisions, bugs found, features shipped |
| `BACKLOG.md` | **Only outstanding work.** Finished items move to CONTEXT |
| `DEFERRED.md` | Deliberately not doing, with the trigger to revisit |
| `PARITY.md` | How the app measures against Trading212 and TradingView |
| `QUESTIONS.md` | Open questions that do not block |
| `BLOCKERS.md` | What is actually stopping progress |
| `HANDOFF.md` | This file |

The pre-commit hook enforces the BACKLOG rule and checks that every API
route appears in the README, because both drifted before anyone noticed.

## Round-end checklist

1. Tests green — `pytest` (the pre-push hook blocks a red suite).
2. UI typechecks and builds if you touched `ui/`.
3. Docs match the change: README for API or feature surface, CONTEXT for
   what happened, BACKLOG for what is left.
4. Update the date at the top of this file.
5. Push. Every push to `main` cuts a release, so do not push work in progress.

## Standing constraints

- **No real-money trading.** Broker stubs stay stubs unless the user asks
  for one by name in that session.
- **Never commit credentials.** The pre-commit hook checks, but the rule
  comes first.
- **Never push a red suite.** Every push releases.

## Where things are

```
src/           engine, API, orders, ticks, jobs, services
strategies/    starting points, copied into the data dir on install
ui/            React terminal (Bun, RSBuild, lightweight-charts)
deploy/        launchd and systemd templates
.githooks/     the guards described above
```
