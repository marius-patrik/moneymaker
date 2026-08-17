import { useEffect, useMemo, useState } from "react";
import { Zap, Search, Loader2, Copy } from "lucide-react";
import { Panel, Stat } from "@/components/terminal/Panel";
import { SkeletonRows, ErrorState, EmptyState } from "@/components/terminal/States";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useResource } from "@/lib/useResource";
import { api, type StrategyStats } from "@/lib/api";
import { cn, fmtDollar, fmtPct, pnlColor } from "@/lib/utils";
import { BacktestPanel } from "@/pages/workspace/BacktestPanel";
import { LabPanel } from "@/pages/workspace/LabPanel";
import { NewStrategyDialog } from "@/pages/workspace/NewStrategyDialog";

const LAST_KEY = "mm.strategy";
const TICKER_KEY = "mm.strategy.ticker";

/** Compact performance line for a system in the list. */
function ListMetrics({ s }: { s?: StrategyStats }) {
  if (!s || s.trades === 0) {
    return <span className="text-[10px] text-muted-foreground">no runs yet</span>;
  }
  return (
    <span className="flex items-center gap-2 font-mono text-[10px] tabular-nums">
      <span className={pnlColor(s.total_pnl)}>{fmtDollar(s.total_pnl)}</span>
      <span className="text-muted-foreground">
        {s.trades}t · {s.win_rate != null ? fmtPct(s.win_rate) : "—"}
      </span>
    </span>
  );
}

export function SystemsPanel() {
  const { toast } = useToast();
  const strategies = useResource(() => api.strategies.list(), []);
  const stats = useResource(() => api.strategies.stats(), [], { pollMs: 30000 });

  const [selected, setSelected] = useState<string | null>(
    () => localStorage.getItem(LAST_KEY));
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState(() => localStorage.getItem(TICKER_KEY) ?? "GC=F");
  const [copying, setCopying] = useState(false);

  const list = strategies.data?.strategies ?? [];
  const byName = stats.data?.stats ?? {};

  useEffect(() => { if (!selected && list.length) setSelected(list[0].name); }, [list, selected]);
  useEffect(() => { if (selected) localStorage.setItem(LAST_KEY, selected); }, [selected]);
  useEffect(() => { localStorage.setItem(TICKER_KEY, ticker); }, [ticker]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return list.filter((s) => s.name.toLowerCase().includes(q) || s.doc.toLowerCase().includes(q));
  }, [list, query]);

  const current = list.find((s) => s.name === selected) ?? null;
  const currentStats = current ? byName[current.name] : undefined;

  async function duplicate() {
    if (!current) return;
    setCopying(true);
    try {
      const r = await api.strategies.duplicate(current.name);
      toast(`Created ${r.name}`, "success");
      await strategies.reload();
      setSelected(r.name);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Copy failed", "error");
    }
    setCopying(false);
  }

  return (
    <div className="flex h-full min-h-0">
      {/* systems, with how each has actually performed */}
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-card/40 lg:flex">
        <div className="flex h-11 shrink-0 items-center border-b px-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-muted-foreground">
            Systems
          </span>
        </div>
        <div className="shrink-0 space-y-2 border-b p-2">
          <NewStrategyDialog onCreated={strategies.reload} />
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)}
                   aria-label="Filter systems" placeholder="Filter…"
                   className="h-8 pl-8 text-xs" />
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {strategies.error ? <ErrorState message={strategies.error} onRetry={strategies.reload} />
            : !strategies.settled ? <SkeletonRows rows={6} cols={2} />
            : filtered.length === 0 ? <EmptyState title="Nothing matches" />
            : filtered.map((s) => (
                <button key={s.name} onClick={() => setSelected(s.name)}
                        className={cn("flex w-full flex-col gap-1 border-b border-border/60 px-3 py-2.5 text-left transition-colors",
                          s.name === selected ? "bg-accent" : "hover:bg-accent/40")}>
                  <span className="flex items-center gap-1.5">
                    <Zap className={cn("h-3 w-3 shrink-0",
                      s.name === selected ? "text-primary" : "text-muted-foreground")} />
                    <span className="truncate text-xs font-medium">{s.name}</span>
                  </span>
                  <span className="pl-[18px]"><ListMetrics s={byName[s.name]} /></span>
                </button>
              ))}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {!current ? (
          <div className="flex flex-1 items-center justify-center">
            {strategies.settled
              ? <EmptyState title="No system selected"
                            hint="Create one to start backtesting and optimising."
                            action={<NewStrategyDialog onCreated={strategies.reload} />} />
              : <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          </div>
        ) : (
          <Tabs defaultValue="backtest" className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                {/* the name is the picker */}
                <Select value={selected ?? ""} onValueChange={setSelected}>
                  <SelectTrigger aria-label="Select system"
                                 className="h-auto gap-1.5 border-0 bg-transparent p-0 text-sm font-semibold shadow-none hover:text-muted-foreground focus:ring-0">
                    <span className="truncate">{current.name}</span>
                  </SelectTrigger>
                  <SelectContent>
                    {list.map((s) => <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
                <span className="hidden truncate text-[11px] text-muted-foreground sm:inline">
                  {current.doc}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="ghost" onClick={duplicate} disabled={copying}
                        title="Copy this system so it can be edited">
                  {copying ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                           : <Copy className="h-3.5 w-3.5" />}
                  Duplicate
                </Button>
                <TabsList className="h-8">
                  <TabsTrigger value="backtest" className="text-xs">Backtest</TabsTrigger>
                  <TabsTrigger value="lab" className="text-xs">Lab</TabsTrigger>
                </TabsList>
              </div>
            </div>

            {/* how this system has done so far */}
            <div className="border-b bg-muted/20 px-3 py-2.5">
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 lg:grid-cols-6">
                <Stat label="Net P&L"
                      value={currentStats ? fmtDollar(currentStats.total_pnl) : "—"}
                      tone={!currentStats || currentStats.total_pnl === 0 ? "neutral"
                            : currentStats.total_pnl > 0 ? "profit" : "loss"} />
                <Stat label="Win rate"
                      value={currentStats?.win_rate != null ? fmtPct(currentStats.win_rate) : "—"} />
                <Stat label="Profit factor"
                      value={currentStats?.profit_factor != null
                             ? currentStats.profit_factor.toFixed(2) : "—"}
                      tone={currentStats?.profit_factor == null ? "neutral"
                            : currentStats.profit_factor >= 1 ? "profit" : "loss"} />
                <Stat label="Trades" value={currentStats ? String(currentStats.trades) : "—"} />
                <Stat label="Runs" value={currentStats ? String(currentStats.runs) : "—"} />
                <Stat label="Parameters" value={String(Object.keys(current.params).length)} />
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto">
              <TabsContent value="backtest" className="m-0 p-3">
                <BacktestPanel strategy={current} ticker={ticker} onTicker={setTicker} />
              </TabsContent>
              <TabsContent value="lab" className="m-0 p-3">
                <LabPanel strategy={current} ticker={ticker} />
              </TabsContent>
            </div>
          </Tabs>
        )}
      </div>
    </div>
  );
}
