import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { Search, CornerDownLeft } from "lucide-react";
import { SECTIONS } from "@/components/terminal/SectionNav";
import { api, type Strategy } from "@/lib/api";

interface Command {
  id: string;
  label: string;
  hint?: string;
  group: string;
  run: () => void;
}

/**
 * Cmd/Ctrl+K palette.
 *
 * Navigation and strategies in one searchable list, so the app is reachable
 * from the keyboard the way a terminal is expected to be.
 */
export function CommandPalette({
  open, onClose,
}: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery(""); setCursor(0);
    inputRef.current?.focus();
    api.strategies.list().then((r) => setStrategies(r.strategies)).catch(() => {});
  }, [open]);

  const commands: Command[] = useMemo(() => [
    ...SECTIONS.map((n: { to: string; label: string }) => ({
      id: `nav:${n.to}`, label: n.label, group: "Go to",
      run: () => { navigate(n.to); onClose(); },
    })),
    { id: "settings", label: "Settings", group: "Go to",
      run: () => { navigate("/settings"); onClose(); } },
    ...strategies.map((s) => ({
      id: `strat:${s.name}`, label: s.name, group: "Strategies",
      run: () => { navigate("/workspace"); onClose(); },
    })),
  ], [strategies, navigate, onClose]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(q));
  }, [commands, query]);

  useEffect(() => { setCursor(0); }, [query]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowDown") {
        e.preventDefault(); setCursor((c) => Math.min(c + 1, results.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault(); setCursor((c) => Math.max(c - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault(); results[cursor]?.run();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, results, cursor, onClose]);

  let lastGroup = "";

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-[60] bg-black/50"
          />
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            role="dialog"
            aria-label="Command palette"
            className="glass-strong fixed left-1/2 top-[12vh] z-[61] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 overflow-hidden rounded-xl border shadow-2xl"
          >
            <div className="flex items-center gap-2 border-b px-3">
              <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search pages and strategies…"
                aria-label="Search commands"
                className="h-11 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <kbd className="hidden shrink-0 rounded border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:block">
                esc
              </kbd>
            </div>

            <div className="max-h-[52vh] overflow-y-auto p-1.5">
              {results.length === 0 && (
                <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                  Nothing matches “{query}”.
                </p>
              )}
              {results.map((c, i) => {
                const header = c.group !== lastGroup ? c.group : null;
                lastGroup = c.group;
                return (
                  <div key={c.id}>
                    {header && (
                      <div className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                        {header}
                      </div>
                    )}
                    <button
                      onMouseEnter={() => setCursor(i)}
                      onClick={c.run}
                      className={`flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors ${
                        i === cursor ? "bg-accent text-accent-foreground" : "text-foreground"
                      }`}
                    >
                      <span className="truncate">{c.label}</span>
                      <span className="flex shrink-0 items-center gap-2">
                        {c.hint && (
                          <span className="font-mono text-[10px] text-muted-foreground">{c.hint}</span>
                        )}
                        {i === cursor && <CornerDownLeft className="h-3 w-3 text-muted-foreground" />}
                      </span>
                    </button>
                  </div>
                );
              })}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
