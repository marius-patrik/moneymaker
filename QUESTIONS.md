# Questions

Open questions that don't need an immediate answer. Add freely during any
session. Resolve by answering inline + moving to "Resolved", or discard if
they become moot.

---

## Open

**Q1 — GitHub repo visibility**
Is `marius-patrik/moneymaker` private? Per HANDOFF.md guardrails it should be
private; never explicitly confirmed. Run `gh repo view marius-patrik/moneymaker
--json visibility` to verify.

**Q2 — Strategy install: user-editable or system-managed?**
When bundled strategies are installed to `~/.moneymaker/strategies/`, are they
intended to be edited freely by the user (editable copies), or should they be
treated as system-managed (hands-off, overwritten on upgrade)? The merge
mechanism in PROPOSALS.md P-INSTALL assumes editable-copy semantics, but
confirming this shapes the design.

**Q3 — release_dates calendar for data-release strategies**
If we add a `release_dates` parameter to `retail_sales_spike_filtered`, where
should the list come from? Options: (a) hard-coded list in the strategy file,
(b) user-provided CSV, (c) integration with a calendar API (FRED, Trading
Economics). Hard-coded is simplest; calendar API requires external dependency.

**Q4 — Volume in Bar: what's the scope?**
`vwap_reversion` needs `Bar.volume`. Extending Bar requires changes to the engine
(Simulator.run_backtest passes `row["Close"]` only), DataFeed (must pass
`row["Volume"]`), and any existing tests that construct synthetic Bars. Is this
worth doing as a standalone PR now, or wait until we're actually implementing
vwap_reversion?

**Q5 — Trailing stop in momentum_continuation**
The stub specifies a trailing stop "once 1:1 is reached." The engine's current
close-on-bar logic checks stop/target at each bar but doesn't move stops. What's
the preferred trailing-stop update mechanism — move stop in on_bar (strategy-owned),
or extend StrategyContext with a `trail_stop` flag the engine respects?

---

## Resolved

_(none yet)_
