import { useMemo } from "react";
import { ArrowUpRight, ArrowDownRight, Loader2, X } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Stat } from "@/components/terminal/Panel";
import { ErrorState } from "@/components/terminal/States";
import { PriceChart, type Drawing } from "@/components/terminal/PriceChart";
import { useResource } from "@/lib/useResource";
import { api, type PositionRow } from "@/lib/api";
import { fmt, fmtDollar, pnlColor } from "@/lib/utils";

/** Trading days a window spans, used to pick a chart range around a trade. */
function daysBetween(a: string, b: string): number {
  const t0 = new Date(a).getTime(), t1 = new Date(b || a).getTime();
  if (!Number.isFinite(t0) || !Number.isFinite(t1)) return 5;
  return Math.max(2, Math.ceil(Math.abs(t1 - t0) / 86_400_000) + 4);
}

/**
 * A single trade, with the price action it happened in.
 *
 * A row in a table says what a trade did; this says what the market was
 * doing when it did it — which is the only way to tell a good decision from
 * a lucky one.
 */
export function TradeDetail({
  trade, open, onOpenChange, onClosed,
}: {
  trade: PositionRow | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onClosed?: () => void;
}) {
  const isOpen = !trade?.exit_time;
  const span = trade ? daysBetween(trade.entry_time, trade.exit_time) : 5;

  const hist = useResource(
    () => trade?.ticker
      ? api.orders.history(trade.ticker, span > 20 ? "1d" : "1h", span)
      : Promise.resolve(null as never),
    [trade?.ticker, span],
  );

  // Entry and exit as horizontal levels, so the trade is legible on the chart.
  const drawings = useMemo<Drawing[]>(() => {
    if (!trade) return [];
    const out: Drawing[] = [];
    if (trade.entry_price != null) {
      out.push({ id: "entry", kind: "hline",
                 points: [{ time: 0, price: trade.entry_price }], color: "#94a3b8" });
    }
    if (trade.exit_price != null) {
      out.push({ id: "exit", kind: "hline",
                 points: [{ time: 0, price: trade.exit_price }],
                 color: (trade.pnl ?? 0) >= 0 ? "#22c55e" : "#ef4444" });
    }
    return out;
  }, [trade]);

  if (!trade) return null;

  const long = trade.direction === "long";
  const notional = (trade.entry_price ?? 0) * (trade.size ?? 0);
  const movePct = trade.entry_price && trade.exit_price
    ? (trade.exit_price - trade.entry_price) / trade.entry_price * (long ? 1 : -1)
    : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span className="font-mono">{trade.ticker || "—"}</span>
            <Badge variant={long ? "profit" : "loss"} className="gap-1">
              {long ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
              {trade.direction}
            </Badge>
            {isOpen
              ? <Badge variant="secondary" className="text-[10px]">open</Badge>
              : <Badge variant="outline" className="text-[10px]">{trade.exit_reason || "closed"}</Badge>}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Size" value={trade.size != null ? fmt(trade.size, 4) : "—"} />
            <Stat label="Entry" value={trade.entry_price != null ? fmt(trade.entry_price) : "—"} />
            <Stat label={isOpen ? "Mark" : "Exit"}
                  value={(isOpen ? trade.mark : trade.exit_price) != null
                         ? fmt((isOpen ? trade.mark : trade.exit_price)!) : "—"} />
            <Stat label={isOpen ? "Unrealised" : "Realised"}
                  value={(isOpen ? trade.unrealised_pnl : trade.pnl) != null
                         ? fmtDollar((isOpen ? trade.unrealised_pnl : trade.pnl)!) : "—"}
                  tone={(() => {
                    const v = isOpen ? trade.unrealised_pnl : trade.pnl;
                    return v == null || v === 0 ? "neutral" : v > 0 ? "profit" : "loss";
                  })()} />
          </div>

          <div className="h-64 overflow-hidden rounded-lg border">
            {hist.error ? <ErrorState message={hist.error} onRetry={hist.reload} />
              : !hist.settled ? (
                <div className="flex h-full items-center justify-center">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              ) : (hist.data?.candles.length ?? 0) > 1 ? (
                <PriceChart candles={hist.data!.candles} kind="candles"
                            height={256} drawings={drawings} />
              ) : (
                <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                  No price data for this window.
                </div>
              )}
          </div>

          <div className="grid gap-2 rounded-lg border bg-muted/30 p-3 text-[11px] sm:grid-cols-2">
            {([
              ["Opened", trade.entry_time.replace("T", " ").slice(0, 19)],
              ["Closed", trade.exit_time ? trade.exit_time.replace("T", " ").slice(0, 19) : "still open"],
              ["Notional", fmtDollar(notional)],
              ["Move", movePct != null ? `${(movePct * 100).toFixed(2)}%` : "—"],
              ["Run", trade.run],
              ["Account", trade.account_id],
            ] as const).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3">
                <span className="text-muted-foreground">{k}</span>
                <span className="truncate font-mono">{v}</span>
              </div>
            ))}
          </div>

          {isOpen && trade.id && (
            <Button
              variant="destructive" className="w-full"
              onClick={async () => {
                try {
                  await api.positions.close(trade.id!);
                  onOpenChange(false);
                  onClosed?.();
                } catch { /* the panel's toast reports it */ }
              }}
            >
              <X className="h-4 w-4" /> Close at market
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
