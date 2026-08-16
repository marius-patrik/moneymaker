import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { Loader2, ArrowRight, Activity } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, Cell, XAxis, YAxis, Tooltip,
         ResponsiveContainer, ReferenceLine } from "recharts";
import { Panel, Stat, DataTable } from "@/components/terminal/Panel";
import { Badge } from "@/components/ui/badge";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { api, type LiveStatus, type Stats, type SessionEntry, type EquityPoint,
         type PnlDistribution } from "@/lib/api";
import { fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

function tone(n: number | null | undefined) {
  if (n == null || n === 0) return "neutral" as const;
  return n > 0 ? ("profit" as const) : ("loss" as const);
}

export function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [dist, setDist] = useState<PnlDistribution | null>(null);
  const [sessions, setSessions] = useState<SessionEntry[]>([]);
  const [liveIds, setLiveIds] = useState<string[]>([]);
  const [liveStatuses, setLiveStatuses] = useState<Record<string, LiveStatus>>({});

  useEffect(() => {
    api.stats.get().then(setStats).catch(() => {});
    api.stats.equity().then((r) => setEquity(r.points)).catch(() => {});
    api.stats.distribution().then(setDist).catch(() => {});
    api.sessions.list().then((r) => setSessions(r.sessions)).catch(() => {});
    api.live.list().then((r) => setLiveIds(r.session_ids)).catch(() => {});
  }, []);

  useEffect(() => {
    liveIds.forEach((id) =>
      api.live.status(id)
        .then((s) => setLiveStatuses((p) => ({ ...p, [id]: s })))
        .catch(() => {}));
  }, [liveIds]);

  if (!stats) {
    return (
      <div className="flex items-center gap-2 p-4 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }

  const pnl = stats.total_pnl;
  const chartColor = pnl >= 0 ? "hsl(var(--profit))" : "hsl(var(--loss))";

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="space-y-3 p-3 pb-8 sm:p-4">
      {/* performance summary — one panel, not eight floating tiles */}
      <Panel title="Performance">
        <div className="grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4 xl:grid-cols-8">
          <Stat label="Net P&L" value={fmtDollar(pnl)} tone={tone(pnl)}
                sub={`${stats.trades} trades`} />
          <Stat label="Win rate" value={stats.win_rate != null ? fmtPct(stats.win_rate) : "—"}
                sub={`${stats.wins}W / ${stats.losses}L`} />
          <Stat label="Profit factor"
                value={stats.profit_factor != null ? stats.profit_factor.toFixed(2) : "—"}
                tone={stats.profit_factor == null ? "neutral"
                      : stats.profit_factor >= 1 ? "profit" : "loss"}
                sub="win / loss" />
          <Stat label="Equity" value={fmtDollar(stats.total_balance)}
                sub={`${stats.accounts} accounts`} />
          <Stat label="Avg win" value={fmtDollar(stats.avg_win)} tone="profit" />
          <Stat label="Avg loss" value={fmtDollar(stats.avg_loss)} tone="loss" />
          <Stat label="Best" value={stats.best_trade != null ? fmtDollar(stats.best_trade) : "—"}
                tone="profit" />
          <Stat label="Worst" value={stats.worst_trade != null ? fmtDollar(stats.worst_trade) : "—"}
                tone="loss" />
        </div>
      </Panel>

      {/* equity curve */}
      {equity.length > 1 && (
        <Panel title="Equity curve"
               actions={<span className="font-mono text-[10px] text-muted-foreground">
                 {stats.trades} trades
               </span>}>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equity} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={chartColor} stopOpacity={0.26} />
                    <stop offset="100%" stopColor={chartColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="i" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                       axisLine={false} tickLine={false} minTickGap={48} />
                <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                       axisLine={false} tickLine={false} width={52}
                       tickFormatter={(v: number) => `${Math.round(v / 1000)}k`} />
                <ReferenceLine y={0} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                <Tooltip formatter={(v: number) => [fmtDollar(v), "Equity"]}
                         labelFormatter={(_, pl) => (pl?.[0]?.payload as EquityPoint)?.t ?? ""}
                         contentStyle={{ background: "hsl(var(--popover))",
                                         border: "1px solid hsl(var(--border))",
                                         borderRadius: 10, fontSize: 11 }} />
                <Area type="monotone" dataKey="equity" stroke={chartColor}
                      strokeWidth={1.6} fill="url(#eq)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      )}

      {/* where the P&L actually comes from */}
      {dist && dist.trades > 0 && (
        <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Panel title="Trade P&L distribution"
                 actions={<span className="font-mono text-[10px] text-muted-foreground">
                   {dist.trades} trades</span>}>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={dist.buckets} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <XAxis dataKey="mid" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                         axisLine={false} tickLine={false} minTickGap={28}
                         tickFormatter={(v: number) => fmtDollar(v).replace(".00", "")} />
                  <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                         axisLine={false} tickLine={false} width={32} allowDecimals={false} />
                  <ReferenceLine x={0} stroke="hsl(var(--border))" />
                  <Tooltip
                    cursor={{ fill: "hsl(var(--accent) / 0.4)" }}
                    formatter={(v: number, _n, p) => [
                      `${v} trades · ${fmtDollar((p?.payload as { pnl: number })?.pnl ?? 0)}`, "Bucket"]}
                    labelFormatter={(v: number) => `around ${fmtDollar(v)}`}
                    contentStyle={{ background: "hsl(var(--popover))",
                                    border: "1px solid hsl(var(--border))",
                                    borderRadius: 10, fontSize: 11 }} />
                  <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                    {dist.buckets.map((b, i) => (
                      <Cell key={i} fill={b.mid >= 0 ? "hsl(var(--profit))" : "hsl(var(--loss))"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Composition">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Gross profit" value={fmtDollar(dist.gross_win)} tone="profit"
                      sub={`${dist.wins} winners`} />
                <Stat label="Gross loss" value={fmtDollar(dist.gross_loss)} tone="loss"
                      sub={`${dist.losses} losers`} />
              </div>
              {/* One bar showing how much of the gross each side accounts for. */}
              <div>
                <div className="mb-1.5 flex h-2.5 overflow-hidden rounded-full bg-muted">
                  <div className="bg-profit" style={{
                    width: `${(dist.gross_win / (dist.gross_win + Math.abs(dist.gross_loss) || 1)) * 100}%` }} />
                  <div className="bg-loss" style={{
                    width: `${(Math.abs(dist.gross_loss) / (dist.gross_win + Math.abs(dist.gross_loss) || 1)) * 100}%` }} />
                </div>
                <div className="flex justify-between text-[10px] text-muted-foreground">
                  <span>{fmtPct(dist.wins / dist.trades)} of trades win</span>
                  <span>net {fmtDollar(dist.gross_win + dist.gross_loss)}</span>
                </div>
              </div>
            </div>
          </Panel>
        </div>
      )}

      <div className="grid gap-3 xl:grid-cols-2">
        {/* live */}
        <Panel title="Live positions" dense>
          {liveIds.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">
              Nothing running. Launch from <Link to="/terminal" className="underline">Trade</Link>.
            </p>
          ) : (
            <DataTable head={<><th>Strategy</th><th>Status</th><th className="!text-right">Trades</th><th className="!text-right">P&L</th></>}>
              {liveIds.map((id) => {
                const s = liveStatuses[id];
                return (
                  <tr key={id}>
                    <td className="font-mono">{id}</td>
                    <td>
                      <span className="flex items-center gap-1.5">
                        <AnimatedIcon icon={Activity} active className="h-3 w-3 text-primary" />
                        <Badge variant="secondary" className="text-[10px]">
                          {s?.running ? "running" : "stopped"}
                        </Badge>
                      </span>
                    </td>
                    <td className="text-right tabular-nums">{s?.trade_count ?? "—"}</td>
                    <td className={`text-right font-mono tabular-nums ${pnlColor(s?.total_pnl ?? 0)}`}>
                      {s ? fmtDollar(s.total_pnl) : "—"}
                    </td>
                  </tr>
                );
              })}
            </DataTable>
          )}
        </Panel>

        {/* recent runs */}
        <Panel title="Recent activity" dense
               actions={
                 <Link to="/portfolio"
                       className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground">
                   All <ArrowRight className="h-3 w-3" />
                 </Link>}>
          {sessions.length === 0 ? (
            <p className="px-3 py-6 text-center text-xs text-muted-foreground">No activity yet.</p>
          ) : (
            <DataTable head={<><th>Run</th><th className="!text-right">Trades</th><th className="!text-right">P&L</th></>}>
              {sessions.slice(0, 7).map((s) => (
                <tr key={s.name}>
                  <td className="max-w-0 truncate font-mono" title={s.name}>{s.name}</td>
                  <td className="text-right tabular-nums text-muted-foreground">{s.trades ?? "—"}</td>
                  <td className={`text-right font-mono tabular-nums ${pnlColor(s.total_pnl)}`}>
                    {s.total_pnl != null ? fmtDollar(s.total_pnl) : "—"}
                  </td>
                </tr>
              ))}
            </DataTable>
          )}
        </Panel>
      </div>
    </motion.div>
  );
}
