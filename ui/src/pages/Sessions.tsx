import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { FileText, ChevronRight, Loader2, ArrowLeft } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { api, type Trade } from "@/lib/api";
import { fmtDollar, pnlColor } from "@/lib/utils";

function PnlChart({ trades }: { trades: Trade[] }) {
  const data = trades
    .filter((t) => t.pnl && t.pnl !== "")
    .map((t, i) => ({ i: i + 1, pnl: parseFloat(t.pnl), balance: parseFloat(t.balance) }));

  if (data.length === 0) return null;

  const runningPnl = data.map((d, i) => ({
    i: d.i,
    cumPnl: data.slice(0, i + 1).reduce((s, x) => s + x.pnl, 0),
    balance: d.balance,
  }));

  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={runningPnl} margin={{ left: 4, right: 4, top: 4, bottom: 4 }}>
          <XAxis dataKey="i" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            formatter={(value: number) => [fmtDollar(value)]}
            contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }}
          />
          <ReferenceLine y={0} stroke="hsl(var(--border))" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="cumPnl" stroke="hsl(142 76% 36%)" strokeWidth={2} dot={false} name="Cum. P&L" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Sessions() {
  const [sessions, setSessions] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.sessions.list().then((r) => setSessions(r.sessions)).catch(() => {});
  }, []);

  async function open(filename: string) {
    setSelected(filename);
    setLoading(true);
    try {
      const r = await api.sessions.get(filename);
      setTrades(("trades" in r ? r.trades : []) as Trade[]);
    } catch {}
    setLoading(false);
  }

  const totalPnl = trades.reduce((s, t) => s + (parseFloat(t.pnl) || 0), 0);
  const wins = trades.filter((t) => parseFloat(t.pnl) > 0).length;
  const winRate = trades.length > 0 ? wins / trades.length : 0;

  if (selected) {
    return (
      <div className="space-y-4 p-4 sm:p-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => { setSelected(null); setTrades([]); }}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="min-w-0 truncate font-mono text-sm font-bold sm:text-base">{selected}</h1>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading…</div>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-2 sm:gap-3">
              {[
                { label: "Total P&L", value: fmtDollar(totalPnl), color: pnlColor(totalPnl) },
                { label: "Trades", value: String(trades.length) },
                { label: "Win Rate", value: (winRate * 100).toFixed(1) + "%" },
              ].map(({ label, value, color }) => (
                <Card key={label}>
                  <CardContent className="pt-4 pb-3 text-center">
                    <div className="text-xs text-muted-foreground mb-1">{label}</div>
                    <div className={`text-lg font-bold ${color ?? ""}`}>{value}</div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Cumulative P&L</CardTitle></CardHeader>
              <CardContent><PnlChart trades={trades} /></CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Trades</CardTitle></CardHeader>
              <ScrollArea className="h-72">
                <table className="w-full min-w-[520px] text-xs">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="text-left py-2 px-3">Time</th>
                      <th className="text-left py-2 px-3">Side</th>
                      <th className="text-right py-2 px-3">Price</th>
                      <th className="text-right py-2 px-3">Qty</th>
                      <th className="text-right py-2 px-3">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((t, i) => (
                      <tr key={i} className="border-b border-border/50 hover:bg-accent/30">
                        <td className="py-1.5 px-3 font-mono text-muted-foreground">{t.timestamp?.slice(0, 19) ?? "—"}</td>
                        <td className="py-1.5 px-3">
                          <Badge variant={t.side === "buy" ? "profit" : "loss"} className="text-xs px-1.5 py-0">{t.side}</Badge>
                        </td>
                        <td className="py-1.5 px-3 text-right font-mono">{t.price}</td>
                        <td className="py-1.5 px-3 text-right">{t.qty}</td>
                        <td className={`py-1.5 px-3 text-right font-semibold ${pnlColor(parseFloat(t.pnl) || 0)}`}>{t.pnl !== "" ? fmtDollar(parseFloat(t.pnl)) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollArea>
            </Card>
          </>
        )}
      </div>
    );
  }

  const visible = [...sessions].reverse().filter((s) =>
    s.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Sessions</h1>
          <p className="text-sm text-muted-foreground">
            {visible.length} of {sessions.length} recorded runs
          </p>
        </div>
        <Input value={filter} onChange={(e) => setFilter(e.target.value)}
               placeholder="Filter sessions…" className="h-8 w-full text-sm sm:max-w-56" />
      </div>
      {visible.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          {sessions.length === 0
            ? "No sessions yet. Run a backtest to see results here."
            : `No sessions match “${filter}”.`}
        </p>
      ) : (
        <div className="space-y-1">
          {visible.map((s) => (
            <motion.div key={s} whileHover={{ x: 2 }}>
              <button
                onClick={() => open(s)}
                className="w-full flex items-center justify-between rounded-md px-3 py-2.5 text-sm hover:bg-accent transition-colors text-left"
              >
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span className="font-mono">{s}</span>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </button>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
