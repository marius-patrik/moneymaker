import { useState } from "react";
import { Panel, DataTable, Stat } from "@/components/terminal/Panel";
import { SkeletonRows, ErrorState, EmptyState } from "@/components/terminal/States";
import { Badge } from "@/components/ui/badge";
import { TradeDetail } from "@/components/terminal/TradeDetail";
import { Input } from "@/components/ui/input";
import { useAccount } from "@/lib/useAccount";
import { useResource } from "@/lib/useResource";
import { api, type PositionRow } from "@/lib/api";
import { fmt, fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

/**
 * Full trade history.
 *
 * Its own page rather than a panel on the portfolio: hundreds of rows push
 * everything else off the screen, and the portfolio's job is the current
 * state of the book, not its complete past.
 */
export function History() {
  const { scoped } = useAccount();
  const [filter, setFilter] = useState("");
  const [limit, setLimit] = useState(100);
  const [inspect, setInspect] = useState<PositionRow | null>(null);
  const positions = useResource(() => api.positions.list(scoped), [scoped]);

  const all = positions.data?.closed ?? [];
  const q = filter.trim().toLowerCase();
  const rows = q
    ? all.filter((t) => (t.ticker || "").toLowerCase().includes(q) ||
                        t.run.toLowerCase().includes(q))
    : all;
  const shown = rows.slice(0, limit);

  const wins = rows.filter((t) => (t.pnl ?? 0) > 0).length;
  const total = rows.reduce((s, t) => s + (t.pnl ?? 0), 0);

  return (
    <div className="space-y-3 p-3 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-[15px] font-semibold tracking-tight">Trade history</h1>
        <Input value={filter} onChange={(e) => { setFilter(e.target.value); setLimit(100); }}
               aria-label="Filter history" placeholder="Filter by instrument or run…"
               className="h-8 w-full text-sm sm:max-w-64" />
      </div>

      <Panel title="Summary">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Trades" value={String(rows.length)}
                sub={q ? `filtered from ${all.length}` : undefined} />
          <Stat label="Net P&L" value={fmtDollar(total)}
                tone={total === 0 ? "neutral" : total > 0 ? "profit" : "loss"} />
          <Stat label="Win rate"
                value={rows.length ? fmtPct(wins / rows.length) : "—"}
                sub={`${wins}W / ${rows.length - wins}L`} />
          <Stat label="Showing" value={`${shown.length}`} sub={`of ${rows.length}`} />
        </div>
      </Panel>

      <Panel dense title="Closed trades">
        {positions.error ? <ErrorState message={positions.error} onRetry={positions.reload} />
          : !positions.settled ? <SkeletonRows rows={10} cols={6} />
          : rows.length === 0
            ? <EmptyState title={q ? "Nothing matches" : "No trades yet"}
                          hint={q ? undefined : "Run a backtest or trade to build history."} />
            : (
              <>
                <DataTable head={<><th>Instrument</th><th>Side</th><th>Opened</th><th>Closed</th>
                                  <th className="!text-right">Size</th><th className="!text-right">Entry</th>
                                  <th className="!text-right">Exit</th><th>Reason</th>
                                  <th className="!text-right">P&L</th><th>Run</th></>}>
                  {shown.map((t, i) => (
                    <tr key={i} onClick={() => setInspect(t)} className="cursor-pointer">
                      <td className="font-mono">{t.ticker || "—"}</td>
                      <td>
                        <Badge variant={t.direction === "long" ? "profit" : "loss"}
                               className="px-1.5 py-0 text-[10px]">{t.direction}</Badge>
                      </td>
                      <td className="whitespace-nowrap font-mono text-muted-foreground">
                        {t.entry_time.replace("T", " ").slice(0, 16)}
                      </td>
                      <td className="whitespace-nowrap font-mono text-muted-foreground">
                        {t.exit_time.replace("T", " ").slice(0, 16)}
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
                      <td className="max-w-0 truncate font-mono text-[10px] text-muted-foreground">
                        {t.run}
                      </td>
                    </tr>
                  ))}
                </DataTable>
                {rows.length > shown.length && (
                  <button onClick={() => setLimit((n) => n + 200)}
                          className="w-full border-t py-2 text-xs text-muted-foreground hover:bg-accent/40">
                    Show {Math.min(200, rows.length - shown.length)} more
                  </button>
                )}
              </>
            )}
      </Panel>

      <TradeDetail trade={inspect} open={!!inspect}
                   onOpenChange={(v) => !v && setInspect(null)} />
    </div>
  );
}
