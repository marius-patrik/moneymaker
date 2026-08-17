import { useRef, useState } from "react";
import {
  motion, useMotionValue, useSpring, useTransform, AnimatePresence,
} from "motion/react";
import { CandlestickChart, Wallet, FlaskConical, Settings, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { type View } from "@/lib/useView";
import { AnimatedIcon, type IconMotion } from "@/components/ui/animated-icon";

export const SECTIONS: {
  view: View; icon: React.ElementType; label: string; motion: IconMotion;
}[] = [
  { view: "trade",     icon: CandlestickChart, label: "Trade",     motion: "draw" },
  { view: "portfolio", icon: Wallet,           label: "Portfolio", motion: "lift" },
  { view: "research",  icon: FlaskConical,     label: "Research",  motion: "wiggle" },
  { view: "settings",  icon: Settings,         label: "Settings",  motion: "wiggle" },
];

/**
 * One dock item, magnifying as the cursor approaches.
 *
 * The scale is driven by horizontal distance from the item's centre, which
 * is what makes the effect feel like a lens rather than a hover state.
 */
function DockIcon({
  mouseX, view, icon, label, motion: m, active, onSelect,
}: {
  mouseX: ReturnType<typeof useMotionValue<number>>;
  view: View; icon: React.ElementType; label: string; motion: IconMotion;
  active: boolean; onSelect: (v: View) => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);

  const distance = useTransform(mouseX, (x) => {
    const b = ref.current?.getBoundingClientRect();
    if (!b) return Infinity;
    return x - (b.x + b.width / 2);
  });
  const scaleRaw = useTransform(distance, [-90, 0, 90], [1, 1.4, 1]);
  const liftRaw = useTransform(distance, [-90, 0, 90], [0, -5, 0]);
  const spring = { mass: 0.1, stiffness: 210, damping: 15 } as const;
  const scale = useSpring(scaleRaw, spring);
  const y = useSpring(liftRaw, spring);

  return (
    <button ref={ref} onClick={() => onSelect(view)} title={label}
            aria-label={label}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group flex w-14 shrink-0 flex-col items-center justify-center gap-1 text-[9px] font-medium transition-colors sm:w-16",
              active ? "text-accent-blue" : "text-muted-foreground hover:text-foreground"
            )}>
      {/* Only the glyph magnifies — scaling the whole slot would push its
          neighbours sideways and the labels would drift apart. The selected
          pill sits behind the icon rather than under the label, so the
          indicator moves with the thing being magnified. */}
      <motion.span
        style={{ scale, y }}
        className={cn(
          "flex h-7 w-11 items-center justify-center rounded-full transition-colors",
          active ? "bg-accent-blue/20" : "bg-transparent"
        )}
      >
        <AnimatedIcon icon={icon} motionType={m} className="h-[18px] w-[18px]" />
      </motion.span>
      <span className="leading-none">{label}</span>
    </button>
  );
}

/**
 * The dock.
 *
 * One navigation component at every width, and one search behaviour: the
 * dock becomes the input and results stack above it. A centred modal was a
 * second pattern to maintain that behaved differently from the phone for no
 * reason a user could name.
 */
export function Dock({
  view, onSelect, onInlineSearch, inlineQuery, onInlineQuery, inlineOpen,
}: {
  view: View;
  onSelect: (v: View) => void;
  onInlineSearch: (open: boolean) => void;
  inlineQuery: string;
  onInlineQuery: (q: string) => void;
  inlineOpen: boolean;
}) {
  const mouseX = useMotionValue(Infinity);
  const half = Math.ceil(SECTIONS.length / 2);
  const inputRef = useRef<HTMLInputElement>(null);

  const body = (
    <div
      onMouseMove={(e) => mouseX.set(e.clientX)}
      onMouseLeave={() => mouseX.set(Infinity)}
      className="flex h-16 w-full items-center justify-around gap-0 overflow-x-auto px-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:w-auto sm:justify-center"
    >
      <AnimatePresence mode="wait" initial={false}>
        {inlineOpen ? (
          // Phone: the dock becomes the search field, results sit above it.
          <motion.div
            key="search"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="flex w-[min(22rem,calc(100vw-3rem))] items-center gap-2 px-2"
          >
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input
              ref={inputRef}
              autoFocus
              value={inlineQuery}
              onChange={(e) => onInlineQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Escape") onInlineSearch(false); }}
              aria-label="Search"
              placeholder="Instruments, systems, accounts…"
              className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            <button onClick={() => onInlineSearch(false)} aria-label="Close search"
                    className="shrink-0 rounded-full p-1.5 text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </motion.div>
        ) : (
          <motion.div
            key="nav"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="flex w-full items-center justify-around sm:justify-center"
          >
            {SECTIONS.slice(0, half).map((s) => (
              <DockIcon key={s.view} mouseX={mouseX} {...s}
                        active={view === s.view} onSelect={onSelect} />
            ))}

            <button
              onClick={() => onInlineSearch(true)}
              aria-label="Search"
              className="group mx-0.5 flex w-11 shrink-0 items-center justify-center sm:mx-1 sm:w-12"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-accent-blue text-white shadow-lg transition-transform group-hover:scale-110 group-active:scale-95">
                <AnimatedIcon icon={Search} motionType="pop" className="h-4 w-4" />
              </span>
            </button>

            {SECTIONS.slice(half).map((s) => (
              <DockIcon key={s.view} mouseX={mouseX} {...s}
                        active={view === s.view} onSelect={onSelect} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center p-3 sm:p-4">
      <div className="liquid-glass pointer-events-auto w-full overflow-hidden rounded-full sm:w-auto">
        {body}
      </div>
    </div>
  );
}
