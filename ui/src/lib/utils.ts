import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(n: number | undefined | null, decimals = 2): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function fmtPct(n: number | undefined | null): string {
  if (n == null) return "—";
  return (n * 100).toFixed(1) + "%";
}

export function fmtDollar(n: number | undefined | null): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "" : "-";
  return sign + "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * Colour for a P&L figure.
 *
 * Exactly zero is neutral: a session that took no trades, or closed flat,
 * is not a win and should not be coloured like one.
 */
export function pnlColor(n: number | null | undefined): string {
  if (n == null || n === 0) return "text-muted-foreground";
  return n > 0 ? "text-profit" : "text-loss";
}
