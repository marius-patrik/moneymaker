import { useEffect, useState } from "react";
import { Panel, Stat, DataTable } from "@/components/terminal/Panel";
import { SkeletonRows, ErrorState, EmptyState } from "@/components/terminal/States";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useResource } from "@/lib/useResource";
import { api } from "@/lib/api";
import { fmt, fmtDollar, pnlColor } from "@/lib/utils";

const ALL = "__all__";

/**
 * Positions and trade history, scoped to one account or all of them.
 *
 * Accounts are administered in Settings; this view is about what they hold
 * and what they have done.
 */
export function Portfolio() {
  const [account, setAccount] = useState(ALL);
  const accounts = useResource(() => api.accounts.list(), []);
  const positions = useResource(
    () => api.positions.list(account === ALL ? undefined : account),
    [account],
    { pollMs: 15000 }
  );

  const list = accounts.data?.accounts ?? [];
  const d = positions.data;
  const scoped = list.find((a) => a.account_id === account);
  const equity = account === ALL
    ? list.reduce((s, a) => s + (a.balance ?? 0), 0)
    : scoped?.balance ?? 0;

  return (
    <div className="space-y-3 p-3 sm:p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="w-full max-w-56 space-y-1">
          <Label htmlFor="pf-account" className="text-xs">Account</Label>
          <Select value={account} onValueChange={setAccount}>
            <SelectTrigger id="pf-account" className="h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All accounts</SelectItem>
              {list.map((a) => (
                <SelectItem key={a.account_id} value={a.account_id}>
                  {a.name} · {fmtDollar(a.balance)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Panel title="Summary">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Equity" value={fmtDollar(equity)}
                sub={account === ALL ? `${list.length} accounts` : scoped?.provider} />
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
                  <tr key={i}>
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
                {d!.closed.slice(0, 200).map((t, i) => (
                  <tr key={i}>
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
    </div>
  );
}
