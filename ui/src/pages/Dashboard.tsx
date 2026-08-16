import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { TrendingUp, TrendingDown, Activity, Layers, Wallet, FileText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type Account, type LiveStatus, type AppConfig } from "@/lib/api";
import { fmtDollar, pnlColor } from "@/lib/utils";

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.06 } }),
};

function StatCard({ title, value, sub, icon: Icon, i }: { title: string; value: string; sub?: string; icon: React.ElementType; i: number }) {
  return (
    <motion.div variants={fadeUp} initial="hidden" animate="show" custom={i}>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
          <Icon className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{value}</div>
          {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
        </CardContent>
      </Card>
    </motion.div>
  );
}

export function Dashboard() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [liveIds, setLiveIds] = useState<string[]>([]);
  const [liveStatuses, setLiveStatuses] = useState<Record<string, LiveStatus>>({});
  const [sessions, setSessions] = useState<string[]>([]);
  const [config, setConfig] = useState<AppConfig | null>(null);

  useEffect(() => {
    api.accounts.list().then((r) => setAccounts(r.accounts)).catch(() => {});
    api.live.list().then((r) => setLiveIds(r.session_ids)).catch(() => {});
    api.sessions.list().then((r) => setSessions(r.sessions)).catch(() => {});
    api.config.get().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    liveIds.forEach((id) => {
      api.live.status(id).then((s) => setLiveStatuses((prev) => ({ ...prev, [id]: s }))).catch(() => {});
    });
  }, [liveIds]);

  const totalBalance = accounts.reduce((s, a) => s + a.starting_balance, 0);
  const totalPnl = Object.values(liveStatuses).reduce((s, st) => s + (st.total_pnl ?? 0), 0);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          {config ? `moneymaker v${config.version} · ${config.home}` : " "}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard i={0} title="Accounts" value={String(accounts.length)} sub="registered" icon={Wallet} />
        <StatCard i={1} title="Total Balance" value={fmtDollar(totalBalance)} sub="across all accounts" icon={Layers} />
        <StatCard i={2} title="Sessions" value={String(sessions.length)} sub="recorded runs" icon={FileText} />
        <StatCard
          i={3}
          title={liveIds.length > 0 ? "Live P&L" : "Live Sessions"}
          value={liveIds.length > 0 ? fmtDollar(totalPnl) : "0"}
          sub={liveIds.length > 0 ? `${liveIds.length} running` : "none active"}
          icon={liveIds.length === 0 ? Activity : totalPnl >= 0 ? TrendingUp : TrendingDown}
        />
      </div>

      {liveIds.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
          <h2 className="text-lg font-semibold mb-3">Active Live Sessions</h2>
          <div className="space-y-2">
            {liveIds.map((id) => {
              const st = liveStatuses[id];
              return (
                <Card key={id}>
                  <CardContent className="flex items-center justify-between py-4">
                    <div className="flex items-center gap-3">
                      <Activity className="h-4 w-4 text-primary animate-pulse" />
                      <span className="font-mono text-sm">{id}</span>
                      <Badge variant="secondary">{st?.running ? "running" : "stopped"}</Badge>
                    </div>
                    {st && (
                      <div className="flex gap-6 text-sm">
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

      {sessions.length > 0 && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}>
          <h2 className="text-lg font-semibold mb-3">Recent Sessions</h2>
          <Card>
            <CardContent className="pt-4">
              <div className="space-y-1">
                {sessions.slice(-8).reverse().map((s) => (
                  <div key={s} className="flex items-center justify-between py-1 text-sm">
                    <span className="font-mono text-muted-foreground">{s}</span>
                    <Badge variant="outline">{s.endsWith(".csv") ? "trades" : "json"}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
