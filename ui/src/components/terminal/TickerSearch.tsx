import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Search, Loader2, X } from "lucide-react";
import { api, type Instrument } from "@/lib/api";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<string, string> = {
  future: "FUT", equity: "STK", etf: "ETF", index: "IDX",
  currency: "FX", cryptocurrency: "CRY", mutualfund: "FUND",
};

/**
 * Instrument search.
 *
 * Symbols like GC=F or NQ=F are not guessable, so a system is pointed at an
 * instrument by searching for it by name and picking from the results.
 */
export function TickerSearch({
  value, onSelect, className,
}: { value: string; onSelect: (symbol: string) => void; className?: string }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Instrument[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [cursor, setCursor] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const q = query.trim();
    if (!q) { setResults([]); return; }
    let alive = true;
    setLoading(true);
    const t = setTimeout(() => {
      api.orders.search(q)
        .then((r) => { if (alive) { setResults(r.results); setCursor(0); } })
        .catch(() => { if (alive) setResults([]); })
        .finally(() => { if (alive) setLoading(false); });
    }, 300);
    return () => { alive = false; clearTimeout(t); };
  }, [query]);

  // Close when focus or a click leaves the control.
  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  function choose(sym: string) {
    onSelect(sym);
    setQuery(""); setOpen(false);
  }

  return (
    <div ref={boxRef} className={cn("relative", className)}>
      <div className="flex h-8 items-center gap-2 rounded-lg border bg-background px-2.5">
        <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <input
          value={open ? query : value}
          onFocus={() => { setOpen(true); setQuery(""); }}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, results.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
            else if (e.key === "Enter" && results[cursor]) { e.preventDefault(); choose(results[cursor].symbol); }
            else if (e.key === "Escape") setOpen(false);
          }}
          aria-label="Search instruments"
          placeholder="Search…"
          className="w-full bg-transparent font-mono text-xs outline-none placeholder:font-sans placeholder:text-muted-foreground"
        />
        {loading && <Loader2 className="h-3 w-3 shrink-0 animate-spin text-muted-foreground" />}
        {open && query && !loading && (
          <button onClick={() => setQuery("")} aria-label="Clear search">
            <X className="h-3 w-3 text-muted-foreground" />
          </button>
        )}
      </div>

      <AnimatePresence>
        {open && (query.trim() || results.length > 0) && (
          <motion.div
            initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
            className="glass-strong absolute left-0 right-0 top-9 z-50 max-h-72 overflow-y-auto rounded-lg border shadow-xl"
          >
            {loading && results.length === 0 ? (
              <p className="px-3 py-4 text-center text-[11px] text-muted-foreground">Searching…</p>
            ) : results.length === 0 ? (
              <p className="px-3 py-4 text-center text-[11px] text-muted-foreground">
                No instruments match “{query}”.
              </p>
            ) : (
              results.map((r, i) => (
                <button
                  key={`${r.symbol}-${i}`}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => choose(r.symbol)}
                  className={cn(
                    "flex w-full items-center gap-2 px-2.5 py-2 text-left transition-colors",
                    i === cursor ? "bg-accent" : ""
                  )}
                >
                  <span className="w-8 shrink-0 rounded bg-muted px-1 py-0.5 text-center font-mono text-[9px] text-muted-foreground">
                    {TYPE_LABEL[r.type] ?? r.type.slice(0, 3).toUpperCase()}
                  </span>
                  <span className="w-20 shrink-0 truncate font-mono text-xs font-medium">{r.symbol}</span>
                  <span className="min-w-0 flex-1 truncate text-[11px] text-muted-foreground">{r.name}</span>
                  <span className="shrink-0 text-[10px] text-muted-foreground">{r.exchange}</span>
                </button>
              ))
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
