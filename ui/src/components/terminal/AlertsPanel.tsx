import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Bell, BellRing, X, RotateCcw, Plus } from "lucide-react";
import { Panel, DataTable } from "@/components/terminal/Panel";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/terminal/States";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { useResource } from "@/lib/useResource";
import { api } from "@/lib/api";
import { cn, fmt } from "@/lib/utils";

/**
 * Price alerts for the charted instrument.
 *
 * Alerts ride the same sweep as resting orders, so they fire on the price
 * the engine actually sees rather than a second, differently-delayed feed.
 */
export function AlertsPanel({ ticker, lastPrice }: { ticker: string; lastPrice?: number | null }) {
  const { toast } = useToast();
  const alerts = useResource(() => api.orders.alerts(ticker), [ticker], { pollMs: 15000 });
  const [adding, setAdding] = useState(false);
  const [level, setLevel] = useState("");
  const [condition, setCondition] = useState("above");
  const [busy, setBusy] = useState(false);

  const rows = alerts.data?.alerts ?? [];
  const fired = alerts.data?.recently_fired ?? [];

  async function create() {
    setBusy(true);
    try {
      await api.orders.createAlert({
        ticker, level: Number(level), condition, repeat: condition === "crosses",
      });
      toast(`Alert set on ${ticker} ${condition} ${level}`, "success");
      setLevel(""); setAdding(false);
      alerts.reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not set alert", "error");
    }
    setBusy(false);
  }

  async function remove(id: string) {
    try { await api.orders.deleteAlert(id); alerts.reload(); }
    catch (e) { toast(e instanceof Error ? e.message : "Delete failed", "error"); }
  }

  async function rearm(id: string) {
    try { await api.orders.rearmAlert(id); alerts.reload(); }
    catch (e) { toast(e instanceof Error ? e.message : "Re-arm failed", "error"); }
  }

  return (
    <Panel dense
           title={`Alerts${rows.length ? ` · ${rows.length}` : ""}`}
           actions={
             <button onClick={() => { setAdding((v) => !v); setLevel(lastPrice ? String(fmt(lastPrice)) : ""); }}
                     aria-label="Add alert"
                     className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
               <AnimatedIcon icon={Plus} motionType="pop" className="h-3.5 w-3.5" />
             </button>
           }>
      {fired.length > 0 && (
        <div className="flex items-center gap-2 border-b bg-profit/10 px-3 py-2">
          <BellRing className="h-3.5 w-3.5 shrink-0 text-profit" />
          <span className="min-w-0 flex-1 truncate text-[11px]">
            {fired.length} alert{fired.length > 1 ? "s" : ""} fired —{" "}
            {fired.slice(0, 2).map((a) => `${a.ticker} ${a.condition} ${fmt(a.level)}`).join(", ")}
          </span>
          <button onClick={() => api.orders.acknowledgeAlerts().then(() => alerts.reload())}
                  className="shrink-0 text-[10px] text-muted-foreground hover:text-foreground">
            dismiss
          </button>
        </div>
      )}

      <AnimatePresence>
        {adding && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-b">
            <div className="space-y-2 p-3">
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label htmlFor="alert-cond" className="text-xs">Condition</Label>
                  <Select value={condition} onValueChange={setCondition}>
                    <SelectTrigger id="alert-cond" className="h-8 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(alerts.data?.conditions ?? []).map((c) => (
                        <SelectItem key={c.kind} value={c.kind}>{c.kind}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Field label="Level" type="number" value={level} onValueChange={setLevel} />
              </div>
              <Button size="sm" className="w-full" onClick={create} disabled={busy || !level}>
                Set alert on {ticker}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {alerts.error ? <ErrorState message={alerts.error} onRetry={alerts.reload} />
        : !alerts.settled ? <SkeletonRows rows={2} cols={3} />
        : rows.length === 0
          ? <EmptyState title="No alerts" hint={`Watch a level on ${ticker} without resting an order.`} />
          : (
            <DataTable head={<><th>Condition</th><th className="!text-right">Level</th>
                              <th>Status</th><th className="w-14" /></>}>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td>
                    <span className="flex items-center gap-1.5">
                      <Bell className={cn("h-3 w-3",
                        a.status === "armed" ? "text-primary" : "text-muted-foreground")} />
                      {a.condition}{a.repeat ? " ⟳" : ""}
                    </span>
                  </td>
                  <td className="text-right font-mono tabular-nums">{fmt(a.level)}</td>
                  <td>
                    {a.status === "armed"
                      ? <Badge variant="secondary" className="text-[10px]">armed</Badge>
                      : <span className="font-mono text-[10px] text-muted-foreground">
                          hit {a.fired_price != null ? fmt(a.fired_price) : ""}
                        </span>}
                  </td>
                  <td>
                    <span className="flex justify-end gap-0.5">
                      {a.status === "fired" && (
                        <button onClick={() => rearm(a.id)} aria-label="Re-arm alert"
                                className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
                          <RotateCcw className="h-3 w-3" />
                        </button>
                      )}
                      <button onClick={() => remove(a.id)} aria-label="Delete alert"
                              className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-destructive">
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  </td>
                </tr>
              ))}
            </DataTable>
          )}
    </Panel>
  );
}
