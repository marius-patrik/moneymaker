import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast";
import { Dock } from "@/components/terminal/Dock";
import { TopBar } from "@/components/terminal/TopBar";
import { InlineSearchResults } from "@/components/terminal/InlineSearchResults";
import { useView, type View } from "@/lib/useView";
import { Trade } from "@/pages/Trade";
import { Portfolio } from "@/pages/Portfolio";
import { History } from "@/pages/History";
import { Research } from "@/pages/Research";
import { Settings } from "@/pages/Settings";

const SCREENS: Record<View, () => JSX.Element> = {
  trade: Trade,
  portfolio: Portfolio,
  history: History,
  research: Research,
  settings: Settings,
};

export function App() {
  const { view, setView } = useView();
  const [inlineOpen, setInlineOpen] = useState(false);
  const [inlineQuery, setInlineQuery] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault(); setInlineOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Changing screen should not leave the phone search open behind it.
  useEffect(() => { setInlineOpen(false); setInlineQuery(""); }, [view]);

  const Screen = SCREENS[view];

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <div className="flex h-dvh flex-col overflow-hidden">
          <TopBar />

          {/* Bottom padding clears the floating dock. */}
          <main className="min-h-0 flex-1 overflow-hidden pb-24">
            <AnimatePresence mode="wait">
              <motion.div
                key={view}
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                transition={{ duration: 0.12 }}
                className="h-full min-h-0 overflow-y-auto"
              >
                <Screen />
              </motion.div>
            </AnimatePresence>
          </main>

          <InlineSearchResults open={inlineOpen} query={inlineQuery}
                               onClose={() => setInlineOpen(false)} />

          <Dock
            view={view}
            onSelect={setView}
            onInlineSearch={setInlineOpen}
            inlineQuery={inlineQuery}
            onInlineQuery={setInlineQuery}
            inlineOpen={inlineOpen}
          />

        </div>
      </TooltipProvider>
    </ToastProvider>
  );
}
