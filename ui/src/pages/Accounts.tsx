import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Wallet, Plus, Loader2, Trash2, Search, Sparkles, FileText,
  ChevronRight, ArrowLeft,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Panel, DataTable } from "@/components/terminal/Panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AnimatedIcon, MotionHost } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { api, type Account, type SessionEntry, type Trade } from "@/lib/api";
import { fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

// ------------------------------------------------------------- accounts

function CreateDialog({ onCreated }: { onCreated: (a: Account) => void }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", starting_balance: "10000" });
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    try {
      const a = await api.accounts.create({
        name: form.name, starting_balance: Number(form.starting_balance),
      });
      onCreated(a);
      toast(`Created ${a.name}`, "success");
      setOpen(false);
      setForm({ name: "", starting_balance: "10000" });
    } catch (e) {
      toast(e instanceof Error ? e.message : "Create failed", "error");
    }
    setLoading(false);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <MotionHost>
          <Button size="sm">
            <AnimatedIcon icon={Plus} motionType="pop" className="h-4 w-4" />
            New account
          </Button>
        </MotionHost>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Create account</DialogTitle></DialogHeader>
        <div className="space-y-3 pt-2">
          <Field label="Name" value={form.name} className="h-10" placeholder="my-account"
                 onValueChange={(v) => setForm((f) => ({ ...f, name: v }))} />
          <Field label="Starting balance (USD)" type="number" className="h-10"
                 value={form.starting_balance}
                 onValueChange={(v) => setForm((f) => ({ ...f, starting_balance: v }))} />
          <Button className="w-full" onClick={submit} disabled={loading || !form.name}>
            {loading && <Loader2 className="h-4 w-4 animate-spin" />} Create
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function AccountsPanel() {
  const { toast } = useToast();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [pruning, setPruning] = useState(false);
  const [limit, setLimit] = useState(24);

  useEffect(() => {
    api.accounts.list().then((r) => setAccounts(r.accounts)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return accounts.filter((a) =>
      a.name.toLowerCase().includes(q) || a.account_id.toLowerCase().includes(q));
  }, [accounts, query]);

  const shown = filtered.slice(0, limit);
  const total = filtered.reduce((s, a) => s + (a.balance ?? 0), 0);

  async function remove(a: Account) {
    setDeleting(a.account_id);
    try {
      await api.accounts.remove(a.account_id);
      setAccounts((p) => p.filter((x) => x.account_id !== a.account_id));
      toast(`Deleted ${a.name}`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Delete failed", "error");
    }
    setDeleting(null);
  }

  async function prune() {
    setPruning(true);
    try {
      const dry = await api.accounts.prune("mw_", true);
      if (dry.matched === 0) toast("No scratch accounts to prune.", "info");
      else if (window.confirm(`Delete ${dry.matched} scratch account(s) from older backtests?`)) {
        const r = await api.accounts.prune("mw_", false);
        setAccounts((p) => p.filter((a) => !a.name.startsWith("mw_")));
        toast(`Deleted ${r.deleted} scratch account(s)`, "success");
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : "Prune failed", "error");
    }
    setPruning(false);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <div className="relative min-w-0 flex-1 sm:flex-none">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} aria-label="Filter accounts"
                   onChange={(e) => { setQuery(e.target.value); setLimit(24); }}
                   placeholder="Filter…" className="h-8 w-full pl-8 text-sm sm:w-56" />
          </div>
          <MotionHost>
            <Button size="sm" variant="outline" onClick={prune} disabled={pruning}>
              {pruning ? <Loader2 className="h-4 w-4 animate-spin" />
                       : <AnimatedIcon icon={Sparkles} motionType="wiggle" className="h-4 w-4" />}
              Prune
            </Button>
          </MotionHost>
          <CreateDialog onCreated={(a) => setAccounts((p) => [...p, a])} />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {accounts.length === 0 ? "No accounts yet." : `No accounts match "${query}".`}
        </p>
      ) : (
        <Panel dense
               title={`${filtered.length} of ${accounts.length} accounts`}
               actions={<span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                 {fmtDollar(total)} combined</span>}>
          <DataTable head={<><th>Name</th><th>Provider</th><th>Currency</th>
                            <th className="!text-right">Balance</th><th className="w-8" /></>}>
            {shown.map((a) => (
              <tr key={a.account_id} className="group">
                <td>
                  <div className="flex items-center gap-2">
                    <Wallet className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <span className="font-medium">{a.name}</span>
                    {a.is_live && <Badge variant="destructive" className="text-[10px]">live</Badge>}
                  </div>
                  <div className="pl-5 font-mono text-[10px] text-muted-foreground">{a.account_id}</div>
                </td>
                <td className="text-muted-foreground">{a.provider}</td>
                <td className="text-muted-foreground">{a.currency}</td>
                <td className="text-right font-mono tabular-nums">{fmtDollar(a.balance)}</td>
                <td>
                  <button
                    onClick={() => remove(a)}
                    disabled={deleting === a.account_id}
                    aria-label={`Delete ${a.name}`}
                    className="rounded p-1 opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100"
                  >
                    {deleting === a.account_id
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Trash2 className="h-3.5 w-3.5 text-destructive" />}
                  </button>
                </td>
              </tr>
            ))}
          </DataTable>
          {filtered.length > shown.length && (
            <button onClick={() => setLimit((n) => n + 48)}
                    className="w-full border-t py-2 text-xs text-muted-foreground hover:bg-accent/40">
              Show {filtered.length - shown.length} more
            </button>
          )}
        </Panel>
      )}
    </div>
  );
}

// ------------------------------------------------------------- sessions

function PnlChart({ trades }: { trades: Trade[] }) {
  const rows = trades.filter((t) => t.pnl !== "" && t.pnl != null)
    .map((t, i) => ({ i: i + 1, pnl: parseFloat(t.pnl) }));
  if (!rows.length) return null;
  const cum = rows.map((d, i) => ({
    i: d.i, cumPnl: rows.slice(0, i + 1).reduce((s, x) => s + x.pnl, 0),
  }));
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={cum} margin={{ left: 4, right: 4, top: 4, bottom: 4 }}>
          <XAxis dataKey="i" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip formatter={(v: number) => [fmtDollar(v)]}
                   contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }} />
          <ReferenceLine y={0} stroke="hsl(var(--border))" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="cumPnl" stroke="hsl(142 76% 45%)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function SessionsPanel() {
  const [sessions, setSessions] = useState<SessionEntry[]>([]);
  const [selected, setSelected] = useState<SessionEntry | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.sessions.list().then((r) => setSessions(r.sessions)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  async function open(s: SessionEntry) {
    setSelected(s); setBusy(true);
    try {
      const r = await api.sessions.get(s.name);
      setTrades(("trades" in r ? r.trades : []) as Trade[]);
    } catch { setTrades([]); }
    setBusy(false);
  }

  const visible = sessions.filter((s) => s.name.toLowerCase().includes(filter.toLowerCase()));

  if (selected) {
    const pnl = selected.total_pnl ?? 0;
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => { setSelected(null); setTrades([]); }}
                  aria-label="Back to sessions">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h2 className="min-w-0 truncate font-mono text-sm font-bold">{selected.name}</h2>
        </div>

        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          {[
            { l: "Total P&L", v: fmtDollar(pnl), c: pnlColor(pnl) },
            { l: "Trades", v: String(selected.trades ?? trades.length) },
            { l: "Win rate", v: selected.win_rate != null ? fmtPct(selected.win_rate) : "—" },
          ].map(({ l, v, c }) => (
            <Card key={l}>
              <CardContent className="pb-3 pt-4 text-center">
                <div className="text-xs text-muted-foreground">{l}</div>
                <div className={`text-lg font-bold tabular-nums ${c ?? ""}`}>{v}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {busy ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading trades…
          </div>
        ) : (
          <>
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
                      <th className="px-3 py-2 text-left">Entry</th>
                      <th className="px-3 py-2 text-left">Dir</th>
                      <th className="px-3 py-2 text-right">Price</th>
                      <th className="px-3 py-2 text-right">Exit</th>
                      <th className="px-3 py-2 text-right">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((t, i) => {
                      const v = parseFloat(t.pnl) || 0;
                      return (
                        <tr key={i} className="border-b border-border/50 hover:bg-accent/30">
                          <td className="px-3 py-1.5 font-mono text-muted-foreground">
                            {(t.entry_time ?? "").slice(0, 16)}
                          </td>
                          <td className="px-3 py-1.5">
                            <Badge variant={t.direction === "long" ? "profit" : "loss"}
                                   className="px-1.5 py-0 text-[10px]">{t.direction}</Badge>
                          </td>
                          <td className="px-3 py-1.5 text-right font-mono tabular-nums">{t.entry_price}</td>
                          <td className="px-3 py-1.5 text-right font-mono tabular-nums">{t.exit_price ?? "—"}</td>
                          <td className={`px-3 py-1.5 text-right font-semibold tabular-nums ${pnlColor(v)}`}>
                            {t.pnl !== "" ? fmtDollar(v) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </ScrollArea>
            </Card>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Input value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter sessions"
               placeholder="Filter…" className="h-8 w-full text-sm sm:max-w-56" />
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : visible.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {sessions.length === 0 ? "No sessions yet — run a backtest from Strategies." : "Nothing matches."}
        </p>
      ) : (
        <Panel title={`${visible.length} runs`} dense>
          <DataTable head={<><th>Session</th><th>When</th><th className="!text-right">Trades</th>
                            <th className="!text-right">Win</th><th className="!text-right">P&L</th><th className="w-6" /></>}>
            {visible.map((s) => (
              <tr key={s.name} onClick={() => open(s)} className="cursor-pointer">
                <td className="max-w-0 truncate font-mono" title={s.name}>{s.name}</td>
                <td className="whitespace-nowrap text-muted-foreground">{s.modified.replace("T", " ")}</td>
                <td className="text-right tabular-nums text-muted-foreground">{s.trades ?? "—"}</td>
                <td className="text-right tabular-nums text-muted-foreground">
                  {s.win_rate != null ? fmtPct(s.win_rate) : "—"}
                </td>
                <td className={`text-right font-mono tabular-nums ${pnlColor(s.total_pnl)}`}>
                  {s.total_pnl != null ? fmtDollar(s.total_pnl) : "—"}
                </td>
                <td><ChevronRight className="h-3.5 w-3.5 text-muted-foreground" /></td>
              </tr>
            ))}
          </DataTable>
        </Panel>
      )}
    </div>
  );
}

// ----------------------------------------------------------------- page

export function Accounts() {
  return (
    <div className="space-y-3 p-3 sm:p-4">
      <div className="page-header">
        <h1 className="text-[15px] font-semibold tracking-tight">Accounts</h1>
      </div>
      <Tabs defaultValue="accounts">
        <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
          <TabsTrigger value="accounts">Accounts</TabsTrigger>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
        </TabsList>
        <TabsContent value="accounts" className="pt-4"><AccountsPanel /></TabsContent>
        <TabsContent value="sessions" className="pt-4"><SessionsPanel /></TabsContent>
      </Tabs>
    </div>
  );
}
