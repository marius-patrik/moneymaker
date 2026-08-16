import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Zap, ChevronDown, Play, Loader2, Layers, SlidersHorizontal, RotateCcw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { StrategyFlow } from "@/components/StrategyFlow";
import { api, type Strategy, type BacktestResult, type MultiWindowResult, type AppConfig } from "@/lib/api";
import { fmt, fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

/** Coerce an edited param string back to the type its default implies. */
function coerce(raw: string, original: unknown): unknown {
  if (typeof original === "number") {
    const n = Number(raw);
    return Number.isNaN(n) ? original : n;
  }
  if (typeof original === "boolean") return raw === "true";
  return raw;
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-md border p-2.5 text-center">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className={`text-sm font-bold ${color ?? ""}`}>{value}</div>
    </div>
  );
}

function StrategyCard({ s, config }: { s: Strategy; config: AppConfig | null }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [showParams, setShowParams] = useState(false);
  const [mode, setMode] = useState<"single" | "multi">("single");

  const [form, setForm] = useState({
    ticker: "ES=F", start: "2026-01-01", end: "2026-08-01", interval: "5m",
    data_provider: "yfinance", windows: "2026-06-01:2026-07-01,2026-07-01:2026-08-01",
  });
  const [params, setParams] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [multi, setMulti] = useState<MultiWindowResult | null>(null);

  // Seed the param editor from the strategy's declared defaults.
  useEffect(() => {
    setParams(Object.fromEntries(Object.entries(s.params).map(([k, v]) => [k, String(v)])));
  }, [s]);

  const changed = Object.entries(params).filter(
    ([k, v]) => String(s.params[k]) !== v
  );

  async function runSingle() {
    setLoading(true);
    setMulti(null);
    try {
      const overrides = Object.fromEntries(
        changed.map(([k, v]) => [k, coerce(v, s.params[k])])
      );
      const r = await api.backtest.run({
        strategy: s.name, ticker: form.ticker, start: form.start, end: form.end,
        interval: form.interval, data_provider: form.data_provider,
        params: Object.keys(overrides).length ? overrides : undefined,
      });
      setResult(r);
      toast(`${s.name}: ${r.trade_count} trades, ${fmtDollar(r.total_pnl)}`,
            r.total_pnl >= 0 ? "success" : "info");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Backtest failed", "error");
    }
    setLoading(false);
  }

  async function runMulti() {
    const windows = form.windows.split(",").map((w) => w.trim()).filter(Boolean)
      .map((w) => w.split(":").map((x) => x.trim()) as [string, string])
      .filter(([a, b]) => a && b);
    if (!windows.length) return toast("Enter windows as start:end,start:end", "error");
    setLoading(true);
    setResult(null);
    try {
      const r = await api.backtest.runMulti({
        strategy: s.name, ticker: form.ticker, windows, interval: form.interval,
      });
      setMulti(r);
      toast(`${windows.length} windows · ${fmtDollar(r.total_pnl)}`,
            r.total_pnl >= 0 ? "success" : "info");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Multi-window backtest failed", "error");
    }
    setLoading(false);
  }

  return (
    <motion.div layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="overflow-hidden">
        <CardHeader className="cursor-pointer select-none" onClick={() => setOpen((v) => !v)}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <Zap className="h-4 w-4 shrink-0 text-primary" />
              <CardTitle className="truncate text-base">{s.name}</CardTitle>
              <Badge variant={s.source === "built-in" ? "secondary" : "outline"}>{s.source}</Badge>
              {Object.keys(s.params).length > 0 && (
                <Badge variant="outline" className="hidden sm:inline-flex">
                  {Object.keys(s.params).length} params
                </Badge>
              )}
            </div>
            <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            </motion.div>
          </div>
          <CardDescription className="line-clamp-1">{s.doc}</CardDescription>
        </CardHeader>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              style={{ overflow: "hidden" }}
            >
              <CardContent className="space-y-4 border-t pt-4">
                <StrategyFlow strategyName={s.name} params={s.params} />

                {/* mode switch */}
                <div className="flex gap-1 rounded-md bg-muted p-1">
                  {(["single", "multi"] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                        mode === m ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"
                      }`}
                    >
                      {m === "single" ? "Single window" : "Multi-window"}
                    </button>
                  ))}
                </div>

                <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:grid-cols-4">
                  <Field label="Ticker" value={form.ticker}
                         onValueChange={(v) => setForm((f) => ({ ...f, ticker: v }))} />
                  <Field label="Interval" value={form.interval}
                         onValueChange={(v) => setForm((f) => ({ ...f, interval: v }))} />

                  {mode === "single" ? (
                    <>
                      <Field label="Start" value={form.start}
                             onValueChange={(v) => setForm((f) => ({ ...f, start: v }))} />
                      <Field label="End" value={form.end}
                             onValueChange={(v) => setForm((f) => ({ ...f, end: v }))} />
                      <div className="space-y-1 min-[420px]:col-span-2">
                        <Label htmlFor={`dp-${s.name}`} className="text-xs">Data provider</Label>
                        <Select value={form.data_provider}
                                onValueChange={(v) => setForm((f) => ({ ...f, data_provider: v }))}>
                          <SelectTrigger id={`dp-${s.name}`} className="h-8 text-sm"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {(config?.data_providers ?? ["yfinance"]).map((p) => (
                              <SelectItem key={p} value={p}>{p}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </>
                  ) : (
                    <div className="min-[420px]:col-span-2">
                      <Field label="Windows" value={form.windows} mono
                             onValueChange={(v) => setForm((f) => ({ ...f, windows: v }))}
                             placeholder="start:end,start:end" />
                    </div>
                  )}
                </div>

                {/* param editor */}
                {Object.keys(s.params).length > 0 && (
                  <div className="rounded-md border">
                    <button
                      onClick={() => setShowParams((v) => !v)}
                      className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <span className="flex items-center gap-2">
                        <SlidersHorizontal className="h-3.5 w-3.5" />
                        Parameters
                        {changed.length > 0 && (
                          <Badge variant="secondary" className="text-[10px]">{changed.length} changed</Badge>
                        )}
                      </span>
                      <motion.div animate={{ rotate: showParams ? 180 : 0 }}>
                        <ChevronDown className="h-3.5 w-3.5" />
                      </motion.div>
                    </button>
                    <AnimatePresence>
                      {showParams && (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }} style={{ overflow: "hidden" }}>
                          <div className="space-y-2 border-t p-3">
                            <div className="grid grid-cols-1 gap-2 min-[420px]:grid-cols-2 sm:grid-cols-3">
                              {Object.entries(s.params).map(([k, def]) => {
                                const isChanged = String(def) !== params[k];
                                return (
                                  <Field
                                    key={k}
                                    label={k}
                                    value={params[k] ?? ""}
                                    onValueChange={(v) => setParams((p) => ({ ...p, [k]: v }))}
                                    mono
                                    labelClassName={isChanged ? "text-primary" : undefined}
                                    className={`h-7 ${isChanged ? "border-primary" : ""}`}
                                  />
                                );
                              })}
                            </div>
                            {changed.length > 0 && (
                              <Button size="sm" variant="ghost" className="h-7 text-xs"
                                      onClick={() => setParams(Object.fromEntries(
                                        Object.entries(s.params).map(([k, v]) => [k, String(v)])))}>
                                <RotateCcw className="h-3 w-3" /> Reset to defaults
                              </Button>
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}

                <Button size="sm" className="w-full" disabled={loading}
                        onClick={mode === "single" ? runSingle : runMulti}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" />
                           : mode === "single" ? <Play className="h-4 w-4" /> : <Layers className="h-4 w-4" />}
                  {loading ? "Running…" : mode === "single" ? "Run backtest" : "Run multi-window"}
                </Button>

                {/* single-window result */}
                {result && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <Metric label="P&L" value={fmtDollar(result.total_pnl)} color={pnlColor(result.total_pnl)} />
                      <Metric label="Trades" value={String(result.trade_count)} />
                      <Metric label="Win rate" value={fmtPct(result.win_rate)} />
                      <Metric label="Bars" value={String(result.bars_seen ?? "—")} />
                    </div>
                    <p className="font-mono text-[11px] text-muted-foreground">{result.session_name}</p>
                  </motion.div>
                )}

                {/* multi-window result */}
                {multi && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      <Metric label="Total P&L" value={fmtDollar(multi.total_pnl)} color={pnlColor(multi.total_pnl)} />
                      <Metric label="Windows" value={String(multi.window_count ?? multi.windows?.length ?? 0)} />
                      <Metric
                        label="Profitable"
                        value={multi.window_count
                          ? `${multi.windows_profitable}/${multi.window_count}`
                          : String(multi.windows_profitable ?? "—")}
                      />
                      <Metric label="P&L std" value={fmt(multi.pnl_std)} />
                    </div>
                    {multi.windows?.length > 0 && (
                      <div className="space-y-1 rounded-md border p-2">
                        {multi.windows.map((w, i) => (
                          <div key={i} className="flex items-center justify-between text-[11px]">
                            <span className="font-mono text-muted-foreground">{w.start} → {w.end}</span>
                            <span className={pnlColor(w.total_pnl)}>{fmtDollar(w.total_pnl)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </motion.div>
                )}
              </CardContent>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  );
}

export function Strategies() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.strategies.list()
      .then((r) => setStrategies(r.strategies))
      .catch(() => {})
      .finally(() => setLoading(false));
    api.config.get().then(setConfig).catch(() => {});
  }, []);

  const filtered = strategies.filter(
    (s) => s.name.toLowerCase().includes(query.toLowerCase()) ||
           s.doc.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Strategies</h1>
          <p className="text-sm text-muted-foreground">
            {strategies.length} available · expand one to tune parameters and backtest.
          </p>
        </div>
        <Input value={query} onChange={(e) => setQuery(e.target.value)}
               aria-label="Filter strategies"
               placeholder="Filter…" className="h-8 w-full text-sm sm:max-w-56" />
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">No strategies match “{query}”.</p>
      ) : (
        <div className="space-y-3">
          {filtered.map((s) => <StrategyCard key={s.name} s={s} config={config} />)}
        </div>
      )}
    </div>
  );
}
