import { NavLink } from "react-router-dom";
import { CandlestickChart, Wallet, Newspaper, Settings, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { AnimatedIcon, type IconMotion } from "@/components/ui/animated-icon";

export const SECTIONS: {
  to: string; icon: React.ElementType; label: string; motion: IconMotion;
}[] = [
  { to: "/trade",     icon: CandlestickChart, label: "Trade",     motion: "draw" },
  { to: "/portfolio", icon: Wallet,           label: "Portfolio", motion: "lift" },
  { to: "/news",      icon: Newspaper,        label: "News",      motion: "lift" },
  { to: "/settings",  icon: Settings,         label: "Settings",  motion: "wiggle" },
];

export const SETTINGS_ROUTE = "/settings";

function Item({
  to, icon, label, motion,
}: { to: string; icon: React.ElementType; label: string; motion: IconMotion }) {
  return (
    <NavLink to={to} className="flex-1">
      {({ isActive }) => (
        <span className={cn(
          "flex h-full flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors",
          isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
        )}>
          <AnimatedIcon icon={icon} motionType={motion} className="h-[18px] w-[18px]" />
          {label}
          <span className={cn("h-0.5 w-6 rounded-full transition-colors",
            isActive ? "bg-primary" : "bg-transparent")} />
        </span>
      )}
    </NavLink>
  );
}

/**
 * The dock.
 *
 * One navigation component at every width rather than a rail on desktop and
 * a tab bar on mobile — two layouts meant two sets of behaviour to keep in
 * step, and the difference bought nothing. Search sits in the middle because
 * it is the most-used control and the centre is the easiest place to hit,
 * with a thumb or a cursor.
 */
export function Dock({ onOpenSearch }: { onOpenSearch: () => void }) {
  const half = Math.ceil(SECTIONS.length / 2);
  return (
    <nav className="glass z-40 flex h-16 shrink-0 items-stretch border-t px-2 sm:h-14">
      <div className="mx-auto flex w-full max-w-2xl items-stretch">
        {SECTIONS.slice(0, half).map((s) => <Item key={s.to} {...s} />)}

        <button
          onClick={onOpenSearch}
          aria-label="Search"
          className="group flex w-16 shrink-0 flex-col items-center justify-center gap-1"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform group-hover:scale-105 group-active:scale-95">
            <AnimatedIcon icon={Search} motionType="pop" className="h-4 w-4" />
          </span>
          <span className="text-[10px] font-medium text-muted-foreground">Search</span>
        </button>

        {SECTIONS.slice(half).map((s) => <Item key={s.to} {...s} />)}
      </div>
    </nav>
  );
}
