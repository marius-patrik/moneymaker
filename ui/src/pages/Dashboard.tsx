import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import {
  TrendingUp, TrendingDown, Activity, Wallet, FileText, Zap,
  Target, Scale, ArrowRight, Loader2, CandlestickChart, FlaskConical,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AnimatedIcon, MotionHost } from "@/components/ui/animated-icon";
import { api, type LiveStatus, type AppConfig, type Stats, type SessionEntry } from "@/lib/api";
import { fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.035 } }),
};

function StatCard({ title, value, sub, icon, i, color, motionType = "pulse" }: {
  title: string; value: string; sub?: string; icon: React.ElementType;
  i: number; color?: string; motionType?: "pulse" | "lift" | "draw" | "pop";
}) {
  return (
    <motion.div variants={fadeUp} initial="hidden" animate="show" custom={i}>
      <MotionHost>
        <Card className="transition-colors hover:bg-accent/20">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">{title}</CardTitle>
            <AnimatedIcon icon={icon} motionType={motionType} className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-xl font-bold tabular-nums sm:text-2xl ${color ?? ""}`}>{value}</div>
            {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
          </CardContent>
        </Card>
      </MotionHost>
    </motion.div>
  );
}

export function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [liveIds, setLiveIds] = useState<string[]>([]);
  const [liveStatuses, setLiveStatuses] = useState<Record<string, LiveStatus>>({});
  const [sessions, setSessions] = useState<SessionEntry[]>([]);

  useEffect(() => {
    api.stats.get().then(setStats).catch(() => {});
    api.config.get().then(setConfig).catch(() => {});
    api.live.list().then((r) => setLiveIds(r.session_ids)).catch(() => {});
    api.sessions.list().then((r) => setSessions(r.sessions)).catch(() => {});
  }, []);

  useEffect(() => {
    liveIds.forEach((id) => {
      api.live.status(id)
        .then((s) => setLiveStatuses((prev) => ({ ...prev, [id]: s })))
        .catch(() => {});
    });
  }, [liveIds]);

  if (!stats) {
    return (
      <div className="flex items-center gap-2 p-4 text-muted-foreground sm:p-6">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }

  const pnl = stats.total_pnl;

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {config ? `v${config.version} · ${stats.strategies} strategies · ${stats.sessions} sessions` : " "}
        </p>
      </div>

      {/* headline */}
      <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:gap-4 xl:grid-cols-4">
        <StatCard i={0} title="Total P&L" icon={pnl >= 0 ? TrendingUp : TrendingDown}
                  motionType="draw" value={fmtDollar(pnl)} color={pnlColor(pnl)}
                  sub={`across ${stats.trades} trades`} />
        <StatCard i={1} title="Win rate" icon={Target} motionType="pop"
                  value={stats.win_rate != null ? fmtPct(stats.win_rate) : "—"}
                  sub={`${stats.wins}W / ${stats.losses}L`} />
        <StatCard i={2} title="Profit factor" icon={Scale}
                  value={stats.profit_factor != null ? stats.profit_factor.toFixed(2) : "—"}
                  color={stats.profit_factor != null
                    ? (stats.profit_factor >= 1 ? "text-profit" : "text-loss") : undefined}
                  sub="gross win / gross loss" />
        <StatCard i={3} title="Balance" icon={Wallet} motionType="lift"
                  value={fmtDollar(stats.total_balance)}
                  sub={`${stats.accounts} account${stats.accounts === 1 ? "" : "s"}`} />
      </div>

      {/* trade quality */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard i={4} title="Avg win" icon={TrendingUp} value={fmtDollar(stats.avg_win)} color="text-profit" />
        <StatCard i={5} title="Avg loss" icon={TrendingDown} value={fmtDollar(stats.avg_loss)} color="text-loss" />
        <StatCard i={6} title="Best trade" icon={TrendingUp} color="text-profit"
                  value={stats.best_trade != null ? fmtDollar(stats.best_trade) : "—"} />
        <StatCard i={7} title="Worst trade" icon={TrendingDown} color="text-loss"
                  value={stats.worst_trade != null ? fmtDollar(stats.worst_trade) : "—"} />
      </div>

      {/* live */}
      {liveIds.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
          <h2 className="mb-3 text-lg font-semibold">Open positions</h2>
          <div className="space-y-2">
            {liveIds.map((id) => {
              const st = liveStatuses[id];
              return (
                <Card key={id}>
                  <CardContent className="flex flex-wrap items-center justify-between gap-2 py-4">
                    <div className="flex min-w-0 items-center gap-3">
                      <AnimatedIcon icon={Activity} active className="h-4 w-4 text-primary" />
                      <span className="truncate font-mono text-sm">{id}</span>
                      <Badge variant="secondary">{st?.running ? "running" : "stopped"}</Badge>
                    </div>
                    {st && (
                      <div className="flex gap-4 text-sm tabular-nums">
                        <span className="text-muted-foreground">{st.trade_count} trades</span>
                        <span className={pnlColor(st.total_pnl)}>{fmtDollar(st.total_pnl)}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* recent sessions with results */}
      {sessions.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent sessions</h2>
            <Link to="/accounts" className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <Card>
            <CardContent className="divide-y p-0">
              {sessions.slice(0, 6).map((s) => (
                <Link key={s.name} to="/accounts"
                      className="flex items-center justify-between gap-3 px-4 py-2.5 transition-colors hover:bg-accent/40">
                  <div className="flex min-w-0 items-center gap-2">
                    <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate font-mono text-xs" title={s.name}>{s.name}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 text-xs tabular-nums">
                    {s.trades != null && <span className="text-muted-foreground">{s.trades}t</span>}
                    {s.total_pnl != null && (
                      <span className={`font-semibold ${pnlColor(s.total_pnl)}`}>{fmtDollar(s.total_pnl)}</span>
                    )}
                  </div>
                </Link>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* quick links */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {([
          { to: "/strategies", icon: Zap, label: "Strategies", m: "pop" },
          { to: "/research", icon: FlaskConical, label: "Research", m: "wiggle" },
          { to: "/trade", icon: CandlestickChart, label: "Trade", m: "draw" },
          { to: "/accounts", icon: Wallet, label: "Accounts", m: "lift" },
        ] as const).map(({ to, icon, label, m }) => (
          <Link key={to} to={to}>
            <MotionHost>
              <Card className="transition-colors hover:bg-accent/40">
                <CardContent className="flex items-center gap-2 py-3">
                  <AnimatedIcon icon={icon} motionType={m} className="h-4 w-4 text-primary" />
                  <span className="truncate text-sm font-medium">{label}</span>
                </CardContent>
              </Card>
            </MotionHost>
          </Link>
        ))}
      </div>
    </div>
  );
}
