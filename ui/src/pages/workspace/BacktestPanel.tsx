import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Play, Layers, Loader2, RotateCcw, SlidersHorizontal, ChevronDown } from "lucide-react";
import { Panel, Stat, DataTable } from "@/components/terminal/Panel";
import { EmptyState } from "@/components/terminal/States";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { TickerSearch } from "@/components/terminal/TickerSearch";
import { StrategyFlow } from "@/components/StrategyFlow";
import { useResource } from "@/lib/useResource";
import { api, type Strategy, type BacktestResult, type MultiWindowResult, type Trade } from "@/lib/api";
import { fmt, fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

function coerce(raw: string, original: unknown): unknown {
  if (typeof original === "number") { const n = Number(raw); return Number.isNaN(n) ? original : n; }
  if (typeof original === "boolean") return raw === "true";
  return raw;
}

export function BacktestPanel({
  strategy, ticker, onTicker,
}: { strategy: Strategy; ticker: string; onTicker: (t: string) => void }) {
  const { toast } = useToast();
  const config = useResource(() => api.config.get(), []);
  const [mode, setMode] = useState<"single" | "multi">("single");
  const [form, setForm] = useState({
    start: "2025-01-01", end: "2026-01-01", interval: "1d",
    data_provider: "yfinance", windows: "2025-01-01:2025-07-01,2025-07-01:2026-01-01",
  });
  const [params, setParams] = useState<Record<string, string>>({});
  const [showParams, setShowParams] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [multi, setMulti] = useState<MultiWindowResult | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    setParams(Object.fromEntries(Object.entries(strategy.params).map(([k, v]) => [k, String(v)])));
    setResult(null); setMulti(null); setTrades([]);
  }, [strategy]);

  const changed = Object.entries(params).filter(([k, v]) => String(strategy.params[k]) !== v);

  async function runSingle() {
    setLoading(true); setMulti(null);
    try {
      const overrides = Object.fromEntries(changed.map(([k, v]) => [k, coerce(v, strategy.params[k])]));
      const r = await api.backtest.run({
        strategy: strategy.name, ticker, start: form.start, end: form.end,
        interval: form.interval, data_provider: form.data_provider,
        params: Object.keys(overrides).length ? overrides : undefined,
      });
      setResult(r);
      // Pull the trade log so the run can be inspected, not just scored.
      try {
        const log = await api.sessions.get(`${r.session_name}.csv`);
        setTrades(("trades" in log ? log.trades : []) as Trade[]);
      } catch { setTrades([]); }
      toast(`${r.trade_count} trades · ${fmtDollar(r.total_pnl)}`,
            r.total_pnl > 0 ? "success" : "info");
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
    setLoading(true); setResult(null); setTrades([]);
    try {
      const r = await api.backtest.runMulti({
        strategy: strategy.name, ticker, windows, interval: form.interval,
      });
      setMulti(r);
      toast(`${windows.length} windows · ${fmtDollar(r.total_pnl)}`,
            r.total_pnl > 0 ? "success" : "info");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Multi-window failed", "error");
    }
    setLoading(false);
  }

  return (
    <div className="space-y-3">
      <Panel title="Configuration">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1">
              <Label className="text-xs">Instrument</Label>
              <TickerSearch value={ticker} onSelect={onTicker} />
            </div>
            <Field label="Interval" value={form.interval}
                   onValueChange={(v) => setForm((f) => ({ ...f, interval: v }))} />
            {mode === "single" ? (
              <>
                <Field label="Start" value={form.start}
                       onValueChange={(v) => setForm((f) => ({ ...f, start: v }))} />
                <Field label="End" value={form.end}
                       onValueChange={(v) => setForm((f) => ({ ...f, end: v }))} />
              </>
            ) : (
              <div className="sm:col-span-2">
                <Field label="Windows" value={form.windows} mono
                       onValueChange={(v) => setForm((f) => ({ ...f, windows: v }))} />
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-lg bg-muted p-0.5">
              {(["single", "multi"] as const).map((m) => (
                <button key={m} onClick={() => setMode(m)}
                        className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                          mode === m ? "bg-background shadow-sm" : "text-muted-foreground"}`}>
                  {m === "single" ? "Single" : "Walk-forward"}
                </button>
              ))}
            </div>
            <Button size="sm" onClick={mode === "single" ? runSingle : runMulti} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" />
                : <AnimatedIcon icon={mode === "single" ? Play : Layers} motionType="nudge" className="h-4 w-4" />}
              {loading ? "Running…" : "Run"}
            </Button>
            {Object.keys(strategy.params).length > 0 && (
              <Button size="sm" variant="ghost" onClick={() => setShowParams((v) => !v)}>
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Parameters
                {changed.length > 0 && (
                  <Badge variant="secondary" className="text-[10px]">{changed.length}</Badge>
                )}
                <ChevronDown className={`h-3 w-3 transition-transform ${showParams ? "rotate-180" : ""}`} />
              </Button>
            )}
          </div>

          {showParams && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                        className="space-y-2 overflow-hidden rounded-lg border bg-muted/20 p-3">
              <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
                {Object.entries(strategy.params).map(([k, def]) => {
                  const isChanged = String(def) !== params[k];
                  return (
                    <Field key={k} label={k} value={params[k] ?? ""} mono
                           onValueChange={(v) => setParams((p) => ({ ...p, [k]: v }))}
                           labelClassName={isChanged ? "text-primary" : undefined}
                           className={`h-7 ${isChanged ? "border-primary" : ""}`} />
                  );
                })}
              </div>
              {changed.length > 0 && (
                <Button size="sm" variant="ghost" className="h-7 text-xs"
                        onClick={() => setParams(Object.fromEntries(
                          Object.entries(strategy.params).map(([k, v]) => [k, String(v)])))}>
                  <RotateCcw className="h-3 w-3" /> Reset
                </Button>
              )}
            </motion.div>
          )}

          <StrategyFlow strategyName={strategy.name} params={strategy.params} />
        </div>
      </Panel>

      {result && (
        <Panel title="Result" actions={
          <span className="font-mono text-[10px] text-muted-foreground">{result.session_name}</span>}>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Net P&L" value={fmtDollar(result.total_pnl)}
                  tone={result.total_pnl === 0 ? "neutral" : result.total_pnl > 0 ? "profit" : "loss"} />
            <Stat label="Trades" value={String(result.trade_count)} />
            <Stat label="Win rate" value={fmtPct(result.win_rate)} />
            <Stat label="Bars" value={String(result.bars_seen ?? "—")} />
          </div>
        </Panel>
      )}

      {trades.length > 0 && (
        <Panel title={`${trades.length} trades`} dense>
          <DataTable head={<><th>Instrument</th><th>Side</th><th>Opened</th><th>Closed</th>
                            <th className="!text-right">Size</th><th className="!text-right">Entry</th>
                            <th className="!text-right">Exit</th><th>Reason</th>
                            <th className="!text-right">P&L</th></>}>
            {trades.map((t, i) => {
              const v = parseFloat(t.pnl) || 0;
              return (
                <tr key={i}>
                  <td className="font-mono">{t.ticker || ticker}</td>
                  <td>
                    <Badge variant={t.direction === "long" ? "profit" : "loss"}
                           className="px-1.5 py-0 text-[10px]">{t.direction}</Badge>
                  </td>
                  <td className="whitespace-nowrap font-mono text-muted-foreground">
                    {(t.entry_time ?? "").slice(0, 16)}
                  </td>
                  <td className="whitespace-nowrap font-mono text-muted-foreground">
                    {(t.exit_time ?? "").slice(0, 16) || "—"}
                  </td>
                  <td className="text-right font-mono tabular-nums">{t.size ?? "—"}</td>
                  <td className="text-right font-mono tabular-nums">{t.entry_price}</td>
                  <td className="text-right font-mono tabular-nums">{t.exit_price ?? "—"}</td>
                  <td className="text-muted-foreground">{t.exit_reason ?? "—"}</td>
                  <td className={`text-right font-mono tabular-nums ${pnlColor(v)}`}>
                    {t.pnl !== "" ? fmtDollar(v) : "—"}
                  </td>
                </tr>
              );
            })}
          </DataTable>
        </Panel>
      )}

      {multi && (
        <Panel title="Walk-forward">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Total P&L" value={fmtDollar(multi.total_pnl)}
                    tone={multi.total_pnl === 0 ? "neutral" : multi.total_pnl > 0 ? "profit" : "loss"} />
              <Stat label="Windows" value={String(multi.window_count ?? multi.windows?.length ?? 0)} />
              <Stat label="Profitable"
                    value={multi.window_count ? `${multi.windows_profitable}/${multi.window_count}`
                                              : String(multi.windows_profitable ?? "—")} />
              <Stat label="P&L stdev" value={fmt(multi.pnl_std)} />
            </div>
            {multi.windows?.length > 0 && (
              <DataTable head={<><th>From</th><th>To</th><th className="!text-right">Trades</th>
                                <th className="!text-right">P&L</th></>}>
                {multi.windows.map((w, i) => (
                  <tr key={i}>
                    <td className="font-mono">{w.start}</td>
                    <td className="font-mono">{w.end}</td>
                    <td className="text-right tabular-nums text-muted-foreground">{w.trades}</td>
                    <td className={`text-right font-mono tabular-nums ${pnlColor(w.total_pnl)}`}>
                      {fmtDollar(w.total_pnl)}
                    </td>
                  </tr>
                ))}
              </DataTable>
            )}
          </div>
        </Panel>
      )}

      {!result && !multi && (
        <Panel dense>
          <EmptyState title="No run yet"
                      hint={`Configure a window and run ${strategy.name} on ${ticker}.`} />
        </Panel>
      )}
    </div>
  );
}
