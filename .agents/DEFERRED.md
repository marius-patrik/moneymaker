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

## Stub provider implementation (trading212_demo, ibkr_paper, oanda_practice)

Each stub needs a separate, explicit session discussion before wiring any real
API calls. Must never happen as a side effect of other work. Real-money trading
activation is always a separate, explicit, discussed decision.

**Trigger:** user explicitly names a provider and initiates the discussion in
session.
