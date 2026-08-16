import { useEffect, useState } from "react";
import { KeyRound, Trash2, Loader2, Server, Database, FolderOpen } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { api, type AppConfig, type Provider } from "@/lib/api";

export function SettingsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { toast } = useToast();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [creds, setCreds] = useState<Record<string, Record<string, string>>>({});
  const [form, setForm] = useState({ provider: "", key: "api_key", env_var: "" });
  const [saving, setSaving] = useState(false);

  const loadCreds = () =>
    api.credentials.list().then((r) => setCreds(r.credentials ?? {})).catch(() => {});

  useEffect(() => {
    if (!open) return;
    api.config.get().then(setConfig).catch(() => {});
    api.providers.list().then((r) => setProviders(r.providers)).catch(() => {});
    loadCreds();
  }, [open]);

  async function saveCred() {
    if (!form.provider || !form.env_var) return;
    setSaving(true);
    try {
      await api.credentials.set({ provider: form.provider, key: form.key, env_var: form.env_var });
      toast(`Saved ${form.provider}.${form.key}`, "success");
      setForm({ provider: "", key: "api_key", env_var: "" });
      loadCreds();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to save credential", "error");
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>
            Engine configuration, providers, and stored credentials.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="general" className="pt-1">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="general">General</TabsTrigger>
            <TabsTrigger value="providers">Providers</TabsTrigger>
            <TabsTrigger value="credentials">Credentials</TabsTrigger>
          </TabsList>

          {/* --- General --- */}
          <TabsContent value="general" className="space-y-3 pt-4">
            {config ? (
              <div className="space-y-2 text-sm">
                {[
                  { icon: Server, label: "Version", value: config.version },
                  { icon: FolderOpen, label: "Data directory", value: config.home },
                  { icon: Database, label: "Data providers", value: config.data_providers.join(", ") },
                ].map(({ icon: Icon, label, value }) => (
                  <div key={label} className="flex items-start gap-3 rounded-md border p-3">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <div className="text-xs text-muted-foreground">{label}</div>
                      <div className="break-all font-mono text-xs">{value}</div>
                    </div>
                  </div>
                ))}
                <p className="pt-1 text-xs text-muted-foreground">
                  Override the data directory with the <code className="font-mono">MONEYMAKER_HOME</code> environment
                  variable or the <code className="font-mono">--data-dir</code> flag.
                </p>
              </div>
            ) : (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            )}
          </TabsContent>

          {/* --- Providers --- */}
          <TabsContent value="providers" className="space-y-2 pt-4">
            {providers.map((p) => (
              <div key={p.name} className="flex items-center justify-between rounded-md border p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm">{p.name}</span>
                    <Badge variant={p.status === "ready" ? "profit" : "outline"}>{p.status}</Badge>
                  </div>
                  <p className="truncate text-xs text-muted-foreground">{p.doc}</p>
                </div>
              </div>
            ))}
            <p className="pt-1 text-xs text-muted-foreground">
              Stub providers are scaffolded but place no orders. Wiring one to a real broker is always a
              separate, explicit decision.
            </p>
          </TabsContent>

          {/* --- Credentials --- */}
          <TabsContent value="credentials" className="space-y-4 pt-4">
            <div className="space-y-2">
              {Object.keys(creds).length === 0 ? (
                <p className="text-xs text-muted-foreground">No credentials stored.</p>
              ) : (
                Object.entries(creds).map(([provider, keys]) => (
                  <div key={provider} className="flex items-center justify-between rounded-md border p-3">
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
                    <Button size="icon" variant="ghost" onClick={() => clearCred(provider)} aria-label={`Clear ${provider}`}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                ))
              )}
            </div>

            <div className="space-y-2 rounded-md border p-3">
              <Label className="text-xs font-semibold">Add credential (env var reference)</Label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <Input placeholder="provider" value={form.provider}
                       onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
                       className="h-8 text-xs" />
                <Input placeholder="key" value={form.key}
                       onChange={(e) => setForm((f) => ({ ...f, key: e.target.value }))}
                       className="h-8 text-xs" />
                <Input placeholder="ENV_VAR_NAME" value={form.env_var}
                       onChange={(e) => setForm((f) => ({ ...f, env_var: e.target.value }))}
                       className="h-8 font-mono text-xs" />
              </div>
              <Button size="sm" className="w-full" onClick={saveCred}
                      disabled={saving || !form.provider || !form.env_var}>
                {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Save reference
              </Button>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Only the variable <em>name</em> is stored — the secret itself stays in your environment and never
                touches disk.
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
