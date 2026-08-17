import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { Panel, Stat, DataTable } from "@/components/terminal/Panel";
import { SkeletonRows, ErrorState, EmptyState } from "@/components/terminal/States";
import { Badge } from "@/components/ui/badge";
import { TradeDetail } from "@/components/terminal/TradeDetail";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useResource } from "@/lib/useResource";
import { api, type PositionRow } from "@/lib/api";
import { useAccount } from "@/lib/useAccount";
import { OverviewPanels } from "@/pages/OverviewPanels";
import { fmt, fmtDollar, pnlColor } from "@/lib/utils";

const ALL = "__all__";

/**
 * Positions and trade history, scoped to one account or all of them.
 *
 * Accounts are administered in Settings; this view is about what they hold
 * and what they have done.
 */
export function Portfolio() {
  const [inspect, setInspect] = useState<PositionRow | null>(null);
  // The header owns account context; a second selector here could disagree
  // with it, which is exactly the confusion the global switcher removes.
  const { accountId, scoped, isAll } = useAccount();
  const accounts = useResource(() => api.accounts.list(), []);
  const positions = useResource(() => api.positions.list(scoped), [scoped],
                                { pollMs: 15000 });

  const list = accounts.data?.accounts ?? [];
  const d = positions.data;
  const current = list.find((a) => a.account_id === accountId);
  const equity = isAll
    ? list.reduce((s, a) => s + (a.balance ?? 0), 0)
    : current?.balance ?? 0;

  return (
    <div className="space-y-3 p-3 sm:p-4">
      {/* Account-wide performance, which used to be its own destination. */}
      {isAll && <OverviewPanels />}

      <Panel title="Summary">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Equity" value={fmtDollar(equity)}
                sub={isAll ? `${list.length} accounts` : current?.provider} />
          <Stat label="Realised" value={d ? fmtDollar(d.realised_pnl) : "—"}
                tone={!d || d.realised_pnl === 0 ? "neutral" : d.realised_pnl > 0 ? "profit" : "loss"}
                sub={d ? `${d.closed_count} closed` : undefined} />
          <Stat label="Unrealised" value={d ? fmtDollar(d.unrealised_pnl) : "—"}
                tone={!d || d.unrealised_pnl === 0 ? "neutral" : d.unrealised_pnl > 0 ? "profit" : "loss"}
                sub={d ? `${d.open_count} open` : undefined} />
          <Stat label="Total P&L" value={d ? fmtDollar(d.total_pnl) : "—"}
                tone={!d || d.total_pnl === 0 ? "neutral" : d.total_pnl > 0 ? "profit" : "loss"} />
        </div>
      </Panel>

      <Panel title={`Open positions${d ? ` · ${d.open_count}` : ""}`} dense>
        {positions.error ? <ErrorState message={positions.error} onRetry={positions.reload} />
          : !positions.settled ? <SkeletonRows rows={3} cols={5} />
          : (d?.open.length ?? 0) === 0
            ? <EmptyState title="Flat" hint="No positions are open on this selection." />
            : (
              <DataTable head={<><th>Instrument</th><th>Side</th><th>Opened</th>
                                <th className="!text-right">Size</th>
                                <th className="!text-right">Entry</th>
                                <th className="!text-right">Mark</th>
                                <th className="!text-right">Unrealised</th>
                                <th>Run</th></>}>
                {d!.open.map((t, i) => (
                  <tr key={i} onClick={() => setInspect(t)} className="cursor-pointer">
                    <td className="font-mono">{t.ticker || "—"}</td>
                    <td>
                      <Badge variant={t.direction === "long" ? "profit" : "loss"}
                             className="px-1.5 py-0 text-[10px]">{t.direction}</Badge>
                    </td>
                    <td className="whitespace-nowrap font-mono text-muted-foreground">
                      {t.entry_time.slice(0, 16)}
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
                    <td className="max-w-0 truncate font-mono text-[10px] text-muted-foreground">{t.run}</td>
                  </tr>
                ))}
              </DataTable>
            )}
      </Panel>

      <Panel title={`Trade history${d ? ` · ${d.closed_count}` : ""}`} dense>
        {positions.error ? <ErrorState message={positions.error} onRetry={positions.reload} />
          : !positions.settled ? <SkeletonRows rows={6} cols={6} />
          : (d?.closed.length ?? 0) === 0
            ? <EmptyState title="No trades yet"
                          hint="Run a backtest or deploy a system to build history." />
            : (
              <DataTable head={<><th>Instrument</th><th>Side</th><th>Opened</th><th>Closed</th>
                                <th className="!text-right">Size</th><th className="!text-right">Entry</th>
                                <th className="!text-right">Exit</th><th>Reason</th>
                                <th className="!text-right">P&L</th></>}>
                {d!.closed.slice(0, 8).map((t, i) => (
                  <tr key={i} onClick={() => setInspect(t)} className="cursor-pointer">
                    <td className="font-mono">{t.ticker || "—"}</td>
                    <td>
                      <Badge variant={t.direction === "long" ? "profit" : "loss"}
                             className="px-1.5 py-0 text-[10px]">{t.direction}</Badge>
                    </td>
                    <td className="whitespace-nowrap font-mono text-muted-foreground">
                      {t.entry_time.slice(0, 16)}
                    </td>
                    <td className="whitespace-nowrap font-mono text-muted-foreground">
                      {t.exit_time.slice(0, 16)}
                    </td>
                    <td className="text-right font-mono tabular-nums">
                      {t.size != null ? fmt(t.size, 4) : "—"}
                    </td>
                    <td className="text-right font-mono tabular-nums">
                      {t.entry_price != null ? fmt(t.entry_price) : "—"}
                    </td>
                    <td className="text-right font-mono tabular-nums">
                      {t.exit_price != null ? fmt(t.exit_price) : "—"}
                    </td>
                    <td className="text-muted-foreground">{t.exit_reason || "—"}</td>
                    <td className={`text-right font-mono tabular-nums ${pnlColor(t.pnl)}`}>
                      {t.pnl != null ? fmtDollar(t.pnl) : "—"}
                    </td>
                  </tr>
                ))}
              </DataTable>
            )}
      </Panel>

      <TradeDetail trade={inspect} open={!!inspect}
                   onOpenChange={(v) => !v && setInspect(null)}
                   onClosed={positions.reload} />
    </div>
  );
}
