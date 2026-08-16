import { useEffect, useState } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/ui/toast";
import { Sidebar } from "@/components/layout/Sidebar";
import { SettingsDialog } from "@/components/SettingsDialog";
import { Dashboard } from "@/pages/Dashboard";
import { Strategies } from "@/pages/Strategies";
import { Research } from "@/pages/Research";
import { Live } from "@/pages/Live";
import { Sessions } from "@/pages/Sessions";
import { Accounts } from "@/pages/Accounts";

const COLLAPSE_KEY = "mm.sidebar.collapsed";

function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.18 }}
      className="h-full overflow-auto"
    >
      {children}
    </motion.div>
  );
}

export function App() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  // Cmd/Ctrl+B toggles the sidebar, Cmd/Ctrl+, opens settings.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
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

  const routes: [string, React.ReactNode][] = [
    ["/", <Dashboard />],
    ["/strategies", <Strategies />],
    ["/research", <Research />],
    ["/live", <Live />],
    ["/sessions", <Sessions />],
    ["/accounts", <Accounts />],
  ];

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <div className="flex h-screen overflow-hidden">
          <Sidebar
            collapsed={collapsed}
            onToggle={() => setCollapsed((v) => !v)}
            onOpenSettings={() => setSettingsOpen(true)}
          />
          <main className="flex-1 overflow-hidden">
            <AnimatePresence mode="wait">
              <Routes location={location} key={location.pathname}>
                {routes.map(([path, el]) => (
                  <Route key={path} path={path} element={<PageTransition>{el}</PageTransition>} />
                ))}
              </Routes>
            </AnimatePresence>
          </main>
          <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
        </div>
      </TooltipProvider>
    </ToastProvider>
  );
}
