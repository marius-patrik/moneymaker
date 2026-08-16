import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Zap, ChevronDown, Play, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StrategyFlow } from "@/components/StrategyFlow";
import { api, type Strategy, type BacktestResult } from "@/lib/api";
import { fmtDollar, pnlColor } from "@/lib/utils";

function StrategyCard({ s }: { s: Strategy }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ ticker: "ES=F", start: "2026-01-01", end: "2026-08-01", interval: "5m" });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runBacktest() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.backtest.run({ strategy: s.name, ...form });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <motion.div layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="overflow-hidden">
        <CardHeader
          className="cursor-pointer select-none"
          onClick={() => setOpen((v) => !v)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">{s.name}</CardTitle>
              <Badge variant={s.source === "built-in" ? "secondary" : "outline"}>{s.source}</Badge>
            </div>
            <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            </motion.div>
          </div>
          <CardDescription>{s.doc}</CardDescription>
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

                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[
                    { label: "Ticker", key: "ticker" as const, placeholder: "ES=F" },
                    { label: "Start", key: "start" as const, placeholder: "2026-01-01" },
                    { label: "End", key: "end" as const, placeholder: "2026-08-01" },
                    { label: "Interval", key: "interval" as const, placeholder: "5m" },
                  ].map(({ label, key, placeholder }) => (
                    <div key={key} className="space-y-1">
                      <Label className="text-xs">{label}</Label>
                      <Input
                        value={form[key]}
                        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                        placeholder={placeholder}
                        className="h-8 text-sm"
                      />
                    </div>
                  ))}
                </div>

                <Button size="sm" onClick={runBacktest} disabled={loading} className="w-full">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  {loading ? "Running…" : "Run Backtest"}
                </Button>

                {error && (
                  <p className="text-xs text-destructive bg-destructive/10 rounded px-3 py-2">{error}</p>
                )}

                {result && (
                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid grid-cols-3 gap-3">
                    {[
                      { label: "P&L", value: fmtDollar(result.total_pnl), color: pnlColor(result.total_pnl) },
                      { label: "Trades", value: String(result.trade_count ?? "—") },
                      { label: "Win Rate", value: result.win_rate != null ? (result.win_rate * 100).toFixed(1) + "%" : "—" },
                    ].map(({ label, value, color }) => (
                      <Card key={label}>
                        <CardContent className="pt-3 pb-3 text-center">
                          <div className="text-xs text-muted-foreground mb-1">{label}</div>
                          <div className={`text-sm font-bold ${color ?? ""}`}>{value}</div>
                        </CardContent>
                      </Card>
                    ))}
                    <div className="col-span-3 text-xs text-muted-foreground font-mono">{result.session_name}</div>
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.strategies.list().then((r) => { setStrategies(r.strategies); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Strategies</h1>
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</div>
      ) : (
        <div className="space-y-3">
          {strategies.map((s) => <StrategyCard key={s.name} s={s} />)}
        </div>
      )}
    </div>
  );
}
