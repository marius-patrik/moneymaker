import { useEffect, useState } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { PanelLeftOpen, TrendingUp } from "lucide-react";
import { AnimatedIcon, MotionHost } from "@/components/ui/animated-icon";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast";
import { Sidebar, MobileNav, NAV } from "@/components/layout/Sidebar";
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
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.18 }}
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

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMobileOpen(false);
      if (!(e.metaKey || e.ctrlKey)) return;
      if (e.key === "b") {
        e.preventDefault();
        setCollapsed((v) => !v);
      } else if (e.key === ",") {
        e.preventDefault();
        setSettingsOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const title = NAV.find((n) => n.to === location.pathname)?.label ?? "moneymaker";

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
        <div className="flex h-dvh overflow-hidden">
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

          <div className="flex min-w-0 flex-1 flex-col">
            {/* Mobile top bar — the only way to reach nav below md. */}
            <header className="flex h-14 shrink-0 items-center gap-3 border-b bg-card px-4 md:hidden">
              <MotionHost>
                <button
                  onClick={() => setMobileOpen(true)}
                  aria-label="Open menu"
                  className="-ml-1 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <AnimatedIcon icon={PanelLeftOpen} motionType="nudge" className="h-5 w-5" />
                </button>
              </MotionHost>
              <div className="flex min-w-0 items-center gap-2">
                <TrendingUp className="h-4 w-4 shrink-0 text-primary" />
                <span className="truncate text-sm font-bold tracking-tight">{title}</span>
              </div>
            </header>

            <main className="min-h-0 flex-1 overflow-hidden">
              <AnimatePresence mode="wait">
                <Routes location={location} key={location.pathname}>
                  {routes.map(([path, el]) => (
                    <Route key={path} path={path} element={<PageTransition>{el}</PageTransition>} />
                  ))}
                </Routes>
              </AnimatePresence>
            </main>
          </div>

          <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
        </div>
      </TooltipProvider>
    </ToastProvider>
  );
}
