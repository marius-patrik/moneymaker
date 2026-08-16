# Questions

Open questions that don't need an immediate answer. Add freely during any
session. Resolve by answering inline + moving to "Resolved", or discard if
they become moot.

---

## Open

**Q3 — EconCalendar: series ID taxonomy**
P008 design is settled (FRED + BLS + simulated, CredentialStore, local cache,
general scope). Remaining sub-question: what is the canonical way for a strategy
to specify which release it cares about? Options:
- Strategy param: `fred_series_id="RSXFS"` (explicit, works today)
- Named alias: `release="us_retail_sales"` (engine maps to FRED/BLS IDs)
- Both (alias is sugar over series ID) — probably the right answer

**Q6 — P012 architecture: SignalStore vs MultiBarStrategy**
User confirmed P012 should be implemented. Two design options described in
PROPOSALS.md P012. Decision needed before implementation.

**Q7 — P013 default threshold**
`max_pre_range_pct` default for the pre-release volatility filter: 0.0020 (0.20%)?
Needs confirmation before implementing P013.

**Q8 — DataProvider interface**
For P014 (market data abstraction), what methods should `DataProvider` expose?
Minimum viable: `get_historical(ticker, start, end, interval) -> pd.DataFrame`.
Does it also need `get_last_price(ticker) -> (float, datetime)` for live mode?
And how does the `simulated` provider load its fixture data (CSV path param or
inline synthetic generation)?

---

## Resolved

**Q1 — GitHub repo visibility** _(Resolved 2026-08-16)_
`marius-patrik/moneymaker` is PRIVATE. Confirmed via `gh repo view`.

**Q2 — Strategy install: user-editable or system-managed?** _(Resolved 2026-08-16)_
Editable copies. Merge strategy is context-dependent: skip user-modified files,
report conflicts, let user decide per conflict. `--force` flag available for
full overwrite. Implemented in `engine/installer.py`.

**Q3 — release_dates calendar for data-release strategies** _(Partially resolved 2026-08-16)_
Design settled: FRED + BLS + simulated providers, same CredentialStore,
local cache under `~/.moneymaker/calendars/`, general EconCalendar scope.
Remaining sub-question moved to Q3 (series ID taxonomy) and Q8 (interface).

**Q4 — Volume in Bar: what's the scope?** _(Resolved 2026-08-16)_
Implemented as standalone change (P002): `Bar.volume: float = 0.0`;
`Simulator.run_backtest` passes `row.get("Volume", 0.0)`. No test breakage.

**Q5 — Trailing stop in momentum_continuation** _(Resolved 2026-08-16)_
Strategy-owned: `on_bar` checks if unrealized profit ≥ `trailing_activation_rr ×
init_stop_dist`, then advances `ctx.stop_price` using `trailing_stop_pct`.
No engine changes needed; consistent with the single-responsibility principle.
