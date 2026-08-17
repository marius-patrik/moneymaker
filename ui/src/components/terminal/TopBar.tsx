import { useEffect, useState } from "react";
import { TrendingUp, ChevronDown, Check, Layers } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import {
  Select, SelectContent, SelectItem, SelectTrigger,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useAccount } from "@/lib/useAccount";
import { useResource } from "@/lib/useResource";
import { api, type Stats } from "@/lib/api";
import { cn, fmtDollar, fmtPct, pnlColor } from "@/lib/utils";

/**
 * Global context bar.
 *
 * The account selected here is the account everything acts on — the order
 * ticket used to carry its own selector, which meant the header said one
 * thing and the ticket could do another.
 */
export function TopBar() {
  const [clock, setClock] = useState(() => new Date());
  const [online, setOnline] = useState(true);
  const { accountId, setAccountId, isAll } = useAccount();

  const accounts = useResource(() => api.accounts.list(), []);
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const load = () =>
      api.stats.get()
        .then((v) => { setStats(v); setOnline(true); })
        .catch(() => setOnline(false));
    load();
    const s = setInterval(load, 15000);
    const c = setInterval(() => setClock(new Date()), 1000);
    return () => { clearInterval(s); clearInterval(c); };
  }, []);

  const list = accounts.data?.accounts ?? [];
  const current = list.find((a) => a.account_id === accountId);
  const live = (stats?.live_sessions ?? 0) > 0;

  return (
    <header className="glass z-40 flex h-12 shrink-0 items-center gap-3 border-b px-3 sm:px-4">
      {/* The name appears on hover; the mark alone is enough once you know
          what you are looking at, and the space is better spent on figures. */}
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="group flex shrink-0 cursor-default items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <AnimatePresence>
              <motion.span
                initial={{ width: 0, opacity: 0 }}
                whileHover={{ width: "auto", opacity: 1 }}
                className="hidden overflow-hidden whitespace-nowrap text-[13px] font-semibold tracking-tight group-hover:inline"
              >
                moneymaker
              </motion.span>
            </AnimatePresence>
          </span>
        </TooltipTrigger>
        <TooltipContent side="bottom">moneymaker</TooltipContent>
      </Tooltip>

      {/* Account context */}
      <Select value={accountId} onValueChange={setAccountId}>
        <SelectTrigger
          aria-label="Account"
          className="h-7 w-auto shrink-0 gap-1.5 border-0 bg-muted/60 px-2 text-[12px] font-medium shadow-none focus:ring-0"
        >
          <span className="flex items-center gap-1.5">
            {isAll && <Layers className="h-3 w-3 text-primary" />}
            <span className="max-w-28 truncate">
              {isAll ? "All accounts" : current?.name ?? "Account"}
            </span>
          </span>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__all__">
            <span className="flex items-center gap-2">
              <Layers className="h-3 w-3" /> All accounts
            </span>
          </SelectItem>
          {list.map((a) => (
            <SelectItem key={a.account_id} value={a.account_id}>
              {a.name} · {fmtDollar(a.balance)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="flex min-w-0 flex-1 items-center gap-4 sm:gap-6">
        <Metric label="Equity" value={stats ? fmtDollar(stats.total_balance) : "—"} />
        <Metric label="P&L" value={stats ? fmtDollar(stats.total_pnl) : "—"}
                tone={stats ? pnlColor(stats.total_pnl) : undefined} />
        {stats && stats.open_positions > 0 && (
          <Metric label="Open" value={fmtDollar(stats.unrealised_pnl)}
                  tone={pnlColor(stats.unrealised_pnl)} />
        )}
        <Metric label="Win" value={stats?.win_rate != null ? fmtPct(stats.win_rate) : "—"}
                className="hidden min-[620px]:flex" />
      </div>

      <div className="flex shrink-0 items-center gap-2.5">
        {/* Only shown when it means something: a session is actually live,
            or the server has stopped answering. A permanent dot that is
            usually grey communicates nothing. */}
        {!online ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="rounded bg-loss/15 px-1.5 py-0.5 text-[10px] font-medium text-loss">
                offline
              </span>
            </TooltipTrigger>
            <TooltipContent side="bottom">The server stopped responding.</TooltipContent>
          </Tooltip>
        ) : live ? (
          <span className="flex items-center gap-1.5 rounded bg-profit/15 px-1.5 py-0.5">
            <span className="live-dot" />
            <span className="text-[10px] font-medium text-profit">live</span>
          </span>
        ) : null}
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
    <div className={cn("flex shrink-0 items-baseline gap-1.5", className)}>
      <span className="text-[10px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
        {label}
      </span>
      <span className={cn("font-mono text-[13px] font-semibold tabular-nums", tone)}>
        {value}
      </span>
    </div>
  );
}
