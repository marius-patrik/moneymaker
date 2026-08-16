import { useEffect, useState } from "react";
import { TrendingUp, Search } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, type Stats, type AppConfig } from "@/lib/api";
import { fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

/**
 * Global context strip.
 *
 * A trading terminal keeps the numbers that matter on screen at all times —
 * equity, P&L, whether anything is running — so they are never a navigation
 * away. This is the single most "terminal" element in the app.
 */
export function TopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [clock, setClock] = useState(() => new Date());
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const load = () =>
      api.stats.get()
        .then((v) => { setStats(v); setOnline(true); })
        .catch(() => setOnline(false));
    load();
    api.config.get().then(setConfig).catch(() => {});
    const s = setInterval(load, 15000);
    const c = setInterval(() => setClock(new Date()), 1000);
    return () => { clearInterval(s); clearInterval(c); };
  }, []);

  const live = (stats?.live_sessions ?? 0) > 0;

  return (
    <header className="glass z-40 flex h-12 shrink-0 items-center gap-3 border-b px-3 sm:px-4">
      <div className="flex shrink-0 items-center gap-2">
        <TrendingUp className="h-4 w-4 text-primary" />
        <span className="text-[13px] font-semibold tracking-tight sm:inline">moneymaker</span>
      </div>

      {/* Live account context — the reason this bar exists. */}
      <div className="flex min-w-0 flex-1 items-center gap-4 sm:gap-6">
        <Metric label="Equity" value={stats ? fmtDollar(stats.total_balance) : "—"} />
        <Metric label="P&L" value={stats ? fmtDollar(stats.total_pnl) : "—"}
                tone={stats ? pnlColor(stats.total_pnl) : undefined} />
        {stats && stats.open_positions > 0 && (
          <Metric label="Open" value={fmtDollar(stats.unrealised_pnl)}
                  tone={pnlColor(stats.unrealised_pnl)} />
        )}
        <Metric label="Win" value={stats?.win_rate != null ? fmtPct(stats.win_rate) : "—"}
                className="hidden min-[560px]:flex" />
        <Metric label="Trades" value={stats ? String(stats.trades) : "—"} className="hidden min-[720px]:flex" />
      </div>

      <button
        onClick={onOpenPalette}
        className="hidden items-center gap-2 rounded-md border px-2.5 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:flex"
      >
        <Search className="h-3 w-3" />
        <span>Search</span>
        <kbd className="rounded border bg-muted px-1 font-mono text-[10px]">⌘K</kbd>
      </button>

      <div className="flex shrink-0 items-center gap-2.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="flex items-center gap-1.5">
              <span className={
                !online ? "h-2 w-2 rounded-full bg-loss"
                : live ? "live-dot"
                : "h-2 w-2 rounded-full bg-muted-foreground/40"} />
            </span>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            {!online ? "Disconnected" : live ? "Trading" : "Connected · flat"}
            {config && <span className="block text-muted-foreground">v{config.version}</span>}
          </TooltipContent>
        </Tooltip>
        <span className="hidden font-mono text-[11px] tabular-nums text-muted-foreground sm:inline">
          {clock.toLocaleTimeString("en-GB")}
        </span>
      </div>
    </header>
  );
}

function Metric({
  label, value, tone, className,
}: { label: string; value: string; tone?: string; className?: string }) {
  return (
    <div className={`flex shrink-0 items-baseline gap-1.5 ${className ?? ""}`}>
      <span className="text-[10px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
        {label}
      </span>
      <span className={`font-mono text-[13px] font-semibold tabular-nums ${tone ?? ""}`}>
        {value}
      </span>
    </div>
  );
}
