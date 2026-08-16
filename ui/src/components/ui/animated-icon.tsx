import * as React from "react";
import { motion, useAnimationControls, type Variants } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * Motion wrappers for Lucide icons.
 *
 * Lucide ships static SVGs, so the movement lives in a wrapper. Each variant
 * is a short gesture in the direction the control acts — a nudge toward what
 * will happen — rather than decoration.
 *
 * Hover state is tracked on the wrapper itself rather than inherited from a
 * parent variant: relying on propagation meant an `animate` prop on the host
 * could pin the child to its rest state, which is exactly what stopped these
 * from moving.
 */

export type IconMotion =
  | "lift"    // up — navigation
  | "nudge"   // right — go, submit, next
  | "spin"    // rotate — refresh
  | "pulse"   // scale — live, active
  | "wiggle"  // shake — settings, tuning
  | "pop"     // quick scale — create, add
  | "shake"   // horizontal — destructive
  | "draw";   // scale from centre — charts

const HOVER: Record<IconMotion, Record<string, unknown>> = {
  lift:   { y: -2.5 },
  nudge:  { x: 2.5 },
  spin:   { rotate: 180 },
  pulse:  { scale: 1.18 },
  wiggle: { rotate: [0, -14, 12, -6, 0] },
  pop:    { scale: [1, 1.28, 1.1] },
  shake:  { x: [0, -2.5, 2.5, -1.5, 0] },
  draw:   { scale: 1.15, y: -1 },
};

const REST: Record<IconMotion, Record<string, unknown>> = {
  lift:   { y: 0 },
  nudge:  { x: 0 },
  spin:   { rotate: 0 },
  pulse:  { scale: 1 },
  wiggle: { rotate: 0 },
  pop:    { scale: 1 },
  shake:  { x: 0 },
  draw:   { scale: 1, y: 0 },
};

const SPRING = { type: "spring", stiffness: 420, damping: 17 } as const;

export interface AnimatedIconProps {
  icon: React.ElementType;
  motionType?: IconMotion;
  className?: string;
  /** Loop continuously — reserve for genuinely live state. */
  active?: boolean;
}

export function AnimatedIcon({
  icon: Icon, motionType = "pulse", className, active = false,
}: AnimatedIconProps) {
  const controls = useAnimationControls();
  const hostRef = React.useRef<HTMLSpanElement | null>(null);

  // Drive from the nearest interactive ancestor so the icon reacts when the
  // whole button is hovered, not only the glyph.
  React.useEffect(() => {
    if (active) return;
    const el = hostRef.current;
    if (!el) return;
    const target =
      el.closest("button, a, [role=button], [data-motion-host]") ?? el;

    const enter = () => controls.start({ ...HOVER[motionType], transition: SPRING });
    const leave = () => controls.start({ ...REST[motionType], transition: SPRING });

    target.addEventListener("pointerenter", enter);
    target.addEventListener("pointerleave", leave);
    target.addEventListener("focus", enter);
    target.addEventListener("blur", leave);
    return () => {
      target.removeEventListener("pointerenter", enter);
      target.removeEventListener("pointerleave", leave);
      target.removeEventListener("focus", enter);
      target.removeEventListener("blur", leave);
    };
  }, [controls, motionType, active]);

  return (
    <motion.span
      ref={hostRef}
      animate={active ? { scale: [1, 1.16, 1], opacity: [1, 0.75, 1] } : controls}
      transition={active
        ? { duration: 1.9, repeat: Infinity, ease: "easeInOut" }
        : SPRING}
      className={cn("inline-flex shrink-0 items-center justify-center", className)}
    >
      <Icon className="h-full w-full" />
    </motion.span>
  );
}

/**
 * Optional wrapper for non-interactive hosts (a card that should animate its
 * icons on hover). Buttons and links are detected automatically.
 */
export const MotionHost = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<typeof motion.div>
>(({ children, ...props }, ref) => (
  <motion.div ref={ref} data-motion-host {...props}>
    {children}
  </motion.div>
));
MotionHost.displayName = "MotionHost";
