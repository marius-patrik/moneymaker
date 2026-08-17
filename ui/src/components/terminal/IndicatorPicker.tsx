import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Plus, X, LineChart } from "lucide-react";
import { api, type IndicatorMeta } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ActiveIndicator {
  kind: string;
  label: string;
  period: number;
}

/**
 * Indicator selection for the chart.
 *
 * Strategies already reason about moving averages and VWAP, so the chart
 * showing them is what lets you see what a system was reacting to.
 */
export function IndicatorPicker({
  active, onChange,
}: { active: ActiveIndicator[]; onChange: (v: ActiveIndicator[]) => void }) {
  const [catalog, setCatalog] = useState<IndicatorMeta[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.orders.indicators().then((r) => setCatalog(r.indicators)).catch(() => {});
  }, []);

  function add(meta: IndicatorMeta) {
    const period = meta.params.period ?? 20;
    if (active.some((a) => a.kind === meta.kind && a.period === period)) return;
    onChange([...active, { kind: meta.kind, label: meta.label, period }]);
    setOpen(false);
  }

  return (
    <div className="flex items-center gap-1">
      <AnimatePresence initial={false}>
        {active.map((a, i) => (
          <motion.span
            key={`${a.kind}-${a.period}`}
            initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }} transition={{ duration: 0.12 }}
            className="group flex items-center gap-1 rounded bg-muted/70 px-1.5 py-0.5 font-mono text-[10px]"
          >
            <span className="h-1.5 w-1.5 rounded-full"
                  style={{ background: ["#f59e0b", "#38bdf8", "#a78bfa", "#f472b6"][i % 4] }} />
            {a.label}{a.kind !== "vwap" ? ` ${a.period}` : ""}
            <button onClick={() => onChange(active.filter((_, j) => j !== i))}
                    aria-label={`Remove ${a.label}`}
                    className="text-muted-foreground hover:text-foreground">
              <X className="h-2.5 w-2.5" />
            </button>
          </motion.span>
        ))}
      </AnimatePresence>

      <div className="relative">
        <button onClick={() => setOpen((v) => !v)}
                aria-label="Add indicator"
                className={cn("flex items-center gap-1 rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                              open && "bg-accent text-foreground")}>
          <LineChart className="h-3.5 w-3.5" />
          <Plus className="h-2.5 w-2.5" />
        </button>

        <AnimatePresence>
          {open && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
              <motion.div
                initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.12 }}
                className="glass-strong absolute right-0 top-7 z-50 w-40 overflow-hidden rounded-lg border shadow-xl"
              >
                {catalog.map((m) => (
                  <button key={m.kind} onClick={() => add(m)}
                          className="flex w-full items-center justify-between px-2.5 py-1.5 text-left text-xs transition-colors hover:bg-accent">
                    <span>{m.label}</span>
                    {m.params.period && (
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {m.params.period}
                      </span>
                    )}
                  </button>
                ))}
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
