import { useState } from "react";
import { NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import { Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { SECTIONS, SETTINGS_ROUTE } from "@/components/terminal/SectionNav";

/**
 * Navigation rail.
 *
 * Sits collapsed to icons and widens on hover, so the labels are there when
 * wanted without permanently spending horizontal space the charts and tables
 * would rather have. Icons stay visible in both states — the rail never goes
 * blank.
 */
export function Sidebar() {
  const [hovered, setHovered] = useState(false);

  return (
    <motion.aside
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      animate={{ width: hovered ? 176 : 56 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className="relative z-30 hidden h-full shrink-0 flex-col border-r bg-card/40 md:flex"
    >
      <nav className="flex flex-1 flex-col gap-0.5 p-2">
        {SECTIONS.map(({ to, icon, label, motion: m }) => (
          <NavLink key={to} to={to} end={to === "/"} title={label}>
            {({ isActive }) => (
              <span
                className={cn(
                  "flex h-9 items-center gap-3 overflow-hidden rounded-lg px-2.5 text-[13px] font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <AnimatedIcon icon={icon} motionType={m} className="h-4 w-4" />
                <AnimatePresence initial={false}>
                  {hovered && (
                    <motion.span
                      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                      transition={{ duration: 0.1 }}
                      className="whitespace-nowrap"
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-2">
        <NavLink to={SETTINGS_ROUTE} title="Settings">
          {({ isActive }) => (
            <span className={cn(
              "flex h-9 items-center gap-3 overflow-hidden rounded-lg px-2.5 text-[13px] font-medium transition-colors",
              isActive ? "bg-primary text-primary-foreground"
                       : "text-muted-foreground hover:bg-accent hover:text-accent-foreground")}>
              <AnimatedIcon icon={Settings} motionType="wiggle" className="h-4 w-4" />
              <AnimatePresence initial={false}>
                {hovered && (
                  <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                               transition={{ duration: 0.1 }} className="whitespace-nowrap">
                    Settings
                  </motion.span>
                )}
              </AnimatePresence>
            </span>
          )}
        </NavLink>
      </div>
    </motion.aside>
  );
}
