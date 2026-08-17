import { useEffect, useState } from "react";
import { ArrowUpRight, ArrowDownRight, Loader2, Star, CandlestickChart, LineChart,
         Minus, TrendingUp, Eraser } from "lucide-react";
import { Panel, Stat } from "@/components/terminal/Panel";
import { EmptyState, ErrorState } from "@/components/terminal/States";
import { TickerSearch } from "@/components/terminal/TickerSearch";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription }
  from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { useResource } from "@/lib/useResource";
import { useAccount } from "@/lib/useAccount";
import { PriceChart, OhlcReadout, type ChartKind, type DrawTool, type Drawing }
  from "@/components/terminal/PriceChart";
import { AlertsPanel } from "@/components/terminal/AlertsPanel";
import { PositionsPanel } from "@/components/terminal/PositionsPanel";
import { PendingOrdersPanel } from "@/components/terminal/PendingOrdersPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SystemsPanel } from "@/pages/SystemsPanel";
import { IndicatorPicker, type ActiveIndicator } from "@/components/terminal/IndicatorPicker";
import { api, type Candle, type IndicatorSeries } from "@/lib/api";
import { cn, fmt, fmtDollar, fmtPct } from "@/lib/utils";

const WATCH_KEY = "mm.watchlist";
const TICKER_KEY = "mm.ticker";
const IND_KEY = "mm.indicators";
const DRAW_KEY = "mm.drawings";
const DEFAULT_WATCH = ["GC=F", "ES=F", "NQ=F", "CL=F", "SPY"];

/** Interval paired with a lookback that yields a useful number of bars. */
const TIMEFRAMES = [
  { label: "5m", interval: "5m", days: 5 },
  { label: "15m", interval: "15m", days: 10 },
  { label: "1h", interval: "1h", days: 30 },
  { label: "1d", interval: "1d", days: 365 },
  { label: "1wk", interval: "1wk", days: 1825 },
] as const satisfies readonly { label: string; interval: string; days: number }[];

/** One watchlist row: symbol, last, change. */
function WatchRow({ symbol, active, onSelect, onRemove }: {
  symbol: string; active: boolean; onSelect: () => void; onRemove: () => void;
}) {
  const h = useResource(() => api.orders.history(symbol, "1d", 30), [symbol], { pollMs: 60000 });
  const d = h.data;
  const up = (d?.change ?? 0) >= 0;
  return (
    <div className={cn("group flex items-center gap-2 border-b border-border/60 px-3 py-2 transition-colors",
                       active ? "bg-accent" : "hover:bg-accent/40")}>
      <button onClick={onSelect} className="flex min-w-0 flex-1 items-center justify-between gap-2 text-left">
        <span className="truncate font-mono text-xs font-medium">{symbol}</span>
        <span className="shrink-0 text-right">
          <span className="block font-mono text-xs tabular-nums">
            {d?.last != null ? fmt(d.last) : h.loading ? "…" : "—"}
          </span>
          {d && d.candles.length > 1 && (
            <span className={cn("block font-mono text-[10px] tabular-nums",
                                up ? "text-profit" : "text-loss")}>
              {up ? "+" : ""}{fmtPct(d.change_pct)}
            </span>
          )}
        </span>
      </button>
      <button onClick={onRemove} aria-label={`Remove ${symbol}`}
              className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100">
        <Star className="h-3 w-3 fill-current text-muted-foreground" />
      </button>
    </div>
  );
}

/**
 * Trading desk — instrument first.
 *
 * A watchlist on the left, the selected instrument's chart and a ticket on
 * the right. Systems are deployed from Strategies; this is where you look at
 * a market and act on it directly.
 */
/**
 * Trade.
 *
 * Manual execution and automated systems are two ways to act on the same
 * instrument, so they live behind one tab strip rather than two
 * destinations you navigate between mid-thought.
 */
