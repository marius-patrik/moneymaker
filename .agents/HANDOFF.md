# Agent handoff: test locally, push to GitHub, then take over the project

## Read PROJECT_HISTORY.md first — this is not optional

Before doing anything else, read `PROJECT_HISTORY.md` in this repo's
root. It's the full context of how and why this project was built —
design decisions, two real bugs that were found and fixed (one of which
you should specifically re-verify, see below), what's been tested and
what hasn't. It exists because you can't read the conversation that
produced this repo, only files. Skipping it means re-learning things the
hard way that are already written down.

## You now own this project going forward — not just this one task

This prompt was originally written for a single verify-and-push handoff.
That scope has changed: **you are now the ongoing owner of this
project's technical decisions** — implementing the stub providers when
asked, tuning strategy parameters, adding new strategies, making
architectural calls as it grows. Not just executing this one checklist
and stopping. Keep applying the same standards visible in
`PROJECT_HISTORY.md`: test before claiming something works, verify from
a fresh clone before considering something shipped, flag bugs and design
quirks explicitly instead of silently patching or ignoring them, and
never wire up real-money trading as a side effect of something else —
that's always a separate, explicit, discussed decision with the person
you're working for, not something you do unilaterally.

This particular handoff is happening as a complete takeover — there's no
report expected back into a chat this time (see the note on the final
report section below, which still applies for your own logging/audit
trail even though nobody's waiting to read it).

**If this repo has already been pushed to GitHub before** (check `git
remote -v` — if `origin` is already set, this is a follow-up update, not
a first push): pull first if there's a remote history to reconcile,
apply the same steps below, then `git push` to the existing remote
instead of running `gh repo create` again.

You are a local coding agent with real network access. This repo
(`moneymaker`) was built and unit-tested in a sandbox with NO internet
access to real market data or GitHub. Everything that could be verified
without network access has been (23 passing pytest tests, full CLI and
API server smoke-tested by hand). What's left needs your local machine's
real network access.

Work through the steps below in order. Do not skip ahead if a step fails —
investigate and fix it, or stop and report the failure honestly rather
than pushing broken code.

## 1. Set up the environment

```bash
cd moneymaker
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## 2. Run the existing test suite (should already pass, sanity check)

```bash
pytest -v
```
All 23 tests should pass. They don't touch the network. If any fail,
something about your Python version or environment differs from what
this was built against (Python 3.12) — investigate before continuing,
and note what you found in your final report.

## 3. Verify real network access works (this is the part that couldn't
   be tested in the sandbox that built this repo)

```bash
moneymaker strategies
moneymaker providers
moneymaker accounts create --name "smoke-test" --balance 10000
moneymaker accounts list

# Real historical data pull — confirms yfinance can actually reach Yahoo
# Finance from your network:
moneymaker backtest --strategy retail_sales_spike --ticker "ES=F" \
    --start 2026-07-01 --end 2026-08-01 --interval 5m

# Also run the filtered variant against the same window, for comparison:
moneymaker backtest --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --start 2026-07-01 --end 2026-08-01 --interval 5m
```
Confirm both run without a network/connection error and each produces a
session summary. Record the actual numbers (trades taken, win rate,
total P&L) for both — these go in your final report. If it fails on the
data pull specifically, check that `ES=F` is a valid current Yahoo
Finance ticker (index futures contracts roll over — if it 404s, try
`^GSPC` instead and note the substitution).

## 4. Verify multi-window backtesting and optimization against real data

```bash
# Multiple real historical windows in one run:
moneymaker backtest-multi --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --windows "2026-06-15:2026-06-30,2026-07-01:2026-07-15,2026-07-15:2026-07-31" \
    --interval 5m

# Small grid search with a held-out test window:
moneymaker optimize --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --param-grid '{"stop_pct": [0.003, 0.0045, 0.006], "min_surprise_ratio": [1.5, 2.0]}' \
    --train-windows "2026-06-01:2026-07-01" \
    --test-windows "2026-07-01:2026-08-01" \
    --top 3
```
Record the actual output (per-window trades/P&L, and the top optimizer
candidates with their train vs test numbers) in your final report. If
`optimize` flags any candidate as overfit (profitable train, losing test),
note that explicitly rather than omitting it.

## 5. Verify the live-paper path briefly (optional but recommended if
   it's currently market hours for the ticker you're testing)

```bash
moneymaker live --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --end-time <a few minutes from now> --poll-seconds 15
```
Let it run for a minute or two, confirm it polls without erroring, then
Ctrl+C. This isn't expected to produce a trade — the goal is just
confirming the live polling loop and price fetch work against real data.

## 6. Verify the API server

```bash
moneymaker server --port 8787 &
curl http://127.0.0.1:8787/strategies
curl http://127.0.0.1:8787/providers
curl -X POST http://127.0.0.1:8787/accounts -d '{"name":"api-smoke","starting_balance":10000}'
curl http://127.0.0.1:8787/accounts
kill %1
```
Confirm each returns sensible JSON, not an error.

## 7. If everything above passes: create the GitHub repo and push

```bash
git status   # should already be an initialized repo with commits
gh auth status   # confirm you're authenticated; if not, run `gh auth login` first
gh repo create moneymaker --private --source=. --remote=origin --push
```
Use `--private` unless you have explicit instruction otherwise — default
to private for anything touching trading code and account/credential
handling, even paper-only.

If `gh` isn't available, do it manually instead:
```bash
git remote add origin <URL of a new, empty repo you create on github.com>
git branch -M main
git push -u origin main
```

## Guardrails while you do this

- Do not implement or wire up any of the stub providers
  (`trading212_demo`, `ibkr_paper`, `oanda_practice`) as part of this
  task unless explicitly asked — they're deliberately left unimplemented,
  and none of them should ever place a real-money order without a
  separate, explicit decision made outside of this handoff.
- Do not commit `credentials.json` or any file containing a real API
  key/token/secret. `.gitignore` already excludes the usual suspects —
  double check `git status` before committing anything new.
- If `pytest` fails after any change you make, fix it before pushing —
  don't push on a red test suite.
- If you have to make a nontrivial code change (not just a config/env
  fix) to get something working, keep it minimal and say exactly what
  you changed and why in the final report — don't silently rewrite
  strategy logic or risk/account handling.

## 8. Log — write this to a file, no chat report needed this time

This handoff is a complete takeover, not a round-trip to a chat
conversation — nobody is waiting to read a pasted-back report. Still
write the block below, but to a file (e.g. `HANDOFF_LOG_<date>.md` in
the repo root, or append to a running log — your call) rather than as a
final chat message. It's your own audit trail and the next person/agent
touching this project will benefit from it existing, the same way
`PROJECT_HISTORY.md` benefited you. Keep it plain and factual.

```
MONEYMAKER HANDOFF REPORT
==========================
Environment: <OS, Python version>
Test suite: <PASS/FAIL> — <N>/<N> tests passed
  <if any failed: which ones, and why>

Real-data backtest (retail_sales_spike, ES=F, 2026-07-01 to 2026-08-01):
  Ticker used: <ES=F or substitute, note if substituted and why>
  Trades: <N>  Win rate: <X%>  Total P&L: <±X>
  (Note: prior to the per-day session reset fix, multi-day backtests
  could only ever take one trade total regardless of range. If you're
  re-running this after that fix, the trade count should now scale
  with the number of days that actually produce a valid setup.)

Real-data backtest (retail_sales_spike_filtered, same window):
  Trades: <N>  Win rate: <X%>  Total P&L: <±X>

Multi-window backtest (retail_sales_spike_filtered, 3 windows June-July):
  <per-window: trades, win rate, P&L, or ERROR>
  Aggregate: <total trades>  <% windows profitable>  <total P&L>

Optimizer (retail_sales_spike_filtered, small grid, train June / test July):
  Top candidate params: <the winning param dict>
  Train: <trades, win rate, P&L>   Test: <trades, win rate, P&L>
  Overfit warning triggered: <YES — details / NO>

Live-paper poll test: <RAN CLEANLY / ERRORED — details> or <SKIPPED — why>

API server check: <ALL ENDPOINTS OK / ISSUES — details>

Code changes made (if any): <NONE, or exact diff/description + reason>

GitHub push: <SUCCESS — repo URL> or <FAILED — reason>

Other issues encountered: <NONE, or list>
==========================
```
