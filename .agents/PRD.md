# Product Requirements — moneymaker

## Purpose

A personal tool for developing, backtesting, and eventually live-paper trading
intraday price-action strategies against CFD/futures instruments. It is **not**
a general-purpose trading platform, **not** a signal service, **not** financial
advice infrastructure for anyone except the owner.

## Who uses it

One developer/trader, working alone. Not multi-tenant. Not a public API. Security
model is "trust the operator" — the only user is the owner.

## Core requirements

1. **Backtest parity with live**: all strategy logic runs identically in backtest
   and live modes. The simulated provider is the reference implementation — real
   providers must match its interface exactly.
2. **Risk-first position sizing**: position size is always derived from % of account
   risked per trade, never from a fixed share/contract count.
3. **Pluggable strategies**: new strategies added by dropping a `.py` file into
   `~/.moneymaker/strategies/` with no engine changes.
4. **Credentials never in plaintext by default**: `credentials.json` never committed;
   secrets stored as env-var references unless the user explicitly opts into
   on-disk storage.
5. **Real-money trading is never automatic**: the `is_live` flag on a provider
   controls this; `make_provider()` refuses to auto-construct live providers;
   wiring one up is always an explicit out-of-band decision.

## Non-requirements / explicit out-of-scope

- Multi-user or team support
- Production SLAs, uptime guarantees, or latency requirements
- Real-time execution at sub-second precision
- Financial advice or recommendations for anyone other than the owner
- Compliance, regulatory reporting, or audit logging
- A UI beyond the CLI and the local HTTP API

## Version contract

Backward-incompatible changes to the Strategy/StrategyContext interface should
bump the minor version (0.x). Any change that breaks existing home-directory
data formats (accounts.json schema, session CSV columns) needs a migration path
before shipping.