export function Trade() {
  const { toast } = useToast();
  const { accountId, scoped, isAll } = useAccount();
  const [watch, setWatch] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem(WATCH_KEY) ?? "") ?? DEFAULT_WATCH; }
    catch { return DEFAULT_WATCH; }
  });
  const [ticker, setTicker] = useState(() => localStorage.getItem(TICKER_KEY) ?? DEFAULT_WATCH[0]);
  const [size, setSize] = useState("1");
  const [orderKind, setOrderKind] = useState<"market" | "limit" | "stop" | "strategy">("market");
  const [system, setSystem] = useState("");
  const [confirmAll, setConfirmAll] = useState<null | "long" | "short">(null);
  const [trigger, setTrigger] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [ordNonce, setOrdNonce] = useState(0);
  const [tool, setTool] = useState<DrawTool>("none");
  const [drawings, setDrawings] = useState<Record<string, Drawing[]>>(() => {
    try { return JSON.parse(localStorage.getItem(DRAW_KEY) ?? "{}"); } catch { return {}; }
  });
  const [sizeMode, setSizeMode] = useState<"units" | "cash">("units");

  const [placing, setPlacing] = useState<"long" | "short" | null>(null);
  const [posNonce, setPosNonce] = useState(0);
  const [indicators, setIndicators] = useState<ActiveIndicator[]>(() => {
    try { return JSON.parse(localStorage.getItem(IND_KEY) ?? "[]"); } catch { return []; }
  });
  const [series, setSeries] = useState<IndicatorSeries[]>([]);
  const [tf, setTf] = useState<{ interval: string; days: number; label: string }>(
    TIMEFRAMES[2]);
  const [kind, setKind] = useState<ChartKind>("candles");
  const [hover, setHover] = useState<Parameters<NonNullable<Parameters<typeof PriceChart>[0]["onHover"]>>[0]>(null);

  const accounts = useResource(() => api.accounts.list(), []);
  const strategies = useResource(() => api.strategies.list(), []);
  const hist = useResource(() => api.orders.history(ticker, tf.interval, tf.days),
                           [ticker, tf.interval, tf.days], { pollMs: 45000 });

  useEffect(() => { localStorage.setItem(WATCH_KEY, JSON.stringify(watch)); }, [watch]);
  useEffect(() => { localStorage.setItem(TICKER_KEY, ticker); }, [ticker]);
  useEffect(() => { localStorage.setItem(IND_KEY, JSON.stringify(indicators)); }, [indicators]);
  // Drawings are per instrument — a level on gold means nothing on the S&P.
  useEffect(() => { localStorage.setItem(DRAW_KEY, JSON.stringify(drawings)); }, [drawings]);

  // Indicators follow the chart: same instrument, same timeframe.
  useEffect(() => {
    if (indicators.length === 0) { setSeries([]); return; }
    let alive = true;
    Promise.all(indicators.map((i) =>
      api.orders.indicator(i.kind, ticker, i.period, tf.interval, tf.days)
        .catch(() => null)))
      .then((rs) => { if (alive) setSeries(rs.filter(Boolean) as IndicatorSeries[]); });
    return () => { alive = false; };
  }, [indicators, ticker, tf.interval, tf.days]);
  function select(sym: string) {
    setTicker(sym);
    setWatch((w) => (w.includes(sym) ? w : [sym, ...w].slice(0, 20)));
  }

  async function place(direction: "long" | "short") {
    // Fanning an order across every account is not something to do by
    // accident, so it is confirmed rather than merely allowed.
    if (isAll && orderKind !== "strategy" && confirmAll !== direction) {
      setConfirmAll(direction);
      return;
    }
    setConfirmAll(null);
    setPlacing(direction);
    try {
      if (orderKind === "strategy") {
        if (!system) throw new Error("Pick a strategy to deploy");
        const r = await api.live.start({ strategy: system, ticker });
        toast(`${system} live on ${ticker} · ${r.session_id}`, "success");
        setPosNonce((n) => n + 1);
      } else if (orderKind === "market") {
        const r = await api.orders.place({
          ticker, direction, account_id: scoped, all_accounts: isAll,
          ...(sizeMode === "units"
            ? { size: Number(size) }
            : { notional: Number(size) }),
          stop_loss: stopLoss ? Number(stopLoss) : undefined,
          take_profit: takeProfit ? Number(takeProfit) : undefined,
        });
        const guards = r.attached_orders.length
          ? ` (+${r.attached_orders.length} exit${r.attached_orders.length > 1 ? "s" : ""})` : "";
        const spread = r.accounts.length > 1 ? ` across ${r.accounts.length} accounts` : "";
        toast(`${direction === "long" ? "Bought" : "Sold"} ${r.size} ${r.ticker} @ ${fmt(r.fill_price)}${guards}${spread}`,
              "success");
        setPosNonce((n) => n + 1);
      } else {
        if (!trigger) throw new Error(`A ${orderKind} order needs a trigger price`);
        const o = await api.orders.placePending({
          ticker, direction, size: Number(size), order_type: orderKind,
          trigger_price: Number(trigger),
          limit_price: orderKind === "limit" ? Number(trigger) : undefined,
          account_id: scoped,
        });
        toast(`${orderKind} ${direction} ${o.size} ${o.ticker} resting @ ${fmt(o.trigger_price)}`,
              "success");
        setOrdNonce((n) => n + 1);
      }
      accounts.reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Order rejected", "error");
    }
    setPlacing(null);
  }

  const d = hist.data;
  const last = d?.last ?? null;
  const up = (d?.change ?? 0) >= 0;
  const acct = (accounts.data?.accounts ?? []).find((a) => a.account_id === accountId);
  const notional = sizeMode === "cash"
    ? Number(size || 0)
    : last != null ? last * Number(size || 0) : null;
  const units = sizeMode === "cash" && last
    ? Number(size || 0) / last
    : Number(size || 0);

  return (
    <Tabs defaultValue="manual" className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <TabsList className="h-8">
          <TabsTrigger value="manual" className="text-xs">Manual</TabsTrigger>
          <TabsTrigger value="systems" className="text-xs">Systems</TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="systems" className="m-0 min-h-0 flex-1 overflow-hidden">
        <SystemsPanel />
      </TabsContent>

      <TabsContent value="manual" className="m-0 flex min-h-0 flex-1 overflow-hidden">
      <div className="flex h-full min-h-0 w-full">
      {/* watchlist */}
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-card/40 lg:flex">
        <div className="flex h-11 shrink-0 items-center border-b px-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-muted-foreground">
            Search
          </span>
        </div>
        <div className="shrink-0 border-b p-2">
          <TickerSearch value="" onSelect={select} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {watch.map((sym) => (
            <WatchRow key={sym} symbol={sym} active={sym === ticker}
                      onSelect={() => setTicker(sym)}
                      onRemove={() => setWatch((w) => w.filter((x) => x !== sym))} />
          ))}
        </div>
      </aside>

      <div className="min-w-0 flex-1 overflow-y-auto p-3">
        {/* mobile instrument search */}
        <div className="mb-3 lg:hidden">
          <TickerSearch value={ticker} onSelect={select} />
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
          <Panel title={ticker}
                 actions={
                   <div className="flex items-center gap-1">
                     <div className="flex rounded-md bg-muted/70 p-0.5">
                       {([
                         { t: "hline" as const, icon: Minus, label: "Horizontal level" },
                         { t: "trend" as const, icon: TrendingUp, label: "Trendline" },
                       ]).map(({ t, icon: Icon, label }) => (
                         <button key={t}
                                 onClick={() => setTool((c) => (c === t ? "none" : t))}
                                 aria-label={label} title={label}
                                 className={cn("rounded p-1 transition-colors",
                                   tool === t ? "bg-background text-foreground shadow-sm"
                                              : "text-muted-foreground hover:text-foreground")}>
                           <Icon className="h-3.5 w-3.5" />
                         </button>
                       ))}
                       {(drawings[ticker]?.length ?? 0) > 0 && (
                         <button onClick={() => setDrawings((d) => ({ ...d, [ticker]: [] }))}
                                 aria-label="Clear drawings" title="Clear drawings"
                                 className="rounded p-1 text-muted-foreground transition-colors hover:text-destructive">
                           <Eraser className="h-3.5 w-3.5" />
                         </button>
                       )}
                     </div>
                     <IndicatorPicker active={indicators} onChange={setIndicators} />
                     <div className="flex rounded-md bg-muted/70 p-0.5">
                       {TIMEFRAMES.map((t) => (
                         <button key={t.label} onClick={() => setTf(t)}
                                 className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] transition-colors",
                                   tf.label === t.label ? "bg-background text-foreground shadow-sm"
                                                        : "text-muted-foreground hover:text-foreground")}>
                           {t.label}
                         </button>
                       ))}
                     </div>
                     <button onClick={() => setKind((k) => (k === "candles" ? "line" : "candles"))}
                             aria-label={kind === "candles" ? "Switch to line chart" : "Switch to candles"}
                             className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                       {kind === "candles" ? <CandlestickChart className="h-3.5 w-3.5" />
                                           : <LineChart className="h-3.5 w-3.5" />}
                     </button>
                   </div>
                 }>
            <div className="space-y-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[26px] font-semibold tabular-nums tracking-tight">
                    {last != null ? fmt(last) : "—"}
                  </span>
                  {d && d.candles.length > 1 && (
                    <span className={cn("font-mono text-sm font-medium tabular-nums",
                                        up ? "text-profit" : "text-loss")}>
                      {up ? "+" : ""}{fmt(d.change)} ({fmtPct(d.change_pct)})
                    </span>
                  )}
                </div>
                <OhlcReadout hover={hover} fallback={d?.candles[d.candles.length - 1]} />
              </div>
              {hist.error ? <div className="h-[380px]"><ErrorState message={hist.error} onRetry={hist.reload} /></div>
                : !hist.settled ? <div className="flex h-[380px] items-center justify-center">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
                : d && d.candles.length > 1
                  ? <PriceChart candles={d.candles} kind={kind} height={380}
                                onHover={setHover} overlays={series}
                                drawings={drawings[ticker] ?? []} tool={tool}
                                onDraw={(dr) => {
                                  setDrawings((prev) => ({
                                    ...prev, [ticker]: [...(prev[ticker] ?? []), dr],
                                  }));
                                  setTool("none");   // one shape per selection
                                }} />
                  : <div className="h-[380px]"><EmptyState title="No price data"
                      hint={`Nothing returned for ${ticker} at ${tf.label}.`} /></div>}
            </div>
          </Panel>

          <Panel title="Ticket">
            <div className="space-y-3">
              <div className="flex rounded-lg bg-muted p-0.5">
                {(["market", "limit", "stop", "strategy"] as const).map((k) => (
                  <button key={k} onClick={() => setOrderKind(k)}
                          className={cn("flex-1 rounded-md px-2 py-1 text-[11px] font-medium capitalize transition-colors",
                            orderKind === k ? "bg-background shadow-sm" : "text-muted-foreground")}>
                    {k}
                  </button>
                ))}
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <Label htmlFor="ticket-size" className="text-xs">
                    {sizeMode === "units" ? "Size" : "Amount (USD)"}
                  </Label>
                  <button onClick={() => setSizeMode((m) => (m === "units" ? "cash" : "units"))}
                          className="text-[10px] text-muted-foreground hover:text-foreground">
                    {sizeMode === "units" ? "use amount" : "use units"}
                  </button>
                </div>
                <Input id="ticket-size" type="number" value={size}
                       onChange={(e) => setSize(e.target.value)}
                       className="h-8 text-sm" />
              </div>

              {orderKind === "strategy" && (
                <div className="space-y-1">
                  <Label htmlFor="ticket-strategy" className="text-xs">Strategy</Label>
                  <Select value={system} onValueChange={setSystem}>
                    <SelectTrigger id="ticket-strategy" className="h-8 text-sm">
                      <SelectValue placeholder="Select strategy" />
                    </SelectTrigger>
                    <SelectContent>
                      {(strategies.data?.strategies ?? []).map((st) => (
                        <SelectItem key={st.name} value={st.name}>{st.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    Hands {ticker} to the strategy, which then manages its own entries
                    and exits until you stop it.
                  </p>
                </div>
              )}

              {(orderKind === "limit" || orderKind === "stop") && (
                <Field
                  label={orderKind === "limit" ? "Limit price" : "Stop price"}
                  type="number" value={trigger} onValueChange={setTrigger}
                  placeholder={last != null ? fmt(last) : ""}
                  hint={orderKind === "limit"
                    ? "Buy below the market, sell above."
                    : "Buy above the market, sell below."} />
              )}
              <div className="space-y-1.5 rounded-lg border bg-muted/30 p-2.5 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Notional</span>
                  <span className="font-mono tabular-nums">
                    {notional != null ? fmtDollar(notional) : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Units</span>
                  <span className="font-mono tabular-nums">
                    {Number.isFinite(units) ? fmt(units, 4) : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Buying power</span>
                  <span className="font-mono tabular-nums">{acct ? fmtDollar(acct.balance) : "—"}</span>
                </div>
              </div>

              {orderKind === "market" && (
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Stop loss" type="number" value={stopLoss}
                         onValueChange={setStopLoss} placeholder="optional" />
                  <Field label="Take profit" type="number" value={takeProfit}
                         onValueChange={setTakeProfit} placeholder="optional" />
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                <Button className="w-full bg-profit text-white hover:bg-profit/90"
                        onClick={() => place("long")} disabled={!!placing}>
                  {placing === "long" ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <AnimatedIcon icon={ArrowUpRight} motionType="lift" className="h-4 w-4" />}
                  {orderKind === "strategy" ? "Deploy" : "Buy"}
                </Button>
                <Button className="w-full bg-loss text-white hover:bg-loss/90"
                        onClick={() => place("short")} disabled={!!placing}>
                  {placing === "short" ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <AnimatedIcon icon={ArrowDownRight} motionType="lift" className="h-4 w-4" />}
                  {orderKind === "strategy" ? "Deploy short" : "Sell"}
                </Button>
              </div>
            </div>
          </Panel>
          <div className="space-y-3 xl:col-span-2">
            <PositionsPanel accountId={scoped} refreshKey={posNonce}
                            onChanged={() => { accounts.reload(); setPosNonce((n) => n + 1); }} />
            <PendingOrdersPanel accountId={scoped} refreshKey={ordNonce}
                                onChanged={() => setOrdNonce((n) => n + 1)} />
            <AlertsPanel ticker={ticker} lastPrice={last} />
          </div>
        </div>
      </div>
      </div>
      </TabsContent>

      <Dialog open={!!confirmAll} onOpenChange={(v) => !v && setConfirmAll(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Trade every account?</DialogTitle>
            <DialogDescription>
              The header is set to <strong>All accounts</strong>, so this places the
              same order on each of the {accounts.data?.accounts.length ?? 0} — the
              same size on every one, not split between them.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 rounded-lg border bg-muted/30 p-3 text-[11px]">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Order</span>
              <span className="font-mono">
                {confirmAll} {sizeMode === "cash" ? fmtDollar(Number(size || 0)) : size} {ticker}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total exposure</span>
              <span className="font-mono">
                {fmtDollar((notional ?? 0) * (accounts.data?.accounts.length ?? 1))}
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" onClick={() => setConfirmAll(null)}>Cancel</Button>
            <Button onClick={() => confirmAll && place(confirmAll)}>
              Place on all
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Tabs>
  );
}
