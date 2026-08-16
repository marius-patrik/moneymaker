# Proposals

Engine improvement proposals spotted during code review. Each needs discussion
before implementation — do not adopt as a side effect of another task.

Status tags: `[proposed]` `[adopted]` `[rejected]` `[deferred]`

---

## Engine / core

**P001 — CLI strategy param injection** `[proposed]`
Currently all strategies are instantiated with defaults from the CLI; there's no
way to pass `min_spike_pct=0.001` without editing a Python file. Proposal: add
`--param key=value` (repeatable) to `backtest`, `live`, and `live-paper` commands
that feeds kwargs into the strategy constructor. Requires strategies to declare
their param types (or we parse best-effort). Moderate complexity; high day-to-day
usefulness. Blocks cleaner parameterized backtesting from the shell.

**P002 — Volume field in Bar** `[proposed]`
`vwap_reversion` (and any volume-based filter) needs `Bar.volume`. Currently Bar
only carries `time` and `price`. Extending: add `volume: float = 0.0` to Bar;
update `Simulator.run_backtest` to pass `row.get("Volume", 0.0)`; update DataFeed
to ensure Volume is preserved in parquet. Existing synthetic-Bar tests still work
(volume defaults to 0). Low risk, isolated change. Unblock VWAP stub implementation.

**P003 — Bar deduplication in live mode** `[proposed]`
`run_live` can feed the same bar twice if yfinance returns the same timestamp on
consecutive polls (e.g. polling at 30s intervals on 5m bars). Proposal: track
`last_bar_time` in Simulator; skip any bar whose time ≤ last_bar_time. Simple
guard, prevents double-counting. Affects live mode only; no backtest impact.

**P004 — DataFeed cache TTL** `[proposed]`
`DataFeed.get_historical` caches indefinitely to parquet. An intraday cache from
60+ days ago is beyond the yfinance 60-day limit anyway (the data is frozen, not
extending). But a cache from 1 day ago may be stale for today's trailing bars.
Proposal: if `use_cache=True` and the cache file is >N hours old AND the requested
end date is today-or-later, invalidate and re-fetch. Simple `os.path.getmtime`
check. Prevents silently stale intraday data when running live-paper daily.

**P005 — ctx.bars memory bound** `[proposed]`
`StrategyContext.bars` accumulates all bars across a multi-day backtest. For 60
days of 5m data that's ~4,800 bars — manageable now, but strategies doing O(N)
scans on every bar (baseline window, spike window) are O(N²) across the session.
Proposal: add a `max_bars` param (default 0 = unlimited) to StrategyContext, or
document that strategies should use relative lookbacks and prune `ctx.bars` if
they need the guarantee. Low priority until backtests get slower.

**P006 — Dangling position at backtest end** `[proposed]`
If the last bar of a backtest doesn't trigger a close (no stop/target/timebox hit),
the position is silently open at session end and never logged. Proposal: in
`run_backtest`, after the bar loop, if `ctx.position_open`, force-close at the
last bar price and log with `exit_reason="end_of_data"`. Prevents silent data loss.

**P007 — Strategy param schema declaration** `[proposed]`
Strategies don't declare their constructor parameters in a machine-readable way.
This makes the optimizer `param_grid` a manual exercise (you have to know the
param names). Proposal: optional `params()` classmethod that returns
`{name: {type, default, description}}`. CLI `strategies` could display it; CLI
`optimize` could validate param names against it. No runtime requirement to
implement it — strategies that don't declare params just skip validation.

**P008 — Release-date calendar integration** `[proposed]`
`retail_sales_spike_filtered` fires every day on noise. Proposal A (simple): add
a `release_dates: list[dt.date]` param; if provided, skip sessions not on the
list. Proposal B (smarter): integrate with a public economic calendar API (FRED,
Trading Economics) to auto-populate release dates. Proposal A is low-dependency
and sufficient. Proposal B is more powerful but adds an external data dependency.
See QUESTIONS.md Q3.

**P008a — Spike-fade direction (counter-spike entry)** `[proposed]`
Empirical finding (2026-08-16): on actual large-release days (spike ≥ 0.10%), the
breakout-continuation approach gets 0% win rate. All 6 qualifying release-day
trades were losers because the initial spike faded — the market overshot and
reverted. Proposal: for large spikes, FADE the direction (enter against the spike)
instead of continuing it.

Entry logic change: when `spike_move_pct >= large_spike_threshold`, reverse the
expected direction: a large up-spike → enter SHORT after the basing (fading the
run-up); a large down-spike → enter LONG (buying the dip). Rationale: ES prices in
macro surprises within 1–2 bars; the basing window represents the overshooting
reaction cooling off; the trade fades back toward pre-release fair value.

This would be a new strategy (`retail_sales_spike_fade`) rather than a parameter on
the existing one — the semantics are different enough to warrant a separate class.
See CONTEXT.md session 2026-08-16 for the backtest evidence.

**P009 — Walk-forward window auto-generation** `[proposed]`
The `optimize` command requires manually specifying `--train-windows` and
`--test-windows` as date strings. Proposal: add a `--walk-forward N` mode that
automatically splits the full `--start`/`--end` range into N equal folds, using
the first N-1 as train and the last as test. Makes walk-forward validation
reachable from a single command rather than requiring manual date arithmetic.

**P010 — Open-position pnl in session summary** `[proposed]`
`logger.summary()` reports only closed trades. If a position is open when the
session ends (dangling), the summary looks like the last trade never happened.
Proposal: include a separate `open_pnl` key in summary (unrealized P&L of any
open position at the last bar price). Related to P006.

---

## Install / packaging

**P-INSTALL — Strategy install + merge mechanism** `[proposed]`
Currently bundled strategies are loaded live from the repo's `strategies/` dir.
This breaks in a pip-installed (non-editable) scenario. Proposal:

1. Move bundled strategies into `moneymaker/bundled/` as package data
   (declared in pyproject.toml `[tool.setuptools.package-data]`).
2. Add `moneymaker install` command: on first run (or explicit call), copies
   bundled strategies to `~/.moneymaker/strategies/` and records hashes in
   `~/.moneymaker/.strategy_manifest.json`.
3. Add `moneymaker upgrade-strategies`: re-copies updated bundled strategies to
   home, skipping files whose current hash ≠ installed hash (user-modified).
   Reports any skipped files.
4. `load_strategies` loads from `~/.moneymaker/strategies/` only (no repo-dir
   scanning needed after install).

Design question: see QUESTIONS.md Q2 (user-editable vs system-managed semantics).

**P-VERSION — Version tracking + upgrade command** `[proposed]`
No version is tracked in the home dir; upgrading the package doesn't trigger any
migration or strategy sync. Proposal:

1. Write current `moneymaker.__version__` to `~/.moneymaker/version` on every
   `get_home()` call.
2. If the version on disk differs from the running version, print a warning and
   run any registered migration functions.
3. Add `moneymaker upgrade` command: runs `pip install --upgrade
   git+https://github.com/marius-patrik/moneymaker.git`, then calls
   `upgrade-strategies`.
