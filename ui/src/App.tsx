import { useEffect, useState } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast";
import { Sidebar } from "@/components/layout/Sidebar";
import { BottomNav } from "@/components/terminal/SectionNav";
import { TopBar } from "@/components/terminal/TopBar";
import { CommandPalette } from "@/components/terminal/CommandPalette";
import { Dashboard } from "@/pages/Dashboard";
import { Trade } from "@/pages/Trade";
import { Strategies } from "@/pages/Strategies";
import { News } from "@/pages/News";
import { Portfolio } from "@/pages/Portfolio";
import { Settings } from "@/pages/Settings";

function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.12 }}
      className="h-full min-h-0 overflow-y-auto"
    >
      {children}
    </motion.div>
  );
}

export function App() {
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault(); setPaletteOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const routes: [string, React.ReactNode][] = [
    ["/", <Dashboard />],
    ["/trade", <Trade />],
    ["/strategies", <Strategies />],
    ["/news", <News />],
    ["/portfolio", <Portfolio />],
    ["/settings", <Settings />],
  ];

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <div className="flex h-dvh flex-col overflow-hidden">
          <TopBar onOpenPalette={() => setPaletteOpen(true)} />

          <div className="flex min-h-0 flex-1 overflow-hidden">
            <Sidebar />
            <main className="min-w-0 flex-1 overflow-hidden">
              <AnimatePresence mode="wait">
                <Routes location={location} key={location.pathname}>
                  {routes.map(([path, el]) => (
                    <Route key={path} path={path}
                           element={<PageTransition>{el}</PageTransition>} />
                  ))}
                </Routes>
              </AnimatePresence>
            </main>
          </div>

          {/* Mobile navigation sits within thumb reach. */}
          <BottomNav />

          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
        </div>
      </TooltipProvider>
    </ToastProvider>
  );
}
