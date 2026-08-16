# Deferred

Items explicitly deferred — not forgotten, not abandoned.
Each entry must state *why* it's deferred and *what would trigger revisiting it*.

---

## Full harness integration

Agents will eventually operate inside a full integrated harness (scheduling,
alerting, cross-strategy coordination, resource budgets). Deferred until the
engine's strategy/fork/evolution layer is stable and delivering useful signal.

**Trigger:** engine produces a consistently profitable strategy after fork-eval
and evolution cycles, and agent tooling needs coordination beyond what a single
CLI invocation provides.

---

## TUI

A terminal user interface for monitoring live-paper runs and reviewing backtest
results interactively. Deferred — no human is expected to operate the system
directly in practice; agent tooling covers the use cases.

**Trigger:** explicit user request to build the TUI, or a use case that genuinely
can't be handled via CLI + JSON output.

---

## Web UI

Browser-based interface for the engine and harness. Same rationale as TUI.

**Trigger:** explicit user request, or harness is live and stakeholder needs
a dashboard that isn't a terminal.

---

## Versioned asymmetric interaction network for strategies

Treat strategies not as independent units but as nodes in a versioned interaction
network: strategies observe each other's outputs, votes, or confidence signals,
and the network topology determines how individual signals combine into a final
position decision. "Asymmetric" because the interaction weights don't need to be
symmetric — a fade strategy might discount the continuation strategy's signal
more than vice versa, based on historical correlation.

This is the right frame for the long-run architecture but requires:
(a) a working signal layer (individual strategies producing reliable signal);
(b) enough historical trades per strategy to learn interaction weights;
(c) a versioning scheme for the network topology itself.

None of those prerequisites are met yet. Defer until individual strategy
evaluation (fork-eval / evolve cycles) produces at least one consistently
profitable strategy on real data.

**Trigger:** one or more strategies produce a positive objective score on
walk-forward held-out windows; begin scoping the interaction layer then.

---

## vwap_reversion — regime filter required

vwap_reversion loses money across all parameter variants on SPY 5m (2026-06-18 to
2026-08-16): even with corrected R:R (target = entry + stop_dist × target_rr), all
forks are negative. Root cause: SPY 2026 has been trending, not range-bound. VWAP
reversion is a mean-reversion strategy that only works when the market is choppy.

Strategy needs a regime filter before it can be deployed. Candidates:
- ADX < threshold on prior day's 1d bar (indicates low directional movement)
- Intraday realized volatility check: skip if prior-day range > X% of price
- Prior-day close-to-open gap check: skip if gap > Y%
- Volume-weighted slope of VWAP: skip if VWAP is trending significantly intraday

**Trigger:** user asks to implement a regime filter, or a new market regime (sustained
choppy/range-bound period) makes the untouched version worth re-testing first.

---

## CL=F (crude oil) trend_momentum

CL=F shows no consistent MA crossover profitability across 4 annual windows. The
gc_evolved parameters that work on GC=F produce -2927 on ZN=F and erratic results
on CL=F. The ma_10_50 baseline (CL=F) starts at score=-inf (evolution couldn't improve).
Crude oil trades on geopolitical supply shocks more than secular trends, making simple
MA crossover unreliable.

**Trigger:** user specifically asks to explore crude oil, or a multi-year commodity
bull/bear run in crude creates conditions similar to the 2022–2026 gold secular trend.

---

## ZN=F (10-yr Treasury) trend_momentum — weakly promising

ma_10_50 on ZN=F: 3/4 windows profitable, +299 total over 4 years. Evolved params
(fast=6, slow=50, stop_pct=0.024) give score=+216 but last window (2025-2026) negative.
Not strong enough to deploy alongside GC=F, but the signal exists.

**Trigger:** user asks to revisit bonds, or a clear Fed policy trend cycle (rates rising
or falling steadily for 1+ years) creates conditions that favor slower MA crossover.

---

## Stub provider implementation (trading212_demo, ibkr_paper, oanda_practice)

Each stub needs a separate, explicit session discussion before wiring any real
API calls. Must never happen as a side effect of other work. Real-money trading
activation is always a separate, explicit, discussed decision.

**Trigger:** user explicitly names a provider and initiates the discussion in
session.
