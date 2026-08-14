# Agent handoff: test locally, then push to GitHub

This repo (`moneymaker`) was built and unit-tested in a sandbox with no
internet access to real market data or GitHub. Everything that could be
verified without network access has been (14 passing pytest tests, full
CLI and API server smoke-tested by hand). What's left needs your local
machine's real network access. Do the following, in order, and stop to
report back if any step fails rather than pushing broken code.

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
All 14 tests should pass. They don't touch the network. If any fail,
something about your Python version or environment differs from what
this was built against (Python 3.12) — investigate before continuing.

## 3. Verify real network access works (this is the part that couldn't
   be tested in the sandbox)

```bash
moneymaker strategies
moneymaker providers
moneymaker accounts create --name "smoke-test" --balance 10000
moneymaker accounts list

# Real historical data pull — confirms yfinance can actually reach Yahoo
# Finance from your network:
moneymaker backtest --strategy retail_sales_spike --ticker "ES=F" \
    --start 2026-07-01 --end 2026-08-01 --interval 5m
```
Confirm this runs without a network/connection error and produces a
session summary (win rate, P&L, etc. — the exact numbers don't matter,
what matters is that it completes without crashing). If it fails on the
data pull specifically, check that `ES=F` is a valid current Yahoo
Finance ticker (index futures contracts roll over — if it 404s, try
`^GSPC` instead and note that in your report).

## 4. Verify the live-paper path briefly (optional but recommended if
   it's currently market hours for the ticker you're testing)

```bash
moneymaker live --strategy retail_sales_spike --ticker "ES=F" \
    --end-time <a few minutes from now> --poll-seconds 15
```
Let it run for a minute or two, confirm it polls without erroring, then
Ctrl+C. This isn't expected to produce a trade (that depends on the
strategy's specific entry conditions and real-time price action) — the
goal is just confirming the live polling loop and price fetch work.

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
git status   # should already be an initialized repo with an initial commit
gh auth status   # confirm you're authenticated; if not, run `gh auth login` first
gh repo create moneymaker --private --source=. --remote=origin --push
```
(Use `--public` instead of `--private` if that's the intent — check with
the user first if it isn't obvious which they want.)

If `gh` isn't available, do it manually instead:
```bash
git remote add origin <URL of a new, empty repo you create on github.com>
git branch -M main
git push -u origin main
```

## 7. Report back

Tell the user:
- Whether the real-data backtest and live-poll worked, and with what
  ticker (note if you had to substitute one).
- The final GitHub repo URL.
- Anything you had to fix along the way that wasn't already covered by
  the test suite — that's a gap worth patching in the tests themselves
  for next time.

## Guardrails while you do this

- Do not implement or wire up any of the stub providers
  (`trading212_demo`, `ibkr_paper`, `oanda_practice`) as part of this
  task unless explicitly asked — they're deliberately left unimplemented,
  and none of them should ever place a real-money order without a
  separate, explicit decision to do so.
- Do not commit `credentials.json` or any file containing a real API
  key/token/secret. `.gitignore` already excludes the usual suspects —
  double check `git status` before committing anything new.
- If `pytest` fails after your changes, fix it before pushing — don't
  push on a red test suite.
