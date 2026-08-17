import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Loader2 } from "lucide-react";
import { goTo, viewFromRoute } from "@/lib/useView";
import { api, type QuickGroup } from "@/lib/api";

/**
 * Search results, shown above the dock.
 *
 * A modal covers the screen it is searching, so the dock becomes the input
 * and the answers stack directly above it — the same at every width.
 */
export function InlineSearchResults({
  open, query, onClose,
}: { open: boolean; query: string; onClose: () => void }) {
  const [groups, setGroups] = useState<QuickGroup[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (!open || !q) { setGroups([]); return; }
    let alive = true;
    setLoading(true);
    const t = setTimeout(() => {
      api.orders.quickSearch(q)
        .then((r) => { if (alive) setGroups(r.groups); })
        .catch(() => { if (alive) setGroups([]); })
        .finally(() => { if (alive) setLoading(false); });
    }, 220);
    return () => { alive = false; clearTimeout(t); };
  }, [open, query]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-30 bg-black/50"
          />
          <motion.div
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }} transition={{ duration: 0.15 }}
            className="glass-strong fixed bottom-[6rem] left-1/2 z-40 max-h-[55dvh] w-[min(28rem,calc(100vw-1.5rem))] -translate-x-1/2 overflow-y-auto rounded-2xl border shadow-2xl"
          >
            {!query.trim() ? (
              <p className="px-4 py-6 text-center text-[11px] text-muted-foreground">
                Search instruments, systems, accounts and history.
              </p>
            ) : loading && groups.length === 0 ? (
              <div className="flex justify-center py-6">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            ) : groups.length === 0 ? (
              <p className="px-4 py-6 text-center text-[11px] text-muted-foreground">
                Nothing matches “{query}”.
              </p>
            ) : (
              groups.map((g) => (
                <div key={g.group}>
                  <div className="px-3 pb-1 pt-2.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    {g.group}
                  </div>
                  {g.items.map((it) => (
                    <button
                      key={`${g.group}-${it.id}`}
                      onClick={() => {
                        if (g.group === "Instruments") localStorage.setItem("mm.ticker", it.id);
                        if (g.group === "Systems") localStorage.setItem("mm.strategy", it.id);
                        goTo(viewFromRoute(it.route));
                        onClose();
                      }}
                      className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left transition-colors active:bg-accent"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm">{it.label}</span>
                        {it.sub && (
                          <span className="block truncate text-[10px] text-muted-foreground">
                            {it.sub}
                          </span>
                        )}
                      </span>
                    </button>
                  ))}
                </div>
              ))
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
