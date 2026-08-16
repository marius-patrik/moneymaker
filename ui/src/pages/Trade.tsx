import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Activity, StopCircle, Loader2, RefreshCw, CandlestickChart,
  ArrowUpRight, ArrowDownRight, Zap, Play, DollarSign,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AnimatedIcon, MotionHost } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { api, type LiveStatus, type Strategy, type Account } from "@/lib/api";
import { fmt, fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

// -------------------------------------------------------- manual ticket

function OrderTicket({ accounts }: { accounts: Account[] }) {
  const { toast } = useToast();
  const [form, setForm] = useState({ ticker: "GC=F", size: "1", account_id: "" });
  const [quote, setQuote] = useState<{ price: number; time: string } | null>(null);
  const [quoting, setQuoting] = useState(false);
  const [placing, setPlacing] = useState<"long" | "short" | null>(null);

  useEffect(() => {
    if (!form.account_id && accounts[0]) {
      setForm((f) => ({ ...f, account_id: accounts[0].account_id }));
    }
  }, [accounts]);

  async function refreshQuote() {
    if (!form.ticker) return;
    setQuoting(true);
    try {
      const q = await api.orders.quote(form.ticker);
      setQuote({ price: q.price, time: q.time });
    } catch (e) {
      setQuote(null);
      toast(e instanceof Error ? e.message : "Quote failed", "error");
    }
    setQuoting(false);
  }

  async function place(direction: "long" | "short") {
    setPlacing(direction);
    try {
      const r = await api.orders.place({
        ticker: form.ticker, direction, size: Number(form.size),
        account_id: form.account_id || undefined,
      });
      toast(`${direction === "long" ? "Bought" : "Sold"} ${r.size} ${r.ticker} @ ${fmt(r.fill_price)}`,
            "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Order rejected", "error");
    }
    setPlacing(null);
  }

  const notional = quote ? quote.price * Number(form.size || 0) : null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Order ticket</CardTitle>
        <CardDescription>
          Place a single order by hand. Paper accounts only — the simulated
          provider is the only one wired for execution.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2">
          <Field label="Ticker" value={form.ticker} mono
                 onValueChange={(v) => { setForm((f) => ({ ...f, ticker: v })); setQuote(null); }} />
          <Field label="Size" type="number" value={form.size}
                 onValueChange={(v) => setForm((f) => ({ ...f, size: v }))} />
        </div>

        <div className="space-y-1">
          <Label htmlFor="ticket-account" className="text-xs">Account</Label>
          <Select value={form.account_id}
                  onValueChange={(v) => setForm((f) => ({ ...f, account_id: v }))}>
            <SelectTrigger id="ticket-account" className="h-8 text-sm">
              <SelectValue placeholder="Select account" />
            </SelectTrigger>
            <SelectContent>
              {accounts.map((a) => (
                <SelectItem key={a.account_id} value={a.account_id}>
                  {a.name} · {fmtDollar(a.balance)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* quote strip */}
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Last price</div>
            <div className="font-mono text-lg font-bold tabular-nums">
              {quote ? fmt(quote.price) : "—"}
            </div>
            {notional != null && (
              <div className="text-[11px] text-muted-foreground">
                notional {fmtDollar(notional)}
              </div>
            )}
          </div>
          <MotionHost>
            <Button size="sm" variant="outline" onClick={refreshQuote} disabled={quoting}>
              {quoting ? <Loader2 className="h-4 w-4 animate-spin" />
                       : <AnimatedIcon icon={RefreshCw} motionType="spin" className="h-4 w-4" />}
              Quote
            </Button>
          </MotionHost>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <MotionHost>
            <Button className="w-full bg-profit text-white hover:bg-profit/90"
                    onClick={() => place("long")} disabled={!!placing || !form.ticker}>
              {placing === "long" ? <Loader2 className="h-4 w-4 animate-spin" />
                                  : <AnimatedIcon icon={ArrowUpRight} motionType="lift" className="h-4 w-4" />}
              Buy / Long
            </Button>
          </MotionHost>
          <MotionHost>
            <Button className="w-full bg-loss text-white hover:bg-loss/90"
                    onClick={() => place("short")} disabled={!!placing || !form.ticker}>
              {placing === "short" ? <Loader2 className="h-4 w-4 animate-spin" />
                                   : <AnimatedIcon icon={ArrowDownRight} motionType="lift" className="h-4 w-4" />}
              Sell / Short
            </Button>
          </MotionHost>
        </div>
      </CardContent>
    </Card>
  );
}

// ------------------------------------------------------ strategy launch

function LaunchPanel({ strategies, onLaunched }: {
  strategies: Strategy[]; onLaunched: (id: string) => void;
}) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    strategy: "", ticker: "GC=F", end_time: "16:00", poll_seconds: "30",
  });
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (!form.strategy && strategies[0]) {
      setForm((f) => ({ ...f, strategy: strategies[0].name }));
    }
  }, [strategies]);

  async function start() {
    setStarting(true);
    try {
      const r = await api.live.start({
        strategy: form.strategy, ticker: form.ticker,
        end_time: form.end_time, poll_seconds: Number(form.poll_seconds),
      });
      onLaunched(r.session_id);
      toast(`${form.strategy} live on ${form.ticker}`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Launch failed", "error");
    }
    setStarting(false);
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Run a strategy</CardTitle>
        <CardDescription>
          Hands the ticker to a strategy, which then manages entries and exits
          on its own until the end time.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:grid-cols-4">
          <div className="space-y-1">
            <Label htmlFor="launch-strategy" className="text-xs">Strategy</Label>
            <Select value={form.strategy}
                    onValueChange={(v) => setForm((f) => ({ ...f, strategy: v }))}>
              <SelectTrigger id="launch-strategy" className="h-8 text-sm">
                <SelectValue placeholder="Select" />
              </SelectTrigger>
              <SelectContent>
                {strategies.map((s) => (
                  <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Field label="Ticker" value={form.ticker} mono
                 onValueChange={(v) => setForm((f) => ({ ...f, ticker: v }))} />
          <Field label="End time" value={form.end_time}
                 onValueChange={(v) => setForm((f) => ({ ...f, end_time: v }))} />
          <Field label="Poll (s)" type="number" value={form.poll_seconds}
                 onValueChange={(v) => setForm((f) => ({ ...f, poll_seconds: v }))} />
        </div>
        <MotionHost>
          <Button onClick={start} disabled={starting || !form.strategy}
                  className="w-full sm:w-auto">
            {starting ? <Loader2 className="h-4 w-4 animate-spin" />
                      : <AnimatedIcon icon={Play} motionType="nudge" className="h-4 w-4" />}
            {starting ? "Starting…" : "Go live"}
          </Button>
        </MotionHost>
      </CardContent>
    </Card>
  );
}

// ----------------------------------------------------------- positions

function PositionCard({ id, onStopped }: { id: string; onStopped: () => void }) {
  const { toast } = useToast();
  const [s, setS] = useState<LiveStatus | null>(null);
  const [stopping, setStopping] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    const tick = () => api.live.status(id).then(setS).catch(() => {});
    tick();
    timer.current = setInterval(tick, 3000);
    return () => clearInterval(timer.current);
  }, [id]);

  async function stop() {
    setStopping(true);
    try {
      await api.live.stop(id);
      toast(`Stopped ${id}`, "success");
      onStopped();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Stop failed", "error");
    }
    setStopping(false);
  }

  const long = s?.direction === "long";
  const open = !!s?.position_open;

  return (
    <motion.div layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97 }}>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <AnimatedIcon icon={Activity} active={s?.running} className="h-4 w-4 text-primary" />
              <span className="truncate font-mono text-sm font-medium">{id}</span>
              <Badge variant={s?.running ? "secondary" : "outline"}>
                {s?.running ? "running" : "stopped"}
              </Badge>
              {open && (
                <Badge variant={long ? "profit" : "loss"} className="gap-1">
                  {long ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                  {s?.direction}
                </Badge>
              )}
            </div>
            <MotionHost>
              <Button size="sm" variant="destructive" onClick={stop} disabled={stopping}>
                {stopping ? <Loader2 className="h-4 w-4 animate-spin" />
                          : <AnimatedIcon icon={StopCircle} motionType="shake" className="h-4 w-4" />}
                Stop
              </Button>
            </MotionHost>
          </div>
        </CardHeader>

        {s && (
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { l: "Realised", v: fmtDollar(s.total_pnl), c: pnlColor(s.total_pnl) },
                { l: "Open P&L", v: fmtDollar(s.open_pnl ?? 0), c: pnlColor(s.open_pnl ?? 0) },
                { l: "Trades", v: String(s.trade_count) },
                { l: "Win rate", v: s.win_rate != null ? fmtPct(s.win_rate) : "—" },
              ].map(({ l, v, c }) => (
                <div key={l}>
                  <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{l}</div>
                  <div className={`text-sm font-semibold tabular-nums ${c ?? ""}`}>{v}</div>
                </div>
              ))}
            </div>

            {open && (
              <div className="grid grid-cols-2 gap-3 rounded-lg border p-3 sm:grid-cols-4">
                {[
                  { l: "Entry", v: s.entry_price != null ? fmt(s.entry_price) : "—" },
                  { l: "Last", v: s.last_price != null ? fmt(s.last_price) : "—" },
                  { l: "Stop", v: s.stop_price != null ? fmt(s.stop_price) : "—" },
                  { l: "Target", v: s.target_price != null ? fmt(s.target_price) : "—" },
                ].map(({ l, v }) => (
                  <div key={l}>
                    <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{l}</div>
                    <div className="font-mono text-sm tabular-nums">{v}</div>
                  </div>
                ))}
              </div>
            )}

            <div className="text-[11px] text-muted-foreground">
              {s.bars_seen} bars · updates every 3s
            </div>
          </CardContent>
        )}
      </Card>
    </motion.div>
  );
}

