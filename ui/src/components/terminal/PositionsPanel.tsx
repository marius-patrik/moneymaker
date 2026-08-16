import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Loader2, X, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { Panel, DataTable, Stat } from "@/components/terminal/Panel";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/terminal/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { useResource } from "@/lib/useResource";
import { api, type PositionRow } from "@/lib/api";
import { fmt, fmtDollar, pnlColor } from "@/lib/utils";

/** A single position, marked to market — the analysis view. */
function PositionDetail({ id, onClosed }: { id: string; onClosed: () => void }) {
  const { toast } = useToast();
  const detail = useResource(() => api.positions.get(id), [id], { pollMs: 10000 });
  const [closing, setClosing] = useState(false);
  const d = detail.data;

  async function close() {
    setClosing(true);
    try {
      const r = await api.positions.close(id);
      toast(`Closed ${r.ticker} · ${fmtDollar(r.pnl)}`, r.pnl >= 0 ? "success" : "info");
      onClosed();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Close failed", "error");
    }
    setClosing(false);
  }

  if (detail.error) return <ErrorState message={detail.error} onRetry={detail.reload} />;
  if (!d) return <div className="flex justify-center py-8"><Loader2 className="h-4 w-4 animate-spin" /></div>;

  const long = d.direction === "long";
  const move = d.mark != null ? (d.mark - d.entry_price) / d.entry_price : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="font-mono text-lg font-semibold">{d.ticker}</span>
        <Badge variant={long ? "profit" : "loss"} className="gap-1">
          {long ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
          {d.direction}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat label="Size" value={fmt(d.size, 4)} />
        <Stat label="Entry" value={fmt(d.entry_price)} />
        <Stat label="Mark" value={d.mark != null ? fmt(d.mark) : "—"} />
        <Stat label="Unrealised"
              value={d.unrealised_pnl != null ? fmtDollar(d.unrealised_pnl) : "—"}
              tone={d.unrealised_pnl == null || d.unrealised_pnl === 0 ? "neutral"
                    : d.unrealised_pnl > 0 ? "profit" : "loss"} />
        <Stat label="Move" value={move != null ? `${(move * 100).toFixed(2)}%` : "—"}
              tone={move == null || move === 0 ? "neutral"
                    : (long ? move > 0 : move < 0) ? "profit" : "loss"} />
        <Stat label="Notional" value={fmtDollar(d.entry_price * d.size)} />
      </div>

      <div className="space-y-1 rounded-lg border bg-muted/30 p-3 text-[11px]">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Opened</span>
          <span className="font-mono">{d.entry_time.replace("T", " ")}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Account</span>
          <span className="font-mono">{d.account_id}</span>
        </div>
      </div>

      <Button variant="destructive" className="w-full" onClick={close} disabled={closing}>
        {closing ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
        Close at market
      </Button>
    </div>
  );
}

/**
 * Open positions.
 *
 * Placing an order used to leave nothing on screen; positions are recorded
 * now, and each one opens for inspection and can be closed from here.
 */
export function PositionsPanel({
  accountId, onChanged, title = "Open positions", refreshKey = 0,
}: {
  accountId?: string;
  onChanged?: () => void;
  title?: string;
  /** Bump to refetch immediately — a fill should appear at once, not on the
   *  next poll. */
  refreshKey?: number;
}) {
  const positions = useResource(() => api.positions.list(accountId),
                                [accountId, refreshKey], { pollMs: 10000 });
  const [inspect, setInspect] = useState<string | null>(null);
  const rows = positions.data?.open ?? [];

  return (
    <>
      <Panel dense title={`${title}${positions.data ? ` · ${positions.data.open_count}` : ""}`}>
        {positions.error ? <ErrorState message={positions.error} onRetry={positions.reload} />
          : !positions.settled ? <SkeletonRows rows={2} cols={5} />
          : rows.length === 0
            ? <EmptyState title="Flat" hint="No open positions on this selection." />
            : (
              <DataTable head={<><th>Instrument</th><th>Side</th><th>Opened</th>
                                <th className="!text-right">Size</th>
                                <th className="!text-right">Entry</th>
                                <th className="!text-right">Mark</th>
                                <th className="!text-right">Unrealised</th>
                                <th className="w-8" /></>}>
                <AnimatePresence initial={false}>
                  {rows.map((t: PositionRow, i) => (
                    <motion.tr key={t.id ?? `${t.run}-${i}`} layout
                               initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                               onClick={() => t.id && setInspect(t.id)}
                               className={t.id ? "cursor-pointer" : ""}>
                      <td className="font-mono">{t.ticker || "—"}</td>
                      <td>
                        <Badge variant={t.direction === "long" ? "profit" : "loss"}
                               className="px-1.5 py-0 text-[10px]">{t.direction}</Badge>
                      </td>
                      <td className="whitespace-nowrap font-mono text-muted-foreground">
                        {t.entry_time.replace("T", " ").slice(0, 16)}
                      </td>
                      <td className="text-right font-mono tabular-nums">
                        {t.size != null ? fmt(t.size, 4) : "—"}
                      </td>
                      <td className="text-right font-mono tabular-nums">
                        {t.entry_price != null ? fmt(t.entry_price) : "—"}
                      </td>
                      <td className="text-right font-mono tabular-nums">
                        {t.mark != null ? fmt(t.mark) : "—"}
                      </td>
                      <td className={`text-right font-mono tabular-nums ${pnlColor(t.unrealised_pnl ?? 0)}`}>
                        {t.unrealised_pnl != null ? fmtDollar(t.unrealised_pnl) : "—"}
                      </td>
                      <td className="text-right text-[10px] text-muted-foreground">
                        {t.id ? "inspect" : t.run}
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </DataTable>
            )}
      </Panel>

      <Dialog open={!!inspect} onOpenChange={(v) => !v && setInspect(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Position</DialogTitle></DialogHeader>
          {inspect && (
            <PositionDetail id={inspect}
                            onClosed={() => { setInspect(null); positions.reload(); onChanged?.(); }} />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
