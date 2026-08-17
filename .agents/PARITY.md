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
| Indicator overlays (SMA, EMA, VWAP, RSI) | ✅ added after this audit |
| Price alerts | ❌ not built |
| News feed | ✅ added |
| Compare instruments on one chart | ❌ not built |

Indicator overlays were the gap worth closing, and are done: SMA, EMA, VWAP
and RSI, computed server-side from the same candles the chart draws, so the
overlay and the strategies read one implementation rather than two that
drift. Selection persists per browser.

The remaining three are discretionary-charting conveniences. None blocks the
product's purpose, which is automated systems.

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
| Limit / stop orders | ✅ |
| Stop-loss and take-profit attached at entry | ✅ |
| Fractional-size helper ("invest $X") | ❌ not built |

Order types are done. Resting orders live in `src/orders.py` and a monitor
sweeps every 20s — timer-driven rather than streamed, because the free data
providers are polled anyway and yfinance is ~15s delayed, so a tighter loop
would re-read the same quote. Protective exits are attached to the position
they guard and cancelled with it, since a stop-loss outliving its position
would open a new one in the opposite direction.

The remaining gap is fractional sizing ("invest $X"), which is arithmetic on
top of what exists rather than new machinery.

## Added after this audit

- **Indicator overlays.** `/api/indicators` lists what can be drawn;
  `/api/indicator/<kind>/<ticker>` returns a series aligned to the chart's
  candles. SMA and EMA seed on the first full window; VWAP falls back to an
  unweighted mean when the feed reports no volume, which futures often do,
  so the line still means something. 12 tests.

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
