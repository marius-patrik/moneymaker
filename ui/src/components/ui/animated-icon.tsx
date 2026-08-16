import * as React from "react";
import { motion, type Variants } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * Motion wrappers for Lucide icons.
 *
 * Lucide ships static SVGs, so the animation lives in a wrapper rather than
 * the icon. Each variant is a short, purposeful gesture — a nudge in the
 * direction the control acts — not decoration. Everything is driven by the
 * parent's hover/active state via `whileHover`/`whileTap` on an ancestor
 * with `initial="rest"`, so an icon inside a button animates when the button
 * is hovered rather than only the icon itself.
 *
 * Respects prefers-reduced-motion: the transforms collapse to no-ops.
 */

export type IconMotion =
  | "lift"      // nudge up — navigation, links
  | "nudge"     // slide right — "go", submit, next
  | "spin"      // rotate — refresh, reload
  | "pulse"     // scale in/out — live, active, running
  | "wiggle"    // small rotate shake — settings, tuning
  | "pop"       // quick scale — create, add
  | "shake"     // horizontal shake — destructive
  | "draw";     // scale from centre — charts, data

const VARIANTS: Record<IconMotion, Variants> = {
  lift:  { rest: { y: 0 },              hover: { y: -2 } },
  nudge: { rest: { x: 0 },              hover: { x: 2 } },
  spin:  { rest: { rotate: 0 },         hover: { rotate: 180 } },
  pulse: { rest: { scale: 1 },          hover: { scale: 1.12 } },
  wiggle:{ rest: { rotate: 0 },         hover: { rotate: [0, -12, 12, 0] } },
  pop:   { rest: { scale: 1 },          hover: { scale: 1.18 } },
  shake: { rest: { x: 0 },              hover: { x: [0, -2, 2, -1, 0] } },
  draw:  { rest: { scale: 1, opacity: 1 }, hover: { scale: 1.1 } },
};

const TRANSITION = { type: "spring", stiffness: 400, damping: 18 } as const;

export interface AnimatedIconProps extends React.ComponentProps<typeof motion.span> {
  icon: React.ElementType;
  motionType?: IconMotion;
  className?: string;
  /** Animate continuously rather than on hover — for genuinely live state. */
  active?: boolean;
}

export function AnimatedIcon({
  icon: Icon, motionType = "pulse", className, active = false, ...rest
}: AnimatedIconProps) {
  const variants = VARIANTS[motionType];
  return (
    <motion.span
      variants={variants}
      animate={active ? { scale: [1, 1.15, 1] } : undefined}
      transition={active
        ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" }
        : TRANSITION}
      className={cn("inline-flex shrink-0", className)}
      {...rest}
    >
      <Icon className="h-full w-full" />
    </motion.span>
  );
}

/**
 * Wrap any control so the icons inside it animate on hover/tap.
 * Put this on the button/link, not the icon.
 */
export const MotionHost = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<typeof motion.div>
>(({ children, ...props }, ref) => (
  <motion.div ref={ref} initial="rest" whileHover="hover" whileTap="hover" animate="rest" {...props}>
    {children}
  </motion.div>
));
MotionHost.displayName = "MotionHost";
