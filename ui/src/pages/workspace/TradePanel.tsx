import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import {
  ArrowUpRight, ArrowDownRight, Loader2, Radio, StopCircle, Activity, RefreshCw,
} from "lucide-react";
import { Panel } from "@/components/terminal/Panel";
import { EmptyState, ErrorState } from "@/components/terminal/States";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { TickerSearch } from "@/components/terminal/TickerSearch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { useResource } from "@/lib/useResource";
import { api, type Strategy, type PriceHistory, type LiveStatus } from "@/lib/api";
import { fmt, fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

function Chart({ hist }: { hist: PriceHistory }) {
  const up = hist.change >= 0;
  const stroke = up ? "hsl(var(--profit))" : "hsl(var(--loss))";
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={hist.bars} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="wpx" x1="0" y1="0" x2="0" y2="1">
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
              fill="url(#wpx)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function Position({ id, onStopped }: { id: string; onStopped: () => void }) {
  const { toast } = useToast();
  const [s, setS] = useState<LiveStatus | null>(null);
  const [stopping, setStopping] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    const tick = () => api.live.status(id).then(setS).catch(() => {});
    tick(); timer.current = setInterval(tick, 3000);
    return () => clearInterval(timer.current);
  }, [id]);

  async function stop() {
    setStopping(true);
    try { await api.live.stop(id); toast(`Stopped ${id}`, "success"); onStopped(); }
    catch (e) { toast(e instanceof Error ? e.message : "Stop failed", "error"); }
    setStopping(false);
  }

  const open = !!s?.position_open;
  const long = s?.direction === "long";

  return (
    <motion.div layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="border-b last:border-b-0">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
        <span className="flex min-w-0 items-center gap-2">
          <AnimatedIcon icon={Activity} active={s?.running} className="h-3 w-3 text-primary" />
          <span className="truncate font-mono text-xs">{id}</span>
          {open && (
            <Badge variant={long ? "profit" : "loss"} className="gap-0.5 text-[10px]">
              {long ? <ArrowUpRight className="h-2.5 w-2.5" /> : <ArrowDownRight className="h-2.5 w-2.5" />}
              {s?.direction}
            </Badge>
          )}
        </span>
        <span className="flex items-center gap-3 font-mono text-xs tabular-nums">
          <span className={pnlColor(s?.total_pnl ?? 0)}>{s ? fmtDollar(s.total_pnl) : "—"}</span>
          <Button size="sm" variant="ghost" className="h-6 px-2" onClick={stop} disabled={stopping}>
            {stopping ? <Loader2 className="h-3 w-3 animate-spin" />
                      : <StopCircle className="h-3 w-3 text-destructive" />}
          </Button>
        </span>
      </div>
    </motion.div>
  );
}

export function TradePanel({
  strategy, ticker, onTicker,
}: { strategy: Strategy; ticker: string; onTicker: (t: string) => void }) {
  const { toast } = useToast();
  const [size, setSize] = useState("1");
  const [accountId, setAccountId] = useState("");
  const [placing, setPlacing] = useState<"long" | "short" | null>(null);
  const [golive, setGolive] = useState(false);
  const [liveIds, setLiveIds] = useState<string[]>([]);

  const accounts = useResource(() => api.accounts.list(), []);
  const hist = useResource(() => api.orders.history(ticker, "1h", 5), [ticker], { pollMs: 60000 });

  useEffect(() => { api.live.list().then((r) => setLiveIds(r.session_ids)).catch(() => {}); }, []);
  useEffect(() => {
    const list = accounts.data?.accounts ?? [];
    if (!accountId && list[0]) setAccountId(list[0].account_id);
  }, [accounts.data, accountId]);

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

  async function goLive() {
    if (!window.confirm(`Run ${strategy.name} live on ${ticker}?\n\nIt trades a paper account until the session ends.`))
      return;
    setGolive(true);
    try {
      const r = await api.live.start({ strategy: strategy.name, ticker });
      setLiveIds((p) => [...p, r.session_id]);
      toast(`${strategy.name} live on ${ticker}`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not go live", "error");
    }
    setGolive(false);
  }

  const h = hist.data;
  const last = h?.last ?? null;
  const up = (h?.change ?? 0) >= 0;
  const acct = (accounts.data?.accounts ?? []).find((a) => a.account_id === accountId);
  const notional = last != null ? last * Number(size || 0) : null;

  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-3">
        <Panel title={ticker}
               actions={<span className="font-mono text-[10px] text-muted-foreground">1h · 5d</span>}>
          <div className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-[26px] font-semibold tabular-nums tracking-tight">
                  {last != null ? fmt(last) : "—"}
                </span>
                {h && h.bars.length > 1 && (
                  <span className={`font-mono text-sm font-medium tabular-nums ${up ? "text-profit" : "text-loss"}`}>
                    {up ? "+" : ""}{fmt(h.change)} ({fmtPct(h.change_pct)})
                  </span>
                )}
              </div>
              <div className="flex gap-4 font-mono text-[11px] tabular-nums text-muted-foreground">
                <span>H {h?.high != null ? fmt(h.high) : "—"}</span>
                <span>L {h?.low != null ? fmt(h.low) : "—"}</span>
              </div>
            </div>
            <div className="h-72">
              {hist.error ? <ErrorState message={hist.error} onRetry={hist.reload} />
                : !hist.settled ? <div className="flex h-full items-center justify-center">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>
                : h && h.bars.length > 1 ? <Chart hist={h} />
                : <EmptyState title="No price data" hint={`Nothing returned for ${ticker}.`} />}
            </div>
          </div>
        </Panel>

        <Panel title={liveIds.length ? `${liveIds.length} running` : "Running"} dense>
          {liveIds.length === 0
            ? <EmptyState title="Nothing running"
                          hint={`Start ${strategy.name} on ${ticker} with Go live.`} />
            : <AnimatePresence mode="popLayout">
                {liveIds.map((id) => (
                  <Position key={id} id={id}
                            onStopped={() => setLiveIds((p) => p.filter((x) => x !== id))} />
                ))}
              </AnimatePresence>}
        </Panel>
      </div>

      <Panel title="Ticket">
        <div className="space-y-3">
          <div className="space-y-1">
            <Label className="text-xs">Instrument</Label>
            <TickerSearch value={ticker} onSelect={onTicker} />
          </div>
          <Field label="Size" type="number" value={size} onValueChange={setSize} />
          <div className="space-y-1">
            <Label htmlFor="ws-account" className="text-xs">Account</Label>
            <Select value={accountId} onValueChange={setAccountId}>
              <SelectTrigger id="ws-account" className="h-8 text-sm">
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

          <div className="border-t pt-3">
            <Button variant="outline" className="w-full border-profit/40 text-profit hover:bg-profit/10"
                    onClick={goLive} disabled={golive}>
              {golive ? <Loader2 className="h-4 w-4 animate-spin" />
                : <AnimatedIcon icon={Radio} motionType="pulse" className="h-4 w-4" />}
              Go live with {strategy.name}
            </Button>
          </div>
        </div>
      </Panel>
    </div>
  );
}
