import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { Zap, Plus, Search, Loader2, Activity } from "lucide-react";
import { Panel } from "@/components/terminal/Panel";
import { SkeletonRows, ErrorState, EmptyState } from "@/components/terminal/States";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { useResource } from "@/lib/useResource";
import { api, type Strategy } from "@/lib/api";
import { cn } from "@/lib/utils";
import { BacktestPanel } from "@/pages/workspace/BacktestPanel";
import { LabPanel } from "@/pages/workspace/LabPanel";
import { NewStrategyDialog } from "@/pages/workspace/NewStrategyDialog";

const LAST_KEY = "mm.workspace.strategy";

/**
 * The workspace.
 *
 * Backtesting, optimising and trading a strategy are the same job at
 * different moments, so they are tabs over one selected system rather than
 * separate destinations. The list on the left is the sidebar's actual
 * content — picking a system is navigation.
 */
export function Strategies() {
  const strategies = useResource(() => api.strategies.list(), []);
  const [selected, setSelected] = useState<string | null>(
    () => localStorage.getItem(LAST_KEY));
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState("GC=F");

  const list = strategies.data?.strategies ?? [];

  useEffect(() => {
    if (!selected && list.length) setSelected(list[0].name);
  }, [list, selected]);

  useEffect(() => {
    if (selected) localStorage.setItem(LAST_KEY, selected);
  }, [selected]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return list.filter((s) => s.name.toLowerCase().includes(q) || s.doc.toLowerCase().includes(q));
  }, [list, query]);

  const current = list.find((s) => s.name === selected) ?? null;

  return (
    <div className="flex h-full min-h-0">
      {/* ---- contextual sidebar: the systems themselves ---- */}
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-card/40 lg:flex">
        <div className="flex h-11 shrink-0 items-center justify-between gap-2 border-b px-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.09em] text-muted-foreground">
            Systems
          </span>
        </div>
        <div className="shrink-0 border-b p-2">
          <NewStrategyDialog onCreated={strategies.reload} />
        </div>

        <div className="shrink-0 border-b p-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)}
                   aria-label="Filter systems" placeholder="Filter…"
                   className="h-8 pl-8 text-xs" />
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {strategies.error ? (
            <ErrorState message={strategies.error} onRetry={strategies.reload} />
          ) : !strategies.settled ? (
            <SkeletonRows rows={6} cols={2} />
          ) : filtered.length === 0 ? (
            <EmptyState title="No systems match" />
          ) : (
            filtered.map((s) => (
              <button
                key={s.name}
                onClick={() => setSelected(s.name)}
                className={cn(
                  "flex w-full flex-col gap-0.5 border-b border-border/60 px-3 py-2.5 text-left transition-colors",
                  s.name === selected ? "bg-accent" : "hover:bg-accent/40"
                )}
              >
                <span className="flex items-center gap-1.5">
                  <Zap className={cn("h-3 w-3 shrink-0",
                    s.name === selected ? "text-primary" : "text-muted-foreground")} />
                  <span className="truncate text-xs font-medium">{s.name}</span>
                </span>
                <span className="truncate pl-[18px] text-[10px] text-muted-foreground">
                  {Object.keys(s.params).length} params · {s.source}
                </span>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* ---- workspace ---- */}
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
              {/* The name is the picker — a separate select below it duplicated
                  what the heading already identifies. */}
              <div className="flex min-w-0 items-center gap-2">
                <Select value={selected ?? ""} onValueChange={setSelected}>
                  <SelectTrigger
                    aria-label="Select system"
                    className="h-auto gap-1.5 border-0 bg-transparent p-0 text-sm font-semibold shadow-none hover:text-muted-foreground focus:ring-0"
                  >
                    <span className="truncate">{current.name}</span>
                  </SelectTrigger>
                  <SelectContent>
                    {list.map((s) => (
                      <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Badge variant="outline" className="text-[10px]">{current.source}</Badge>
                <span className="hidden truncate text-[11px] text-muted-foreground sm:inline">
                  {current.doc}
                </span>
              </div>
              <TabsList className="h-8">
                <TabsTrigger value="backtest" className="text-xs">Backtest</TabsTrigger>
                <TabsTrigger value="lab" className="text-xs">Lab</TabsTrigger>
              </TabsList>
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
