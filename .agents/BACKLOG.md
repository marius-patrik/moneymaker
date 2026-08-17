# Backlog

Items grouped by type. Planned = agreed direction but not started.
In-progress items live in CONTEXT.md's current session section.

---

## Strategy improvements

### Other strategy ideas
- **News-sentiment overlay**: use a real-time news API to weight entry direction
  based on sentiment of the release headline (requires external data feed)
- **ES/NQ confirmation strategy**: concrete implementation of MultiBarStrategy
  for the ES entry + NQ confirmation use case

---

## Engine / infrastructure

### Stub provider implementation
Three broker stubs (`trading212_demo`, `ibkr_paper`, `oanda_practice`) need
real API calls wired. Decision to implement ANY of these is always a separate,
explicit discussion — never done as a side effect of another task.

### Live data feed beyond yfinance
yfinance is best-effort / 15-second delayed. Alpaca is now available as a data
provider for US equities. For futures (ES=F, GC=F), a dedicated futures data
feed (Rithmic, CQG, IB TWS) is needed for real-money live mode.
Currently acceptable for strategy development; not acceptable for real-money.

---

## Intelligence layer

### [PLANNED] ML strategy evolution engine
Automated strategy parameter search beyond grid search:
- **Bayesian optimization** (e.g., Optuna): smarter than grid search; models
  the objective function and proposes parameter combos that are likely to improve
  it, rather than trying all combinations exhaustively.
- **Genetic / evolutionary algorithms**: evolve a population of strategy
  configurations across generations, selecting for robustness across multiple
  windows rather than a single score.
- **Walk-forward validation**: required companion to any ML search — train on
  window N, test on window N+1, repeat. A parameter set that's robust across
  all walk-forward folds is far more trustworthy than one optimized on a single
  held-out window.
- Key constraint: with only ~12 independent monthly data release events per year
  for any given release, sample size is tiny. Overfitting is near-certain with
  more than 2–3 free parameters. Any ML search must penalize complexity
  (fewer parameters = better, all else equal).
- Suggested first implementation: Optuna study wrapping the existing
  `run_multi_window_backtest` as the objective, with walk-forward splits and
  a pruner that kills trials early if the first window is strongly negative.

### [PLANNED] Deterministic strategy finding engine
Systematic rule enumeration across historical data:
- Define a vocabulary of atomic signal predicates (price > VWAP, spread vs
  yesterday's close > X%, consecutive up-closes ≥ N, etc.) and entry/exit
  rules (stop at N%, target at M%, time-box at T).
- Enumerate combinations of predicates and rules, backtest each, filter for
  statistical significance.
- The hard problem: with 60 days of 5m data, the number of bars is large but
  the number of INDEPENDENT trade opportunities is small (~40 for a daily
  data-release strategy). Any rule that produces fewer than 20 trades should
  be treated as statistically uninterpretable regardless of reported win rate.
- Suggested approach: enumerate predicate combinations, run them through the
  existing `grid_search` / `run_multi_window_backtest` machinery with
  walk-forward splits, and only surface rules where the test-window P&L is
  positive AND the 95% CI of per-trade P&L excludes zero (bootstrap resampling
  of the trades, not the bars).

---

## Operational

### GitHub repo visibility — CONFIRMED PRIVATE (2026-08-16)
Confirmed via `gh repo view marius-patrik/moneymaker --json visibility`.

### CI / automated testing — ACTIVE (2026-08-16)
GitHub Actions workflow at `.github/workflows/ci.yml`. Runs `pytest` on every
push. 45 tests pass on ubuntu-latest, Python 3.11 and 3.12.
