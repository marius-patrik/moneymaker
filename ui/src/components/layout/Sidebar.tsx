import { NavLink } from "react-router-dom";
import { motion } from "motion/react";
import {
  LayoutDashboard,
  Zap,
  Activity,
  FileText,
  Wallet,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/strategies", icon: Zap, label: "Strategies" },
  { to: "/live", icon: Activity, label: "Live" },
  { to: "/sessions", icon: FileText, label: "Sessions" },
  { to: "/accounts", icon: Wallet, label: "Accounts" },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-56 flex-col border-r bg-card">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <TrendingUp className="h-5 w-5 text-primary" />
        <span className="text-sm font-bold tracking-tight">moneymaker</span>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {nav.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === "/"}>
            {({ isActive }) => (
              <motion.div
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.97 }}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </motion.div>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
