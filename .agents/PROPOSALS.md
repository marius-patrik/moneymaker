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

**P005 — ctx.bars memory bound** `[adopted]`
`StrategyContext.max_bars: int = 0` (0 = unlimited). `Simulator.feed_bar` trims
`ctx.bars` to the last `max_bars` entries after each append. Strategies with
absolute-time lookbacks must set `max_bars` large enough to cover their window.
Default 0 preserves existing behavior.

**P006 — Dangling position at backtest end** `[adopted]`
`run_backtest` force-closes any open position at the last bar with
`exit_reason="end_of_data"` and logs the trade. Prevents silent data loss.

**P007 — Strategy param schema declaration** `[adopted]`
`Strategy.params()` classmethod introspects `__init__` via `inspect.signature`
and returns `{name: default}`. `Strategy.from_params(dict)` instantiates from
that dict, ignoring unknown keys. CLI uses both for `--param` injection and
`factory()` in multi-window backtest.

**P008 — Release-date calendar integration** `[adopted]`
`engine/econ_calendar.py`:
- `EconCalendar` ABC, `get_release_dates(start, end) -> list[date]`
- `FREDCalendar`: FRED vintage dates API; caches to `~/.moneymaker/calendars/`
  (1-day TTL); requires `fred.api_key` credential
- `BLSCalendar`: stub (raises NotImplementedError — no clean BLS vintage API)
- `SimulatedCalendar`: in-memory fixture for unit tests
- Named aliases (`us_retail_sales` → `fred:RSXFS`, etc.) + direct series IDs
- `get_calendar(alias_or_id, home)` factory
- Strategies: `calendar_series: str = ""` param on both spike strategies;
  if set, gate is checked once per session (cached in ctx.extra["is_release_day"]);
  fail-open if calendar unavailable so backtests run without API key

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

**P011 — Continuous rolling evaluation** `[adopted]`
`rolling_fork_eval()` in `engine/agents/forker.py` slides a window of
`window_days` forward by `step_days`, appends results to
`~/.moneymaker/evaluations/<strategy>_<ticker>_rolling.json`. Skips already-
evaluated windows on re-run. CLI: `fork-eval --rolling --rolling-start DATE
--rolling-end DATE --rolling-window DAYS --rolling-step DAYS`. New `rankings`
command reads all rolling eval files and prints score-trajectory table with
trend labels (improving/degrading/flat).

**P012 — Multi-symbol confirmation** `[adopted]`
`MultiBarStrategy` base class in `engine/strategy.py`:
- `tickers: list[str]` class var (first = primary)
- `on_secondary_bar(ctx, bar, ticker)` — default no-op; override to capture
  confirmation signals into `ctx.extra`
- `on_bar(ctx, bar)` still drives position management on primary ticker

`MultiBarSimulator` in `engine/engine.py`:
- Merges `{ticker: DataFrame}` event streams, sorted by timestamp
- Routes primary bars to `Simulator.feed_bar()`, secondary bars to
  `strategy.on_secondary_bar()`
- `run_backtest(data: dict[str, pd.DataFrame])` entry point

**P013 — Pre-release volatility filter** `[adopted]`
`max_pre_range_pct: float = 0.0` added to both `retail_sales_spike_filtered`
and `retail_sales_spike_fade`. Gate is part of the `signal_evaluated` validity
check. Default 0.0 = disabled (no behavior change); recommended value ~0.0020.
Logged to `ctx.extra["stand_down_reason"]` when triggered.

---

## Data ingestion

**P014 — Market data provider abstraction** `[adopted]`
`engine/data_providers/` package with:
- `DataProvider` ABC (`get_historical`, optional `get_last_price`)
- `YFinanceDataProvider`: wraps existing DataFeed, backward compatible
- `AlpacaDataProvider`: free US equity data via alpaca-py, disk cache
- `CSVDataProvider`: load history from local CSV or Parquet file
- `SimulatedDataProvider`: Brownian motion + fixture replay, no network needed
CLI: `--data-provider NAME` and `--data-provider-path PATH` on `backtest`,
`live`, and `backtest-multi`. `run_live` accepts `get_price_fn` param.

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
