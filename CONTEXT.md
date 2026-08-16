# Project history and context

This document exists because the conversation that produced this repo
isn't accessible to you — you can only read files, not chat history. This
is that history, written out, so nothing gets lost in the handoff.

## How this started

The person wanted to trade a CFD off a specific economic data release
(US Retail Sales, July 2026 print, released Aug 14 2026 8:30am ET) and
initially asked for exact buy/sell timing. That's not answerable by
anyone — no model, no human, no fund has reliable foresight into
short-term price action. What was actually built instead, over several
iterations: a real execution plan (entry/stop/target rules tied to price
action around the release, not clock times), then a script to paper-test
that plan, which grew into this full engine.

## Why it's built the way it is

- **Provider-agnostic from early on.** Trading 212's official API doesn't
  cover CFD accounts at all (confirmed via live web search, Aug 2026) —
  only Invest/ISA equity accounts. That single finding is why execution
  is abstracted behind `ExecutionProvider` instead of hardcoded to one
  broker: whatever broker eventually gets wired up for real, the engine
  itself shouldn't need to change.
- **Simulated provider has full parity with real ones on purpose** —
  same account/credential surface, multi-account support — specifically
  so testing a strategy against `simulated` today and against a real
  broker later requires zero code changes to the strategy or engine.
- **Credentials never stored in plaintext by default.** Env-var
  references are the recommended path; direct storage is chmod 600 but
  still flagged as "treat like a password vault," not silently trusted.
- **Every provider except `simulated` is a deliberate stub.** Not an
  oversight — placing real-money orders needs a separate, explicit
  decision each time, not something that happens as a side effect of a
  config string. `make_provider()` refuses to auto-construct anything
  marked `is_live=True`.
- **The strategy stop/target use raw pre-slippage signal price, not the
  fill price**, as their anchor. Found while writing tests, documented
  in `RetailSalesSpikeStrategy`'s docstring rather than silently fixed —
  it's a legitimate design choice (either anchor is defensible), just
  one worth knowing about if tuning `stop_pct` against live P&L rather
  than backtest output.

## Two real bugs found and fixed along the way

**1. Duplicate-bar counting in the basing window.** The original
`retail_sales_spike` strategy counted the current bar twice when
checking if price had "based" after a spike, effectively treating one
bar as satisfying a 2-bar consistency check. Found while tracing through
a synthetic test by hand. Fixed by not double-appending the current bar
to the post-spike window.

**2. Session state not resetting across calendar days (the more serious
one).** A single continuous backtest spanning multiple days would
silently take at most ONE trade total, no matter the range —
`hard_exit_time` was set once on day one and never updated, so every
later day looked "timed out" before the strategy ever evaluated it. This
was found by *interpreting a real handoff report*: an agent (Grok) ran
`backtest --strategy retail_sales_spike --ticker ES=F --start 2026-07-01
--end 2026-08-01` against real data and got back "Trades: 1, P&L:
-109.05" — a number that looked suspiciously low for a full month, which
led to actually reproducing the bug locally and fixing it (see
`reset_session_if_new_day()` in `moneymaker/strategy.py`).

**The practical implication:** any backtest result from before that fix
— including the `-109.05` figure above — reflects roughly ONE
observation across the whole date range, not real coverage of a month of
trading days. It should not be treated as evidence the strategy loses
money; it's evidence the engine only gave it one chance. This is worth
re-verifying with a fresh real-data run now that the fix is in, and
worth remembering as a category of bug to watch for in anything else you
build here: per-session state that's supposed to reset on some boundary
(a new day, a new symbol, a new account) but doesn't.

## The retail_sales_spike_filtered strategy

Built after discovering (via live web search on Aug 16, 2026, checking
what actually happened Aug 14) that the real retail sales miss produced
almost no market reaction — S&P futures held flat, ±0.04%, through the
release. The original strategy's premise (spike, then trade the
direction it bases in) had nothing to trade that day, but would have
taken a low-conviction entry off pure noise anyway. The filtered variant
adds a minimum-surprise gate: measure the day's own pre-release noise,
require the post-release move to clear both an absolute floor and a
multiple of that noise, and stand down entirely (zero trades) if it
doesn't. Verified against both a real-spike scenario (still trades
normally) and a reconstruction of the actual flat Aug 14 session
(correctly takes zero trades).

## Multi-window backtesting and the optimizer

Built because a single day's (or single window's) backtest result isn't
enough to trust a strategy. `backtest-multi` runs one strategy across N
historical windows and reports consistency, not just totals. `optimize`
is grid search with an explicit train/test split — deliberately framed
in its own docstring as NOT machine learning, since overfitting risk is
real when there are only a handful of independent historical event days
to search over. Any candidate that's profitable on train but losing on
test gets flagged, not buried.

