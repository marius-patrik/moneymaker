import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * A terminal panel.
 *
 * Replaces the floating rounded card: panels butt against each other with
 * hairline seams and carry a dense title strip, which is how a trading
 * terminal packs information without it reading as clutter.
 */
export function Panel({
  title, actions, children, className, bodyClassName, dense = false,
}: {
  title?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  dense?: boolean;
}) {
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col overflow-hidden rounded-lg border bg-card",
        "shadow-[0_1px_2px_-1px_hsl(0_0%_0%/0.08)]",
        "dark:shadow-[0_1px_0_0_hsl(0_0%_100%/0.03)_inset,0_2px_8px_-4px_hsl(0_0%_0%/0.5)]",
        className
      )}
    >
      {(title || actions) && (
        <header className="flex h-9 shrink-0 items-center justify-between gap-2 border-b bg-muted/30 px-3">
          <span className="truncate text-[10px] font-semibold uppercase tracking-[0.09em] text-muted-foreground">
            {title}
          </span>
          {actions && <div className="flex shrink-0 items-center gap-1">{actions}</div>}
        </header>
      )}
      <div className={cn(dense ? "" : "p-3", "min-w-0 flex-1", bodyClassName)}>
        {children}
      </div>
    </section>
  );
}

/** A label/value pair, the unit a terminal is built from. */
export function Stat({
  label, value, sub, tone, className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: "profit" | "loss" | "neutral";
  className?: string;
}) {
  const toneClass =
    tone === "profit" ? "text-profit" : tone === "loss" ? "text-loss" : "";
  return (
    <div className={cn("min-w-0", className)}>
      <div className="truncate text-[10px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
        {label}
      </div>
      <div className={cn("truncate font-mono text-[15px] font-semibold tabular-nums", toneClass)}>
        {value}
      </div>
      {sub && <div className="truncate text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

/** Dense data table shell — terminals list, they do not stack cards. */
export function DataTable({
  head, children, className,
}: { head: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0 overflow-x-auto", className)}>
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 z-10">
          <tr className="border-b bg-muted/40 [&>th]:whitespace-nowrap [&>th]:px-3 [&>th]:py-2 [&>th]:text-left [&>th]:text-[10px] [&>th]:font-semibold [&>th]:uppercase [&>th]:tracking-[0.08em] [&>th]:text-muted-foreground">
            {head}
          </tr>
        </thead>
        <tbody className="[&>tr]:border-b [&>tr]:border-border/60 [&>tr:last-child]:border-0 [&>tr:hover]:bg-accent/30 [&>tr>td]:px-3 [&>tr>td]:py-1.5">
          {children}
        </tbody>
      </table>
    </div>
  );
}
