# Agent handoff: test locally, then push to GitHub

You are a local coding agent (this was written for you regardless of which
model/tool you are — Gemini, Claude Code, or otherwise) with real network
access. This repo (`moneymaker`) was built and unit-tested in a sandbox
with NO internet access to real market data or GitHub. Everything that
could be verified without network access has been (16 passing pytest
tests, full CLI and API server smoke-tested by hand). What's left needs
your local machine's real network access.

Work through the steps below in order. Do not skip ahead if a step fails —
investigate and fix it, or stop and report the failure honestly rather
than pushing broken code. At the very end, produce the structured final
report described in the last section — that report will be pasted back
into a conversation with a different AI assistant, so its accuracy and
completeness matter more than how it reads.

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
All 16 tests should pass. They don't touch the network. If any fail,
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

## 4. Verify the live-paper path briefly (optional but recommended if
   it's currently market hours for the ticker you're testing)

```bash
moneymaker live --strategy retail_sales_spike_filtered --ticker "ES=F" \
    --end-time <a few minutes from now> --poll-seconds 15
```
Let it run for a minute or two, confirm it polls without erroring, then
Ctrl+C. This isn't expected to produce a trade — the goal is just
confirming the live polling loop and price fetch work against real data.

## 5. Verify the API server

```bash
moneymaker server --port 8787 &
curl http://127.0.0.1:8787/strategies
curl http://127.0.0.1:8787/providers
curl -X POST http://127.0.0.1:8787/accounts -d '{"name":"api-smoke","starting_balance":10000}'
curl http://127.0.0.1:8787/accounts
kill %1
```
Confirm each returns sensible JSON, not an error.

## 6. If everything above passes: create the GitHub repo and push

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

## 7. Final report — produce EXACTLY this, nothing more, nothing less

When you're done, output ONE final message containing only the block
below, with every placeholder filled in from what you actually observed.
Do not add narrative before or after it. This block is meant to be
pasted verbatim into a conversation with another AI assistant, so keep
it plain, factual, and complete — no marketing language, no hedging
where you actually know the answer.

```
MONEYMAKER HANDOFF REPORT
==========================
Environment: <OS, Python version>
Test suite: <PASS/FAIL> — <N>/<N> tests passed
  <if any failed: which ones, and why>

Real-data backtest (retail_sales_spike, ES=F, 2026-07-01 to 2026-08-01):
  Ticker used: <ES=F or substitute, note if substituted and why>
  Trades: <N>  Win rate: <X%>  Total P&L: <±X>

Real-data backtest (retail_sales_spike_filtered, same window):
  Trades: <N>  Win rate: <X%>  Total P&L: <±X>

Live-paper poll test: <RAN CLEANLY / ERRORED — details> or <SKIPPED — why>

API server check: <ALL ENDPOINTS OK / ISSUES — details>

Code changes made (if any): <NONE, or exact diff/description + reason>

GitHub push: <SUCCESS — repo URL> or <FAILED — reason>

Other issues encountered: <NONE, or list>
==========================
```
