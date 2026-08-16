# Parity audit — against Trading212 and TradingView

Reviewed 2026-08-16. Endpoints were enumerated from `src/server.py` and
diffed against the README; UI capabilities were checked against the two
reference products feature by feature.

## Charting (TradingView)

Built on `lightweight-charts` — TradingView's own library — so the
interaction model is theirs rather than an imitation.

| Capability | State |
|---|---|
| Candlesticks / line toggle | ✅ |
| Volume pane | ✅ |
| Crosshair with OHLCV readout | ✅ |
| Scroll to zoom, drag to pan, axis stretch | ✅ |
| Timeframes 5m / 15m / 1h / 1d / 1wk | ✅ |
| Theme-aware, redraws on theme change | ✅ |
| Drawing tools (trendlines, fib) | ❌ not built |
| Indicator overlays (MA, RSI, MACD) | ❌ not built |
| Price alerts | ❌ not built |
| Compare instruments on one chart | ❌ not built |

The four gaps are analysis conveniences. None of them block the product's
purpose, which is automated systems rather than discretionary charting — but
indicator overlays are the most defensible next addition, since strategies
already compute MAs and VWAP that the chart cannot show.

## Trading (Trading212)

| Capability | State |
|---|---|
| Instrument search | ✅ |
| Watchlist with live price and change | ✅ |
| Market orders, long and short | ✅ |
| Open positions, marked to market | ✅ |
| Position inspection (entry, mark, unrealised, % move) | ✅ |
| Close at market | ✅ |
| Account switching | ✅ |
| Trade history with full detail | ✅ |
| Realised **and** unrealised in headline totals | ✅ (fixed in this audit) |
| Limit / stop orders | ❌ not built |
| Stop-loss and take-profit attached at entry | ❌ not built |
| Fractional-size helper ("invest $X") | ❌ not built |

Order types are the real gap. A strategy sets its own stops internally, so
this only limits manual trading — which the product deliberately treats as
secondary.

## Fixed during this audit

- **Unrealised P&L never reached any total.** It existed per position but
  `/stats` and `/positions` summed realised only, so an account sitting in a
  losing open trade displayed as flat. Both endpoints now report realised,
  unrealised and a combined total; the context bar, overview, portfolio and
  both position tables show it.
- `/api/search` and `/api/pnl-distribution` were implemented but missing
  from the README.

## Deliberately absent

- Real-money brokers. Every execution path refuses a live provider; enabling
  one is a separate, explicit decision.
- Level 2 / order book depth — not available from the free data providers.
