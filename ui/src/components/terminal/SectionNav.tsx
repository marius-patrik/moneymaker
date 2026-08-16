import { NavLink } from "react-router-dom";
import { LayoutDashboard, CandlestickChart, Wallet, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { AnimatedIcon, type IconMotion } from "@/components/ui/animated-icon";

/**
 * Top-level sections.
 *
 * Three, not five: backtesting, optimising and trading a strategy are the
 * same job at different moments, so they live together in the workspace
 * rather than as separate destinations you navigate between mid-thought.
 */
export const SECTIONS: {
  to: string; icon: React.ElementType; label: string; motion: IconMotion;
}[] = [
  { to: "/",          icon: LayoutDashboard,  label: "Overview",  motion: "lift" },
  { to: "/workspace", icon: CandlestickChart, label: "Workspace", motion: "draw" },
  { to: "/portfolio", icon: Wallet,           label: "Portfolio", motion: "lift" },
];

/** Segmented switcher in the context bar (desktop). */
export function SectionNav() {
  return (
    <nav className="hidden items-center gap-0.5 rounded-lg bg-muted/60 p-0.5 md:flex">
      {SECTIONS.map(({ to, icon, label, motion }) => (
        <NavLink key={to} to={to} end={to === "/"}>
          {({ isActive }) => (
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-medium transition-colors",
                isActive
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <AnimatedIcon icon={icon} motionType={motion} className="h-3.5 w-3.5" />
              {label}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

/** Bottom tab bar (mobile) — thumb-reachable, replaces the drawer. */
export function BottomNav({ onOpenSettings }: { onOpenSettings: () => void }) {
  return (
    <nav className="glass z-40 flex h-14 shrink-0 items-stretch border-t md:hidden">
      {SECTIONS.map(({ to, icon, label, motion }) => (
        <NavLink key={to} to={to} end={to === "/"} className="flex-1">
          {({ isActive }) => (
            <span
              className={cn(
                "flex h-full flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors",
                isActive ? "text-foreground" : "text-muted-foreground"
              )}
            >
              <AnimatedIcon icon={icon} motionType={motion} className="h-[18px] w-[18px]" />
              {label}
              <span className={cn(
                "h-0.5 w-6 rounded-full transition-colors",
                isActive ? "bg-primary" : "bg-transparent"
              )} />
            </span>
          )}
        </NavLink>
      ))}
      <button onClick={onOpenSettings}
              aria-label="Settings"
              className="flex flex-1 flex-col items-center justify-center gap-1 text-[10px] font-medium text-muted-foreground">
        <AnimatedIcon icon={Settings} motionType="wiggle" className="h-[18px] w-[18px]" />
        Settings
        <span className="h-0.5 w-6" />
      </button>
    </nav>
  );
}
