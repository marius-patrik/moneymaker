import { Routes, Route } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { useLocation } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Dashboard } from "@/pages/Dashboard";
import { Strategies } from "@/pages/Strategies";
import { Live } from "@/pages/Live";
import { Sessions } from "@/pages/Sessions";
import { Accounts } from "@/pages/Accounts";

function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.18 }}
      className="flex-1 overflow-auto"
    >
      {children}
    </motion.div>
  );
}

export function App() {
  const location = useLocation();
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={<PageTransition><Dashboard /></PageTransition>} />
            <Route path="/strategies" element={<PageTransition><Strategies /></PageTransition>} />
            <Route path="/live" element={<PageTransition><Live /></PageTransition>} />
            <Route path="/sessions" element={<PageTransition><Sessions /></PageTransition>} />
            <Route path="/accounts" element={<PageTransition><Accounts /></PageTransition>} />
          </Routes>
        </AnimatePresence>
      </main>
    </div>
  );
}
