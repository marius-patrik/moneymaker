# Proposals

Engine improvement proposals spotted during code review. Each needs discussion
before implementation — do not adopt as a side effect of another task.

Status tags: `[proposed]` `[adopted]` `[rejected]` `[deferred]`

---

## Engine / core

**P001 — CLI strategy param injection** `[adopted]`
`--param key=value` (repeatable) wired to `backtest`, `live`, and `backtest-multi`
commands. Implemented in `engine/cli.py` via `_parse_param_overrides()`, which
infers types from the strategy's `__init__` signature defaults.

**P002 — Volume field in Bar** `[adopted]`
`Bar.volume: float = 0.0` added to the dataclass. `Simulator.run_backtest` passes
`row.get("Volume", 0.0)`; existing synthetic-Bar tests unaffected (default = 0).

**P003 — Bar deduplication in live mode** `[adopted]`
`Simulator.feed_bar(deduplicate=True)` guards `last_bar_time`; `run_live` passes
`deduplicate=True`. Prevents double-counting on repeated yfinance polls.

**P004 — DataFeed cache TTL** `[adopted]`
`get_historical` checks mtime: if `end < today`, cache is frozen and always valid;
if `end >= today`, invalidate after `cache_ttl_seconds` (default 1 hour).
Prevents stale intraday data in daily live-paper runs.

**P005 — ctx.bars memory bound** `[deferred]`
No ring buffer will be implemented. Instead, document the O(N²) scanning risk:
strategies that do O(N) scans over `ctx.bars` per bar are O(N²) total across
a long multi-day backtest (~4 800 bars for 60 days × 5m). Current backtests are
fast enough; if they slow down, add a `max_bars` param then.
_Action: add a one-line warning comment to StrategyContext.bars, close proposal._

**P006 — Dangling position at backtest end** `[adopted]`
`run_backtest` force-closes any open position at the last bar with
`exit_reason="end_of_data"` and logs the trade. Prevents silent data loss.

**P007 — Strategy param schema declaration** `[adopted]`
`Strategy.params()` classmethod introspects `__init__` via `inspect.signature`
and returns `{name: default}`. `Strategy.from_params(dict)` instantiates from
that dict, ignoring unknown keys. CLI uses both for `--param` injection and
`factory()` in multi-window backtest.

**P008 — Release-date calendar integration** `[proposed]`
Design decisions confirmed (2026-08-16):
- Data sources: FRED API + BLS public API + simulated (hardcoded list for testing)
- Auth: same `credentials set` / `CredentialStore` system as execution providers
- Caching: schedule cached locally under `~/.moneymaker/calendars/`; refreshed
  once per day for current/future dates, frozen for past dates
- Scope: general `EconCalendar` service usable by any strategy (not just
  retail_sales) — strategies pass a `fred_series_id` or `bls_series_id` param

_Still open: CLI integration (`--data-provider` flag or injected via strategy param?),
series ID taxonomy, fallback behavior when FRED/BLS are unreachable._

**P008a — Spike-fade direction (counter-spike entry)** `[adopted]`
`strategies/retail_sales_spike_fade.py` fully implemented as a separate strategy
class (`FadeDataReleaseStrategy`). Includes `min_retracement_pct` and
`max_stop_dist_pct` filters; `target_rr=0` uses baseline as take-profit.
FORKS on `retail_sales_spike_fade` compare fade variants + continuation.

**P009 — Walk-forward window auto-generation** `[adopted]`
`--walk-forward N --wf-start DATE --wf-end DATE` added to `backtest-multi`.
Splits the range into N equal windows; last window snaps to `wf-end` to avoid
rounding drift. Alternative to manual `--windows`.

**P010 — Open-position pnl in session summary** `[adopted]`
`TradeLogger.summary(open_pnl=...)` and `print_summary(open_pnl=...)` accept an
optional float for unrealized P&L. `run_live` passes last bar price at session
end; `status()` API includes `"open_pnl"` key.

---

## Strategy research

**P011 — Continuous rolling evaluation** `[proposed]`
User confirmed: definitely implement. Design:
- `--rolling` flag on `fork-eval`; `--retrain-every N` on `evolve`
- Results stored in `~/.moneymaker/evaluations/<strategy>_rolling.json`
- `rankings` CLI command reads all evaluation files, prints score-trajectory table
_Next: implement in engine/agents/forker.py + CLI wiring._

**P012 — Multi-symbol confirmation** `[proposed]`
User confirmed: implement. Architecture choice still open:
- **Option A (SignalStore)**: shared dict keyed by `(ticker, signal_name)`;
  strategies write/read without engine changes. Simple, no new abstractions.
- **Option B (MultiBarStrategy)**: new base class that registers multiple tickers;
  engine feeds all bar streams to it. Cleaner but more engine surgery.
_Decision needed before implementation._

**P013 — Pre-release volatility filter** `[proposed]`
User confirmed: implement. Add `max_pre_range_pct` gate to both
`retail_sales_spike_filtered` and `retail_sales_spike_fade`. If the pre-release
baseline window is noisier than the threshold, stand down for the session.
Default `max_pre_range_pct = 0.0020` (0.20%) — needs confirmation.

---

## Data ingestion

**P014 — Market data provider abstraction** `[proposed]`
New feature (2026-08-16). Separate from execution providers.

Design decisions confirmed:
- Providers: `yfinance` (keep existing), `fred` (FRED API), `bls` (BLS public API),
  `simulated` (replay hardcoded/CSV data for unit tests and dry runs)
- Auth: `CredentialStore` (same system as execution providers)
- Caching: parquet under `~/.moneymaker/data/`; TTL already handled by P004
- Scope: general; CLI gets `--data-provider` flag on `backtest` / `live` / `backtest-multi`

_Still open: DataProvider interface spec (what methods?), how simulated provider
loads its data (CSV path param? inline fixture?), error handling for missing API keys._

---

## Install / packaging

**P-INSTALL — Strategy install + merge mechanism** `[adopted]`
Implemented in `engine/installer.py`. Bundled strategies in `moneymaker/bundled/`
(package data). `install-strategies` copies to `~/.moneymaker/strategies/`;
`upgrade-strategies` skips user-modified files (hash check), reports conflicts.

**P-VERSION — Version tracking + upgrade command** `[adopted]`
`moneymaker upgrade` command implemented. Runs pip upgrade + strategy sync.

---

## Resolved / rejected

_(P001–P010, P008a, P-INSTALL, P-VERSION moved to [adopted] above)_