## What's actually been verified vs. what hasn't

**Verified, repeatedly, from fresh clones:** all 23 pytest tests, CLI
help/error paths, the API server's every endpoint, the simulated
provider's full account lifecycle, multi-day session resets — all
without needing real network access, by design (injectable data
functions in tests).

**NOT verified by the sandbox that built this** (no path to Yahoo
Finance or GitHub from there): real yfinance data pulls, real live-poll
behavior, real GitHub push. Grok did verify those once, against an
earlier commit (before the daily-reset fix and before
backtest-multi/optimize existed) — see `git log` for what's changed
since. The retail_sales_spike real-data backtest specifically should be
re-run now that the fix is in.

## Where things stand now

- Repo already exists and is pushed: `https://github.com/marius-patrik/moneymaker`
  (pushed by Grok in an earlier session — confirm `git remote -v` before
  assuming you need to create it).
- Confirm the repo's visibility (private was the intended default, per
  `AGENT_PROMPT.md`'s guardrails) — this was never explicitly confirmed.
- The daily-reset fix and doc updates are committed locally but their
  push status to GitHub depends on what happened after this document was
  written — check `git log origin/main..HEAD` (or equivalent) to see if
  anything local is still unpushed.

## Session: Claude Code takeover + full-window backtest + optimizer (2026-08-16)

Claude Code took over as ongoing owner. Work done this session:

**Doc conventions applied:** `AGENT_PROMPT.md` → `HANDOFF.md`, `PROJECT_HISTORY.md` →
`CONTEXT.md` (matching agents-superproject naming conventions). Updated artifact
(`moneymaker (1).zip`) brought in: `multiwindow.py`, `optimizer.py`,
`test_multiwindow_optimizer.py`; daily-reset fix in `strategy.py`; 23 tests pass.

**Real-data backtest confirmed (2026-06-18 → 2026-08-16, max 60-day 5m window):**
- `retail_sales_spike`: 40 trades, 32.5% win rate, -1,007.65 P&L
- `retail_sales_spike_filtered`: 0 trades with default threshold (0.15%)

**Spike-move diagnostic:** 40 days analyzed; median move 0.03%; only 3 of 40 days
exceed 0.15%. With 5m data, there is always exactly one baseline bar before 8:30,
so `pre_noise_pct` is always 0 — `min_surprise_ratio` is completely inert.

**Bug found and fixed:** `~/.moneymaker/strategies/retail_sales_spike_filtered.py`
was the pre-fix version (missing `reset_session_if_new_day`). Optimizer always saw
0 trades because day 1's `hard_exit_time` was never reset, blocking all later days.
Synced the updated file to fix. This reveals an architectural gap: the engine reads
drop-in strategies from `~/.moneymaker/strategies/`, not the repo's `strategies/`
directory — they can silently diverge. Worth consolidating or adding an auto-sync.

**Optimizer results (54-combo grid, train 2026-06-18:07-18, test 07-18:08-16):**
Best candidate: `min_spike_pct=0.0015, stop_pct=0.006` → 3 train trades, 0% win rate,
-187 P&L, 0 test trades. The filter reduces trade count but doesn't improve the
underlying R:R (avg loss > avg win at 32% hit rate). No profitable combination found.
The strategy's edge problem is structural, not a threshold-tuning problem.

**Open questions for future sessions:**
- Underlying R:R: the base strategy loses on 67% of days. Fix that first before
  optimizing the filter. Candidates: tighten entry timing, require stronger basing
  signal, or look for a different post-release entry condition entirely.
- Strategy/home sync: add a mechanism so `scripts/` strategies auto-sync to
  `~/.moneymaker/strategies/` at launch, or move drop-in loading to the repo dir.
- Stub providers: not yet implemented; decision to implement is always explicit.

## Ownership handoff

Starting from whenever you (the agent reading this) pick this up: you
are the ongoing owner of this project's technical decisions, not just
executor of one task. That includes implementing the stub providers
when asked, tuning strategy parameters, adding new strategies, making
architectural calls as the codebase grows — the same kind of judgment
this document's "why" sections show being exercised throughout the
project so far. Keep applying the same standards visible in this
history: test before claiming something works, verify from a fresh
clone before considering something shipped, flag bugs and design
quirks explicitly rather than silently patching or ignoring them, and
never wire up real-money trading as a side effect of something else —
that's always a separate, explicit, discussed decision.
