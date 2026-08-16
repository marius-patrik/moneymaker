import { useEffect, useState } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast";
import { Sidebar, MobileNav } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/terminal/TopBar";
import { StatusBar } from "@/components/terminal/StatusBar";
import { CommandPalette } from "@/components/terminal/CommandPalette";
import { SettingsDialog } from "@/components/SettingsDialog";
import { Dashboard } from "@/pages/Dashboard";
import { Strategies } from "@/pages/Strategies";
import { Research } from "@/pages/Research";
import { Trade } from "@/pages/Trade";
import { Accounts } from "@/pages/Accounts";

const COLLAPSE_KEY = "mm.sidebar.collapsed";

function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.14 }}
      className="h-full overflow-y-auto overflow-x-hidden"
    >
      {children}
    </motion.div>
  );
}

export function App() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMobileOpen(false);
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === "k") { e.preventDefault(); setPaletteOpen((v) => !v); }
      else if (e.key === "b") { e.preventDefault(); setCollapsed((v) => !v); }
      else if (e.key === ",") { e.preventDefault(); setSettingsOpen(true); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const routes: [string, React.ReactNode][] = [
    ["/", <Dashboard />],
    ["/strategies", <Strategies />],
    ["/research", <Research />],
    ["/trade", <Trade />],
    ["/accounts", <Accounts />],
  ];

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        {/* Terminal chrome: context bar on top, status strip at the bottom,
            navigation rail on the left, work in the middle. */}
        <div className="flex h-dvh flex-col overflow-hidden">
          <TopBar onOpenNav={() => setMobileOpen(true)}
                  onOpenPalette={() => setPaletteOpen(true)} />

          <div className="flex min-h-0 flex-1 overflow-hidden">
            <Sidebar
              collapsed={collapsed}
              onToggle={() => setCollapsed((v) => !v)}
              onOpenSettings={() => setSettingsOpen(true)}
            />
            <MobileNav
              open={mobileOpen}
              onClose={() => setMobileOpen(false)}
              onOpenSettings={() => setSettingsOpen(true)}
            />
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

          <StatusBar />

          <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
          <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}
                          onOpenSettings={() => setSettingsOpen(true)} />
        </div>
      </TooltipProvider>
    </ToastProvider>
  );
}
