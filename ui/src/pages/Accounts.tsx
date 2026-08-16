import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Wallet, Plus, Loader2, Trash2, Search, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { api, type Account } from "@/lib/api";
import { fmtDollar } from "@/lib/utils";

function CreateDialog({ onCreated }: { onCreated: (a: Account) => void }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", starting_balance: "10000" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      const a = await api.accounts.create({ name: form.name, starting_balance: Number(form.starting_balance) });
      onCreated(a);
      setOpen(false);
      setForm({ name: "", starting_balance: "10000" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    }
    setLoading(false);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm"><Plus className="h-4 w-4" />New Account</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader><DialogTitle>Create Account</DialogTitle></DialogHeader>
        <div className="space-y-3 pt-2">
          <Field label="Name" value={form.name} className="h-10"
                 onValueChange={(v) => setForm((f) => ({ ...f, name: v }))} placeholder="my-account" />
          <Field label="Starting balance (USD)" type="number" value={form.starting_balance}
                 className="h-10"
                 onValueChange={(v) => setForm((f) => ({ ...f, starting_balance: v }))} />
          {error && <p className="text-xs text-destructive">{error}</p>}
          <Button className="w-full" onClick={submit} disabled={loading || !form.name}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Create
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function Accounts() {
  const { toast } = useToast();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [limit, setLimit] = useState(24);
  const [pruning, setPruning] = useState(false);

  useEffect(() => {
    api.accounts.list()
      .then((r) => setAccounts(r.accounts))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return accounts.filter(
      (a) => a.name.toLowerCase().includes(q) || a.account_id.toLowerCase().includes(q)
    );
  }, [accounts, query]);

  const shown = filtered.slice(0, limit);
  const totalBalance = filtered.reduce((s, a) => s + (a.starting_balance ?? 0), 0);

  /** Two-step: report what matches, then delete once the user confirms. */
  async function prune() {
    setPruning(true);
    try {
      const dry = await api.accounts.prune("mw_", true);
      if (dry.matched === 0) {
        toast("No scratch accounts to prune.", "info");
      } else if (window.confirm(
        `Delete ${dry.matched} scratch account(s) left by older multi-window backtests?\n\n` +
        `e.g. ${dry.sample.slice(0, 3).join(", ")}`
      )) {
        const r = await api.accounts.prune("mw_", false);
        setAccounts((prev) => prev.filter((a) => !a.name.startsWith("mw_")));
        toast(`Deleted ${r.deleted} scratch account(s)`, "success");
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : "Prune failed", "error");
    }
    setPruning(false);
  }

  async function remove(a: Account) {
    setDeleting(a.account_id);
    try {
      await api.accounts.remove(a.account_id);
      setAccounts((prev) => prev.filter((x) => x.account_id !== a.account_id));
      toast(`Deleted ${a.name}`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Delete failed", "error");
    }
    setDeleting(null);
  }

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Accounts</h1>
          <p className="text-sm text-muted-foreground">
            {filtered.length} of {accounts.length} · {fmtDollar(totalBalance)} combined
          </p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <div className="relative min-w-0 flex-1 sm:flex-none">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => { setQuery(e.target.value); setLimit(24); }}
              aria-label="Filter accounts"
              placeholder="Filter by name or id…"
              className="h-8 w-full pl-8 text-sm sm:w-56"
            />
          </div>
          <Button size="sm" variant="outline" onClick={prune} disabled={pruning}>
            {pruning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            Prune scratch
          </Button>
          <CreateDialog onCreated={(a) => setAccounts((prev) => [...prev, a])} />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {accounts.length === 0 ? "No accounts yet." : `No accounts match “${query}”.`}
        </p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <AnimatePresence mode="popLayout">
              {shown.map((a, i) => (
                <motion.div
                  key={a.account_id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ delay: Math.min(i, 12) * 0.02 }}
                >
                  <Card className="group">
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex min-w-0 items-center gap-2">
                          <Wallet className="h-4 w-4 shrink-0 text-primary" />
                          <CardTitle className="truncate text-sm">{a.name}</CardTitle>
                        </div>
                        <div className="flex shrink-0 items-center gap-1">
                          <Badge variant="outline">{a.provider}</Badge>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7 opacity-0 transition-opacity group-hover:opacity-100"
                            onClick={() => remove(a)}
                            disabled={deleting === a.account_id}
                            aria-label={`Delete ${a.name}`}
                          >
                            {deleting === a.account_id
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <Trash2 className="h-3.5 w-3.5 text-destructive" />}
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <div className="text-2xl font-bold">{fmtDollar(a.starting_balance)}</div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span>{a.currency}</span>
                        <span>·</span>
                        <span className="truncate font-mono">{a.account_id}</span>
                      </div>
                      {a.is_live && <Badge variant="destructive" className="text-xs">live</Badge>}
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          {filtered.length > shown.length && (
            <Button variant="outline" className="w-full" onClick={() => setLimit((n) => n + 48)}>
              Show more ({filtered.length - shown.length} remaining)
            </Button>
          )}
        </>
      )}
    </div>
  );
}
