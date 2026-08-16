import React, { useEffect, useState } from "react";
import {
  KeyRound, Trash2, Loader2, Server, FolderOpen, Sun, Moon, Monitor,
  Database, Newspaper, Landmark, Check,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { AnimatedIcon, MotionHost } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { Panel, DataTable } from "@/components/terminal/Panel";
import { SkeletonRows, ErrorState, EmptyState } from "@/components/terminal/States";
import { useResource } from "@/lib/useResource";
import { fmtDollar } from "@/lib/utils";
import { useTheme, type Theme } from "@/lib/useTheme";
import { api, type AppConfig, type ProviderGroups, type Provider } from "@/lib/api";

function ProviderGroup({
  title, icon, blurb, providers,
}: { title: string; icon: React.ElementType; blurb: string; providers: Provider[] }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <AnimatedIcon icon={icon} motionType="pulse" className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">{title}</h3>
        <Badge variant="outline" className="text-[10px]">{providers.length}</Badge>
      </div>
      <p className="text-[11px] text-muted-foreground">{blurb}</p>
      <div className="space-y-1.5">
        {providers.map((p) => (
          <div key={p.name} className="flex items-start gap-2.5 rounded-lg border p-2.5">
            <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-profit" />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-medium">{p.name}</span>
                {p.is_live && <Badge variant="secondary" className="text-[10px]">live prices</Badge>}
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground">{p.doc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Settings() {
  const { toast } = useToast();
  const { theme, setTheme } = useTheme();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [groups, setGroups] = useState<ProviderGroups | null>(null);
  const [creds, setCreds] = useState<Record<string, Record<string, string>>>({});
  const [form, setForm] = useState({ provider: "", key: "api_key", env_var: "" });
  const [saving, setSaving] = useState(false);
  const [homeInput, setHomeInput] = useState("");
  const [savingHome, setSavingHome] = useState(false);

  const loadCreds = () =>
    api.credentials.list().then((r) => setCreds(r.credentials ?? {})).catch(() => {});

  useEffect(() => {
    api.config.get().then((c) => { setConfig(c); setHomeInput(c.home); }).catch(() => {});
    api.providers.list().then(setGroups).catch(() => {});
    loadCreds();
  }, []);

  async function saveCred() {
    setSaving(true);
    try {
      await api.credentials.set({ provider: form.provider, key: form.key, env_var: form.env_var });
      toast(`Saved ${form.provider}.${form.key}`, "success");
      setForm({ provider: "", key: "api_key", env_var: "" });
      loadCreds();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to save", "error");
    }
    setSaving(false);
  }

  async function clearCred(provider: string) {
    try {
      await api.credentials.clear(provider);
      toast(`Cleared ${provider}`, "success");
      loadCreds();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to clear", "error");
    }
  }

  async function saveHome() {
    setSavingHome(true);
    try {
      const r = await api.config.setHome(homeInput);
      toast(
        r.overridden_by
          ? `Saved, but ${r.overridden_by} still takes precedence — unset it to use this.`
          : "Saved. Restart the server to switch data directory.",
        r.overridden_by ? "info" : "success"
      );
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not set data directory", "error");
    }
    setSavingHome(false);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-3 p-3 sm:p-4">
      <div>
        <h1 className="text-[15px] font-semibold tracking-tight">Settings</h1>
        <p className="text-xs text-muted-foreground">
          Appearance, data location, accounts, providers and credentials.
        </p>
      </div>

        <Tabs defaultValue="general">
          <TabsList className="w-full justify-start overflow-x-auto">
            <TabsTrigger value="general">General</TabsTrigger>
            <TabsTrigger value="accounts">Accounts</TabsTrigger>
            <TabsTrigger value="providers">Providers</TabsTrigger>
            <TabsTrigger value="credentials">Credentials</TabsTrigger>
          </TabsList>

          <TabsContent value="accounts" className="pt-4">
            <AccountsSettings />
          </TabsContent>

          {/* ---------------- general ---------------- */}
          <TabsContent value="general" className="space-y-3 pt-4">
            <div className="space-y-2 rounded-lg border p-3">
              <Label className="text-xs font-semibold">Appearance</Label>
              <div className="grid grid-cols-3 gap-2">
                {([
                  { value: "light", label: "Light", icon: Sun },
                  { value: "dark", label: "Dark", icon: Moon },
                  { value: "system", label: "System", icon: Monitor },
                ] as { value: Theme; label: string; icon: React.ElementType }[]).map(
                  ({ value, label, icon }) => (
                    <MotionHost key={value}>
                      <button
                        onClick={() => setTheme(value)}
                        aria-pressed={theme === value}
                        className={`flex w-full items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-xs font-medium transition-colors ${
                          theme === value
                            ? "border-primary bg-primary text-primary-foreground"
                            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                        }`}
                      >
                        <AnimatedIcon icon={icon} motionType="pop" className="h-3.5 w-3.5" />
                        {label}
                      </button>
                    </MotionHost>
                  )
                )}
              </div>
            </div>

            <div className="space-y-2 rounded-lg border p-3">
              <div className="flex items-center gap-2">
                <FolderOpen className="h-3.5 w-3.5 text-muted-foreground" />
                <Label className="text-xs font-semibold">Data directory</Label>
                {config?.home_source && config.home_source !== "default" && (
                  <Badge variant="outline" className="text-[10px]">via {config.home_source}</Badge>
                )}
              </div>
              <Field label="Path" value={homeInput} mono onValueChange={setHomeInput}
                     placeholder={config?.default_home ?? "~/.moneymaker"} />
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" onClick={saveHome}
                        disabled={savingHome || !homeInput || homeInput === config?.home}>
                  {savingHome && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Save
                </Button>
                {config?.default_home && homeInput !== config.default_home && (
                  <Button size="sm" variant="ghost"
                          onClick={() => setHomeInput(config.default_home!)}>
                    Reset to default
                  </Button>
                )}
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Sessions, accounts, credentials and cached bars all live here. The
                change takes effect when the server restarts.
              </p>
            </div>

            <div className="flex items-center gap-2 rounded-lg border p-3 text-xs">
              <Server className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="text-muted-foreground">Version</span>
              <span className="font-mono">{config?.version ?? "—"}</span>
            </div>
          </TabsContent>

          {/* ---------------- providers ---------------- */}
          <TabsContent value="providers" className="space-y-5 pt-4">
            {!groups ? (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            ) : (
              <>
                <ProviderGroup title="Market data" icon={Database} providers={groups.data}
                               blurb="Where price history and live quotes come from." />
                <ProviderGroup title="News & calendar" icon={Newspaper} providers={groups.news}
                               blurb="Economic release schedules used to gate release-day strategies." />
                <ProviderGroup title="Execution" icon={Landmark} providers={groups.execution}
                               blurb="Where orders are filled and balances tracked." />
              </>
            )}
          </TabsContent>

          {/* ---------------- credentials ---------------- */}
          <TabsContent value="credentials" className="space-y-4 pt-4">
            <div className="space-y-2">
              {Object.keys(creds).length === 0 ? (
                <p className="text-xs text-muted-foreground">No credentials stored.</p>
              ) : (
                Object.entries(creds).map(([provider, keys]) => (
                  <div key={provider} className="flex items-center justify-between rounded-lg border p-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <KeyRound className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="font-mono text-sm">{provider}</span>
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {Object.entries(keys).map(([k, v]) => (
                          <Badge key={k} variant="secondary" className="font-mono text-[10px]">
                            {k}={String(v)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <Button size="icon" variant="ghost" onClick={() => clearCred(provider)}
                            aria-label={`Clear ${provider}`}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                ))
              )}
            </div>

            <div className="space-y-2 rounded-lg border p-3">
              <Label className="text-xs font-semibold">Add credential</Label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <Field label="Provider" placeholder="alpaca" value={form.provider}
                       onValueChange={(v) => setForm((f) => ({ ...f, provider: v }))} />
                <Field label="Key" placeholder="api_key" value={form.key}
                       onValueChange={(v) => setForm((f) => ({ ...f, key: v }))} />
                <Field label="Env var" placeholder="ALPACA_API_KEY" mono value={form.env_var}
                       onValueChange={(v) => setForm((f) => ({ ...f, env_var: v }))} />
              </div>
              <Button size="sm" className="w-full" onClick={saveCred}
                      disabled={saving || !form.provider || !form.env_var}>
                {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Save reference
              </Button>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Only the variable <em>name</em> is stored — the secret stays in your
                environment and never touches disk.
              </p>
            </div>
          </TabsContent>
        </Tabs>
    </div>
  );
}

/** Account administration — creating, funding and removing paper accounts. */
function AccountsSettings() {
  const { toast } = useToast();
  const accounts = useResource(() => api.accounts.list(), []);
  const [form, setForm] = useState({ name: "", balance: "10000" });
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function create() {
    setBusy(true);
    try {
      await api.accounts.create({ name: form.name, starting_balance: Number(form.balance) });
      toast(`Created ${form.name}`, "success");
      setForm({ name: "", balance: "10000" });
      accounts.reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Create failed", "error");
    }
    setBusy(false);
  }

  async function remove(id: string, name: string) {
    setDeleting(id);
    try {
      await api.accounts.remove(id);
      toast(`Deleted ${name}`, "success");
      accounts.reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Delete failed", "error");
    }
    setDeleting(null);
  }

  async function prune() {
    try {
      const dry = await api.accounts.prune("mw_", true);
      if (dry.matched === 0) return toast("No scratch accounts to prune.", "info");
      if (window.confirm(`Delete ${dry.matched} scratch account(s) from older backtests?`)) {
        const r = await api.accounts.prune("mw_", false);
        toast(`Deleted ${r.deleted} scratch account(s)`, "success");
        accounts.reload();
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : "Prune failed", "error");
    }
  }

  const list = accounts.data?.accounts ?? [];
  const total = list.reduce((s, a) => s + (a.balance ?? 0), 0);

  return (
    <div className="space-y-3">
      <Panel dense title={`${list.length} accounts`}
             actions={<span className="font-mono text-[10px] tabular-nums text-muted-foreground">
               {fmtDollar(total)} combined</span>}>
        {accounts.error ? <ErrorState message={accounts.error} onRetry={accounts.reload} />
          : !accounts.settled ? <SkeletonRows rows={3} cols={3} />
          : list.length === 0 ? <EmptyState title="No accounts yet" />
          : (
            <DataTable head={<><th>Name</th><th>Provider</th>
                              <th className="!text-right">Balance</th><th className="w-8" /></>}>
              {list.map((a) => (
                <tr key={a.account_id} className="group">
                  <td>
                    <div className="font-medium">{a.name}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">{a.account_id}</div>
                  </td>
                  <td className="text-muted-foreground">{a.provider}</td>
                  <td className="text-right font-mono tabular-nums">{fmtDollar(a.balance)}</td>
                  <td>
                    <button onClick={() => remove(a.account_id, a.name)}
                            disabled={deleting === a.account_id}
                            aria-label={`Delete ${a.name}`}
                            className="rounded p-1 opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100">
                      {deleting === a.account_id
                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        : <Trash2 className="h-3.5 w-3.5 text-destructive" />}
                    </button>
                  </td>
                </tr>
              ))}
            </DataTable>
          )}
      </Panel>

      <Panel title="Add account">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Name" value={form.name} placeholder="paper-1"
                   onValueChange={(v) => setForm((f) => ({ ...f, name: v }))} />
            <Field label="Starting balance (USD)" type="number" value={form.balance}
                   onValueChange={(v) => setForm((f) => ({ ...f, balance: v }))} />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={create} disabled={busy || !form.name}>
              {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Create account
            </Button>
            <Button size="sm" variant="outline" onClick={prune}>
              Prune scratch accounts
            </Button>
          </div>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            Older multi-window backtests left one <code className="font-mono">mw_*</code> account per
            window behind. Pruning clears them; current runs no longer create any.
          </p>
        </div>
      </Panel>
    </div>
  );
}
