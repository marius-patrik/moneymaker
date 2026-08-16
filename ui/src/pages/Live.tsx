import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Activity, StopCircle, Play, Loader2, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, type Strategy, type LiveStatus } from "@/lib/api";
import { fmtDollar, pnlColor } from "@/lib/utils";

function SessionCard({ id, onStop }: { id: string; onStop: () => void }) {
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [stopping, setStopping] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    const fetch = () => api.live.status(id).then(setStatus).catch(() => {});
    fetch();
    timerRef.current = setInterval(fetch, 3000);
    return () => clearInterval(timerRef.current);
  }, [id]);

  async function stop() {
    setStopping(true);
    try { await api.live.stop(id); onStop(); } catch {}
    setStopping(false);
  }

  return (
    <motion.div initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 8 }}>
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary animate-pulse" />
              <span className="font-mono text-sm font-medium">{id}</span>
              <Badge variant={status?.running ? "secondary" : "outline"}>
                {status?.running ? "running" : "stopped"}
              </Badge>
            </div>
            <Button size="sm" variant="destructive" onClick={stop} disabled={stopping}>
              {stopping ? <Loader2 className="h-4 w-4 animate-spin" /> : <StopCircle className="h-4 w-4" />}
              Stop
            </Button>
          </div>
        </CardHeader>
        {status && (
          <CardContent>
            <div className="grid grid-cols-4 gap-4 text-sm">
              {[
                { label: "Trades", value: String(status.trade_count) },
                { label: "Total P&L", value: fmtDollar(status.total_pnl), color: pnlColor(status.total_pnl) },
                { label: "Open P&L", value: fmtDollar(status.open_pnl ?? 0), color: pnlColor(status.open_pnl ?? 0) },
                { label: "Last Price", value: status.last_price != null ? fmtDollar(status.last_price) : "—" },
              ].map(({ label, value, color }) => (
                <div key={label}>
                  <div className="text-xs text-muted-foreground">{label}</div>
                  <div className={`font-semibold ${color ?? ""}`}>{value}</div>
                </div>
              ))}
            </div>
          </CardContent>
        )}
      </Card>
    </motion.div>
  );
}

export function Live() {
  const [liveIds, setLiveIds] = useState<string[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [form, setForm] = useState({ strategy: "", ticker: "ES=F", end_time: "11:00", poll_seconds: "30" });
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => api.live.list().then((r) => setLiveIds(r.session_ids)).catch(() => {});

  useEffect(() => {
    refresh();
    api.strategies.list().then((r) => {
      setStrategies(r.strategies);
      if (r.strategies[0]) setForm((f) => ({ ...f, strategy: r.strategies[0].name }));
    }).catch(() => {});
  }, []);

  async function start() {
    if (!form.strategy) return;
    setStarting(true);
    setError(null);
    try {
      const r = await api.live.start({ strategy: form.strategy, ticker: form.ticker, end_time: form.end_time, poll_seconds: Number(form.poll_seconds) });
      setLiveIds((prev) => [...prev, r.session_id]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Live Trading</h1>
        <Button variant="ghost" size="sm" onClick={refresh}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      {/* Start form */}
      <Card>
        <CardHeader><CardTitle className="text-base">Start a live session</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="space-y-1 col-span-2 sm:col-span-1">
              <Label className="text-xs">Strategy</Label>
              <Select value={form.strategy} onValueChange={(v) => setForm((f) => ({ ...f, strategy: v }))}>
                <SelectTrigger className="h-8 text-sm"><SelectValue placeholder="Select strategy" /></SelectTrigger>
                <SelectContent>
                  {strategies.map((s) => <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {[
              { label: "Ticker", key: "ticker" as const },
              { label: "End Time", key: "end_time" as const },
              { label: "Poll (s)", key: "poll_seconds" as const },
            ].map(({ label, key }) => (
              <div key={key} className="space-y-1">
                <Label className="text-xs">{label}</Label>
                <Input value={form[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} className="h-8 text-sm" />
              </div>
            ))}
          </div>
          <Button onClick={start} disabled={starting || !form.strategy} className="w-full sm:w-auto">
            {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {starting ? "Starting…" : "Start"}
          </Button>
          {error && <p className="text-xs text-destructive bg-destructive/10 rounded px-3 py-2">{error}</p>}
        </CardContent>
      </Card>

      {/* Active sessions */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold text-muted-foreground">
          {liveIds.length === 0 ? "No active sessions" : `${liveIds.length} active session${liveIds.length !== 1 ? "s" : ""}`}
        </h2>
        <AnimatePresence>
          {liveIds.map((id) => (
            <SessionCard key={id} id={id} onStop={() => setLiveIds((prev) => prev.filter((x) => x !== id))} />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
