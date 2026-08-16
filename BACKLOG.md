# Backlog

Items grouped by type. Planned = agreed direction but not started.
In-progress items live in CONTEXT.md's current session section.

---

## Strategy improvements

### retail_sales_spike_filtered — R:R fix (DONE 2026-08-16)
Switched from fixed-% stop to basing-range stop + breakout entry.
Stop distance now ≈ 3–5 pts (basing range width + buffer) vs prior 34 pts.
Target set at 2:1 R:R relative to stop distance.

### Stub strategies to implement
- `momentum_continuation` — follow spike direction on large surprises;
  needs min_spike_pct calibration and trailing stop logic
- `opening_range_breakout` — daily ORB at 9:30 ET; evaluate 5/15/30m windows
- `vwap_reversion` — requires volume data; engine Bar class needs extending

### Other strategy ideas (no stub yet)
- **News-sentiment overlay**: use a real-time news API to weight entry direction
  based on sentiment of the release headline (requires external data feed)
- **Multi-symbol confirmation**: only enter ES trade if NQ or RTY is moving
  in the same direction (reduces solo-instrument false signals)
- **Pre-release volatility filter**: skip sessions where 30-min pre-release
  volatility is already elevated (suggesting the market already moved)

---

## Engine / infrastructure

### Strategy/home sync gap (found 2026-08-16)
`load_strategies` now scans the repo's `strategies/` dir first, then
`~/.moneymaker/strategies/`. The divergence bug is fixed, but the
`~/.moneymaker/strategies/` drop-in dir is now effectively redundant for
bundled strategies — consider deprecating it or making it explicit-override-only.

### Volume support in Bar
`vwap_reversion` and any volume-based filter need the `Bar` dataclass to carry
volume. Current Bar only has `time` and `price`. Extending it requires changes
to the engine, Simulator, and data fetcher.

### Stub provider implementation
Three broker stubs (`trading212_demo`, `ibkr_paper`, `oanda_practice`) need
real API calls wired. Decision to implement ANY of these is always a separate,
explicit discussion — never done as a side effect of another task.

### Live data feed beyond yfinance
yfinance is best-effort / 15-second delayed. For a real live-paper setup,
need a direct broker WebSocket feed or a paid data provider (Polygon.io, etc.).
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
- Longer-term: a "strategy compiler" that takes a high-level description
  ("fade sharp morning spikes on data releases") and outputs parameterized
  Python Strategy subclasses ready for backtesting.

---

## Operational

### GitHub repo visibility confirmation
Grok created the repo as private (per HANDOFF.md guardrails). Never explicitly
confirmed. Run `gh repo view marius-patrik/moneymaker --json visibility` to verify.

### CI / automated testing
No CI pipeline. All 23 tests run locally. Consider adding a GitHub Actions
workflow that runs `pytest` on every push to master.
