import { motion, AnimatePresence } from "motion/react";
import { X, Clock } from "lucide-react";
import { Panel, DataTable } from "@/components/terminal/Panel";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/terminal/States";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { useResource } from "@/lib/useResource";
import { api } from "@/lib/api";
import { fmt } from "@/lib/utils";

const LABELS: Record<string, string> = {
  limit: "Limit", stop: "Stop",
  stop_loss: "Stop loss", take_profit: "Take profit",
};

/**
 * Resting orders.
 *
 * These are waiting on a price rather than filled, so they belong beside the
 * positions they will become — not buried in a history view.
 */
export function PendingOrdersPanel({
  accountId, refreshKey = 0, onChanged,
}: { accountId?: string; refreshKey?: number; onChanged?: () => void }) {
  const { toast } = useToast();
  const orders = useResource(() => api.orders.pending(accountId),
                             [accountId, refreshKey], { pollMs: 10000 });
  const rows = orders.data?.orders ?? [];

  async function cancel(id: string) {
    try {
      await api.orders.cancelPending(id);
      toast("Order cancelled", "success");
      orders.reload();
      onChanged?.();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Cancel failed", "error");
    }
  }

  return (
    <Panel dense title={`Working orders${rows.length ? ` · ${rows.length}` : ""}`}>
      {orders.error ? <ErrorState message={orders.error} onRetry={orders.reload} />
        : !orders.settled ? <SkeletonRows rows={2} cols={5} />
        : rows.length === 0
          ? <EmptyState title="No working orders"
                        hint="Limit and stop orders rest here until the market reaches them." />
          : (
            <DataTable head={<><th>Instrument</th><th>Type</th><th>Side</th>
                              <th className="!text-right">Size</th>
                              <th className="!text-right">Trigger</th>
                              <th>Placed</th><th className="w-8" /></>}>
              <AnimatePresence initial={false}>
                {rows.map((o) => (
                  <motion.tr key={o.id} layout
                             initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <td className="font-mono">{o.ticker}</td>
                    <td>
                      <span className="flex items-center gap-1.5">
                        <Clock className="h-3 w-3 text-muted-foreground" />
                        {LABELS[o.type] ?? o.type}
                      </span>
                    </td>
                    <td>
                      <Badge variant={o.direction === "long" ? "profit" : "loss"}
                             className="px-1.5 py-0 text-[10px]">{o.direction}</Badge>
                    </td>
                    <td className="text-right font-mono tabular-nums">{fmt(o.size, 4)}</td>
                    <td className="text-right font-mono tabular-nums">{fmt(o.trigger_price)}</td>
                    <td className="whitespace-nowrap font-mono text-[10px] text-muted-foreground">
                      {o.placed_at.replace("T", " ").slice(5, 16)}
                    </td>
                    <td>
                      <button onClick={() => cancel(o.id)} aria-label={`Cancel ${o.type} order`}
                              className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-destructive">
                        <X className="h-3 w-3" />
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </DataTable>
          )}
    </Panel>
  );
}
