import { useEffect, useState } from "react";
import { TrendingUp, PanelLeftOpen, Search, Loader2 } from "lucide-react";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { api, type Stats } from "@/lib/api";
import { fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

/**
 * Global context strip.
 *
 * A trading terminal keeps the numbers that matter on screen at all times —
 * equity, P&L, whether anything is running — so they are never a navigation
 * away. This is the single most "terminal" element in the app.
 */
export function TopBar({
  onOpenNav, onOpenPalette,
}: { onOpenNav: () => void; onOpenPalette: () => void }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [clock, setClock] = useState(() => new Date());

  useEffect(() => {
    const load = () => api.stats.get().then(setStats).catch(() => {});
    load();
    const s = setInterval(load, 15000);
    const c = setInterval(() => setClock(new Date()), 1000);
    return () => { clearInterval(s); clearInterval(c); };
  }, []);

  const live = (stats?.live_sessions ?? 0) > 0;

  return (
    <header className="glass z-40 flex h-12 shrink-0 items-center gap-3 border-b px-3 sm:px-4">
      <button
        onClick={onOpenNav}
        aria-label="Open menu"
        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:hidden"
      >
        <AnimatedIcon icon={PanelLeftOpen} motionType="nudge" className="h-4 w-4" />
      </button>

      <div className="hidden items-center gap-2 md:flex">
        <TrendingUp className="h-4 w-4 text-primary" />
        <span className="text-[13px] font-semibold tracking-tight">moneymaker</span>
      </div>

      {/* Live account context — the reason this bar exists. */}
      <div className="flex min-w-0 flex-1 items-center gap-4 sm:gap-6">
        <Metric label="Equity" value={stats ? fmtDollar(stats.total_balance) : "—"} />
        <Metric label="P&L" value={stats ? fmtDollar(stats.total_pnl) : "—"}
                tone={stats ? pnlColor(stats.total_pnl) : undefined} />
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

      <div className="flex shrink-0 items-center gap-2">
        <span className={live ? "live-dot" : "h-2 w-2 rounded-full bg-muted-foreground/40"} />
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
