import { NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import {
  LayoutDashboard,
  Zap,
  Activity,
  FileText,
  Wallet,
  TrendingUp,
  FlaskConical,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/strategies", icon: Zap, label: "Strategies" },
  { to: "/research", icon: FlaskConical, label: "Research" },
  { to: "/live", icon: Activity, label: "Live" },
  { to: "/sessions", icon: FileText, label: "Sessions" },
  { to: "/accounts", icon: Wallet, label: "Accounts" },
];

function NavItems({
  collapsed, onNavigate,
}: { collapsed: boolean; onNavigate?: () => void }) {
  return (
    <>
      {NAV.map(({ to, icon: Icon, label }) => {
        const link = (
          <NavLink key={to} to={to} end={to === "/"} onClick={onNavigate}>
            {({ isActive }) => (
              <motion.div
                whileHover={{ x: collapsed ? 0 : 2 }}
                whileTap={{ scale: 0.97 }}
                className={cn(
                  "flex items-center gap-3 rounded-md px-2.5 py-2 text-sm font-medium transition-colors",
                  collapsed && "justify-center",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <AnimatePresence initial={false}>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.12 }}
                      className="whitespace-nowrap"
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.div>
            )}
          </NavLink>
        );

        return collapsed ? (
          <Tooltip key={to}>
            <TooltipTrigger asChild>{link}</TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        ) : (
          link
        );
      })}
    </>
  );
}

function SettingsButton({
  collapsed, onClick,
}: { collapsed: boolean; onClick: () => void }) {
  const btn = (
    <button
      onClick={onClick}
      aria-label="Settings"
      className={cn(
        "flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
        collapsed && "justify-center"
      )}
    >
      <Settings className="h-4 w-4 shrink-0" />
      {!collapsed && <span className="whitespace-nowrap">Settings</span>}
    </button>
  );
  return collapsed ? (
    <Tooltip>
      <TooltipTrigger asChild>{btn}</TooltipTrigger>
      <TooltipContent side="right">Settings</TooltipContent>
    </Tooltip>
  ) : (
    btn
  );
}

/** Desktop rail: part of the flex row, collapsible to icons. Hidden on mobile. */
export function Sidebar({
  collapsed, onToggle, onOpenSettings,
}: { collapsed: boolean; onToggle: () => void; onOpenSettings: () => void }) {
  return (
    <motion.aside
      animate={{ width: collapsed ? 60 : 216 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="hidden h-dvh shrink-0 flex-col border-r bg-card md:flex"
    >
      <div className={cn("flex h-14 items-center border-b", collapsed ? "justify-center px-2" : "justify-between px-4")}>
        {!collapsed && (
          <div className="flex items-center gap-2 overflow-hidden">
            <TrendingUp className="h-5 w-5 shrink-0 text-primary" />
            <span className="whitespace-nowrap text-sm font-bold tracking-tight">moneymaker</span>
          </div>
        )}
        <button
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        <NavItems collapsed={collapsed} />
      </nav>

      <div className="border-t p-2">
        <SettingsButton collapsed={collapsed} onClick={onOpenSettings} />
      </div>
    </motion.aside>
  );
}

/** Mobile drawer: slides over the content, closes on navigate. */
export function MobileNav({
  open, onClose, onOpenSettings,
}: { open: boolean; onClose: () => void; onOpenSettings: () => void }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/60 md:hidden"
            aria-hidden
          />
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-card md:hidden"
          >
            <div className="flex h-14 items-center justify-between border-b px-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                <span className="text-sm font-bold tracking-tight">moneymaker</span>
              </div>
              <button
                onClick={onClose}
                aria-label="Close menu"
                className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
              <NavItems collapsed={false} onNavigate={onClose} />
            </nav>

            <div className="border-t p-2">
              <SettingsButton
                collapsed={false}
                onClick={() => { onClose(); onOpenSettings(); }}
              />
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
