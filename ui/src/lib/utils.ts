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

export function pnlColor(n: number): string {
  return n >= 0 ? "text-profit" : "text-loss";
}
