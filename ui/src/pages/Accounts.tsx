import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Wallet, Plus, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
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
          <div className="space-y-1">
            <Label>Name</Label>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="my-account" />
          </div>
          <div className="space-y-1">
            <Label>Starting Balance (USD)</Label>
            <Input type="number" value={form.starting_balance} onChange={(e) => setForm((f) => ({ ...f, starting_balance: e.target.value }))} />
          </div>
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
  const [accounts, setAccounts] = useState<Account[]>([]);

  useEffect(() => {
    api.accounts.list().then((r) => setAccounts(r.accounts)).catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Accounts</h1>
        <CreateDialog onCreated={(a) => setAccounts((prev) => [...prev, a])} />
      </div>

      {accounts.length === 0 ? (
        <p className="text-muted-foreground text-sm">No accounts yet.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {accounts.map((a, i) => (
            <motion.div key={a.account_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Wallet className="h-4 w-4 text-primary" />
                      <CardTitle className="text-sm">{a.name}</CardTitle>
                    </div>
                    <Badge variant="outline">{a.provider}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="text-2xl font-bold">{fmtDollar(a.starting_balance)}</div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{a.currency}</span>
                    <span>·</span>
                    <span className="font-mono truncate">{a.account_id}</span>
                  </div>
                  {a.is_live && <Badge variant="destructive" className="text-xs">live</Badge>}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
