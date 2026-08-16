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

## Stub provider implementation (trading212_demo, ibkr_paper, oanda_practice)

Each stub needs a separate, explicit session discussion before wiring any real
API calls. Must never happen as a side effect of other work. Real-money trading
activation is always a separate, explicit, discussed decision.

**Trigger:** user explicitly names a provider and initiates the discussion in
session.
