import { useEffect, useState } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast";
import { Sidebar } from "@/components/layout/Sidebar";
import { BottomNav } from "@/components/terminal/SectionNav";
import { TopBar } from "@/components/terminal/TopBar";
import { CommandPalette } from "@/components/terminal/CommandPalette";
import { SettingsDialog } from "@/components/SettingsDialog";
import { Dashboard } from "@/pages/Dashboard";
import { Workspace } from "@/pages/Workspace";
import { Accounts } from "@/pages/Accounts";

function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.12 }}
      className="h-full min-h-0"
    >
      {children}
    </motion.div>
  );
}

export function App() {
  const location = useLocation();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === "k") { e.preventDefault(); setPaletteOpen((v) => !v); }
      else if (e.key === ",") { e.preventDefault(); setSettingsOpen(true); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const routes: [string, React.ReactNode][] = [
    ["/", <Dashboard />],
    ["/workspace", <Workspace />],
    ["/portfolio", <Accounts />],
  ];

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <div className="flex h-dvh flex-col overflow-hidden">
          <TopBar onOpenPalette={() => setPaletteOpen(true)} />

          <div className="flex min-h-0 flex-1 overflow-hidden">
            <Sidebar onOpenSettings={() => setSettingsOpen(true)} />
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

          {/* Mobile navigation lives at the bottom, within thumb reach. */}
          <BottomNav onOpenSettings={() => setSettingsOpen(true)} />

          <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}
                          onOpenSettings={() => setSettingsOpen(true)} />
        </div>
      </TooltipProvider>
    </ToastProvider>
  );
}
