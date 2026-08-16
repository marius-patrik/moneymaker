import { AlertTriangle, RefreshCw, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AnimatedIcon } from "@/components/ui/animated-icon";

/** Skeleton rows — a shape that settles into content, not a spinner. */
export function SkeletonRows({ rows = 4, cols = 3 }: { rows?: number; cols?: number }) {
  return (
    <div className="divide-y">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-3 py-2.5">
          {Array.from({ length: cols }).map((_, c) => (
            <div key={c}
                 className="h-3 animate-pulse rounded bg-muted"
                 style={{ width: c === 0 ? "40%" : `${18 - c * 3}%`,
                          animationDelay: `${(r * cols + c) * 40}ms` }} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** A failed request says so, and offers a way out. */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
      <AlertTriangle className="h-5 w-5 text-loss" />
      <p className="text-xs font-medium">Could not load</p>
      <p className="max-w-sm break-words text-[11px] text-muted-foreground">{message}</p>
      {onRetry && (
        <Button size="sm" variant="outline" className="mt-1" onClick={onRetry}>
          <AnimatedIcon icon={RefreshCw} motionType="spin" className="h-3.5 w-3.5" />
          Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint, action }: {
  title: string; hint?: string; action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-1.5 px-4 py-10 text-center">
      <p className="text-xs font-medium">{title}</p>
      {hint && <p className="max-w-sm text-[11px] text-muted-foreground">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function Spinner() {
  return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
}