// ---------------------------------------------------------------- page

export function Trade() {
  const [ids, setIds] = useState<string[]>([]);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);

  const refresh = () => api.live.list().then((r) => setIds(r.session_ids)).catch(() => {});

  useEffect(() => {
    refresh();
    api.strategies.list().then((r) => setStrategies(r.strategies)).catch(() => {});
    api.accounts.list().then((r) => setAccounts(r.accounts)).catch(() => {});
    const t = setInterval(refresh, 10000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Trade</h1>
          <p className="text-sm text-muted-foreground">
            {ids.length === 0 ? "Nothing running" : `${ids.length} session${ids.length === 1 ? "" : "s"} running`}
          </p>
        </div>
        <MotionHost>
          <Button variant="ghost" size="sm" onClick={refresh} aria-label="Refresh sessions">
            <AnimatedIcon icon={RefreshCw} motionType="spin" className="h-4 w-4" />
          </Button>
        </MotionHost>
      </div>

      <Tabs defaultValue="manual">
        <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
          <TabsTrigger value="manual">Manual</TabsTrigger>
          <TabsTrigger value="strategy">Strategy</TabsTrigger>
          <TabsTrigger value="positions">
            Positions{ids.length > 0 ? ` (${ids.length})` : ""}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="manual" className="pt-4">
          <OrderTicket accounts={accounts} />
        </TabsContent>

        <TabsContent value="strategy" className="pt-4">
          <LaunchPanel strategies={strategies}
                       onLaunched={(id) => setIds((p) => [...p, id])} />
        </TabsContent>

        <TabsContent value="positions" className="space-y-3 pt-4">
          {ids.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <CandlestickChart className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
                <p className="text-sm font-medium">No open sessions</p>
                <p className="mx-auto mt-1 max-w-sm text-xs text-muted-foreground">
                  Place an order from the Manual tab, or hand a ticker to a strategy.
                </p>
              </CardContent>
            </Card>
          ) : (
            <AnimatePresence mode="popLayout">
              {ids.map((id) => (
                <PositionCard key={id} id={id}
                              onStopped={() => setIds((p) => p.filter((x) => x !== id))} />
              ))}
            </AnimatePresence>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
