import { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { ArrowUpRight, ArrowDownRight, Loader2, Star } from "lucide-react";
import { Panel, Stat } from "@/components/terminal/Panel";
import { EmptyState, ErrorState } from "@/components/terminal/States";
import { TickerSearch } from "@/components/terminal/TickerSearch";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { useResource } from "@/lib/useResource";
import { api, type PriceHistory } from "@/lib/api";
import { cn, fmt, fmtDollar, fmtPct } from "@/lib/utils";

const WATCH_KEY = "mm.watchlist";
const TICKER_KEY = "mm.ticker";
const DEFAULT_WATCH = ["GC=F", "ES=F", "NQ=F", "CL=F", "SPY"];

function Chart({ hist }: { hist: PriceHistory }) {
  const stroke = hist.change >= 0 ? "hsl(var(--profit))" : "hsl(var(--loss))";
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={hist.bars} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="tpx" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity={0.24} />
            <stop offset="100%" stopColor={stroke} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="t" hide />
        <YAxis domain={["dataMin", "dataMax"]} hide />
        <Tooltip formatter={(v: number) => [fmt(v), "Price"]}
                 labelFormatter={(l) => String(l).replace("T", " ")}
                 contentStyle={{ background: "hsl(var(--popover))",
                                 border: "1px solid hsl(var(--border))",
                                 borderRadius: 10, fontSize: 11 }} />
        <Area type="monotone" dataKey="c" stroke={stroke} strokeWidth={1.6}
              fill="url(#tpx)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** One watchlist row: symbol, last, change. */
function WatchRow({ symbol, active, onSelect, onRemove }: {
  symbol: string; active: boolean; onSelect: () => void; onRemove: () => void;
}) {
  const h = useResource(() => api.orders.history(symbol, "1h", 3), [symbol], { pollMs: 60000 });
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
          {d && d.bars.length > 1 && (
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
export function Trade() {
  const { toast } = useToast();
  const [watch, setWatch] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem(WATCH_KEY) ?? "") ?? DEFAULT_WATCH; }
    catch { return DEFAULT_WATCH; }
  });
  const [ticker, setTicker] = useState(() => localStorage.getItem(TICKER_KEY) ?? DEFAULT_WATCH[0]);
  const [size, setSize] = useState("1");
  const [accountId, setAccountId] = useState("");
  const [placing, setPlacing] = useState<"long" | "short" | null>(null);

  const accounts = useResource(() => api.accounts.list(), []);
  const hist = useResource(() => api.orders.history(ticker, "1h", 5), [ticker], { pollMs: 45000 });

  useEffect(() => { localStorage.setItem(WATCH_KEY, JSON.stringify(watch)); }, [watch]);
  useEffect(() => { localStorage.setItem(TICKER_KEY, ticker); }, [ticker]);
  useEffect(() => {
    const list = accounts.data?.accounts ?? [];
    if (!accountId && list[0]) setAccountId(list[0].account_id);
  }, [accounts.data, accountId]);

  function select(sym: string) {
    setTicker(sym);
    setWatch((w) => (w.includes(sym) ? w : [sym, ...w].slice(0, 20)));
  }

  async function place(direction: "long" | "short") {
    setPlacing(direction);
    try {
      const r = await api.orders.place({
        ticker, direction, size: Number(size), account_id: accountId || undefined,
      });
      toast(`${direction === "long" ? "Bought" : "Sold"} ${r.size} ${r.ticker} @ ${fmt(r.fill_price)}`,
            "success");
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
  const notional = last != null ? last * Number(size || 0) : null;

  return (
    <div className="flex h-full min-h-0">
      {/* watchlist */}
      <aside className="hidden w-60 shrink-0 flex-col border-r bg-card/40 lg:flex">
        <div className="flex h-11 shrink-0 items-center border-b px-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-muted-foreground">
            Watchlist
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
                 actions={<span className="font-mono text-[10px] text-muted-foreground">1h · 5d</span>}>
            <div className="space-y-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-[26px] font-semibold tabular-nums tracking-tight">
                    {last != null ? fmt(last) : "—"}
                  </span>
                  {d && d.bars.length > 1 && (
                    <span className={cn("font-mono text-sm font-medium tabular-nums",
                                        up ? "text-profit" : "text-loss")}>
                      {up ? "+" : ""}{fmt(d.change)} ({fmtPct(d.change_pct)})
                    </span>
                  )}
                </div>
                <div className="flex gap-4 font-mono text-[11px] tabular-nums text-muted-foreground">
                  <span>H {d?.high != null ? fmt(d.high) : "—"}</span>
                  <span>L {d?.low != null ? fmt(d.low) : "—"}</span>
                </div>
              </div>
              <div className="h-80">
                {hist.error ? <ErrorState message={hist.error} onRetry={hist.reload} />
                  : !hist.settled ? <div className="flex h-full items-center justify-center">
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
                  : d && d.bars.length > 1 ? <Chart hist={d} />
                  : <EmptyState title="No price data" hint={`Nothing returned for ${ticker}.`} />}
              </div>
            </div>
          </Panel>

          <Panel title="Ticket">
            <div className="space-y-3">
              <Field label="Size" type="number" value={size} onValueChange={setSize} />
              <div className="space-y-1">
                <Label htmlFor="trade-account" className="text-xs">Account</Label>
                <Select value={accountId} onValueChange={setAccountId}>
                  <SelectTrigger id="trade-account" className="h-8 text-sm">
                    <SelectValue placeholder="Select account" />
                  </SelectTrigger>
                  <SelectContent>
                    {(accounts.data?.accounts ?? []).map((a) => (
                      <SelectItem key={a.account_id} value={a.account_id}>
                        {a.name} · {fmtDollar(a.balance)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5 rounded-lg border bg-muted/30 p-2.5 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Notional</span>
                  <span className="font-mono tabular-nums">
                    {notional != null ? fmtDollar(notional) : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Buying power</span>
                  <span className="font-mono tabular-nums">{acct ? fmtDollar(acct.balance) : "—"}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Button className="w-full bg-profit text-white hover:bg-profit/90"
                        onClick={() => place("long")} disabled={!!placing}>
                  {placing === "long" ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <AnimatedIcon icon={ArrowUpRight} motionType="lift" className="h-4 w-4" />}
                  Buy
                </Button>
                <Button className="w-full bg-loss text-white hover:bg-loss/90"
                        onClick={() => place("short")} disabled={!!placing}>
                  {placing === "short" ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <AnimatedIcon icon={ArrowDownRight} motionType="lift" className="h-4 w-4" />}
                  Sell
                </Button>
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
