# Questions

Open questions that don't need an immediate answer. Add freely during any
session. Resolve by answering inline + moving to "Resolved", or discard if
they become moot.

---

## Open

_(none currently open)_

---

## Resolved

**Q1 — GitHub repo visibility** _(Resolved 2026-08-16)_
`marius-patrik/moneymaker` is PRIVATE. Confirmed via `gh repo view`.

**Q2 — Strategy install: user-editable or system-managed?** _(Resolved 2026-08-16)_
Editable copies. Merge strategy is context-dependent: skip user-modified files,
report conflicts, let user decide per conflict. `--force` flag available for
full overwrite. Implemented in `src/installer.py`.

**Q3 — EconCalendar: series ID taxonomy** _(Resolved 2026-08-16)_
Both approaches implemented: direct series IDs (e.g. "RSXFS") and named aliases
(e.g. "us_retail_sales"). Alias table in `src/econ_calendar.py` covers the
main US releases (retail sales, CPI, PCE, NFP, unemployment, GDP, ISM, housing).

**Q4 — Volume in Bar: what's the scope?** _(Resolved 2026-08-16)_
Implemented as P002: `Bar.volume: float = 0.0`. `Simulator.run_backtest`
passes `row.get("Volume", 0.0)`. No test breakage (volume defaults to 0).

**Q5 — Trailing stop in momentum_continuation** _(Resolved 2026-08-16)_
Strategy-owned: `on_bar` checks if unrealized profit ≥ `trailing_activation_rr ×
init_stop_dist`, then advances `ctx.stop_price` using `trailing_stop_pct`.
No engine changes needed.

**Q6 — P012 architecture: SignalStore vs MultiBarStrategy** _(Resolved 2026-08-16)_
Option B: `MultiBarStrategy` base class. Implemented in `src/strategy.py`
and `src/engine.py`. Strategies declare `tickers` list and implement
`on_secondary_bar(ctx, bar, ticker)`.

**Q7 — P013 default volatility threshold** _(Resolved 2026-08-16)_
`max_pre_range_pct = 0.0` (disabled by default). Setting to ~0.0020 (0.20%)
is a reasonable starting point; user can tune via `--param` or FORKS.

**Q8 — DataProvider interface** _(Resolved 2026-08-16)_
`DataProvider` ABC exposes: `get_historical(ticker, start, end, interval) ->
pd.DataFrame` (required) and `get_last_price(ticker) -> (float, datetime)`
(optional, raises NotImplementedError for batch-only providers like CSV).
`is_live: bool` flag indicates live-price support. See `src/data_providers/base.py`.
