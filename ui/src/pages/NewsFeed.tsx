import { useState } from "react";
import { motion } from "motion/react";
import { ExternalLink, Newspaper } from "lucide-react";
import { Panel } from "@/components/terminal/Panel";
import { SkeletonRows, ErrorState, EmptyState } from "@/components/terminal/States";
import { Badge } from "@/components/ui/badge";
import { useResource } from "@/lib/useResource";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const TOPICS = ["markets", "gold", "oil", "fed", "inflation", "earnings", "crypto"];

function ago(iso: string): string {
  if (!iso) return "";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.round(hrs / 24)}d`;
}

/**
 * Market news.
 *
 * The economic calendar says when a release lands; this is the narrative
 * around it. Headlines are read-only — nothing here feeds a strategy, which
 * is deliberate: sentiment is not something the engine acts on.
 */
export function NewsFeed() {
  const [topic, setTopic] = useState("markets");
  const news = useResource(() => api.orders.news(topic, 30), [topic],
                           { pollMs: 300000 });

  const items = news.data?.items ?? [];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1">
          {TOPICS.map((t) => (
            <button key={t} onClick={() => setTopic(t)}
                    className={cn("rounded-md px-2 py-1 text-[11px] font-medium transition-colors",
                      topic === t ? "bg-primary text-primary-foreground"
                                  : "text-muted-foreground hover:bg-accent hover:text-foreground")}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <Panel dense title={`${topic} · ${items.length} headlines`}>
        {news.error ? <ErrorState message={news.error} onRetry={news.reload} />
          : !news.settled ? <SkeletonRows rows={6} cols={3} />
          : items.length === 0
            ? <EmptyState title="Nothing found" hint={`No headlines for "${topic}".`} />
            : (
              <div className="divide-y">
                {items.map((n, i) => (
                  <motion.a
                    key={`${n.link}-${i}`}
                    href={n.link} target="_blank" rel="noopener noreferrer"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(i, 10) * 0.02 }}
                    className="group flex items-start gap-3 px-3 py-2.5 transition-colors hover:bg-accent/40"
                  >
                    <span className="w-9 shrink-0 pt-0.5 text-right font-mono text-[10px] text-muted-foreground">
                      {ago(n.published)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm leading-snug">{n.title}</span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-1.5">
                        <span className="text-[10px] text-muted-foreground">{n.publisher}</span>
                        {n.tickers.slice(0, 4).map((t) => (
                          <Badge key={t} variant="outline" className="px-1 py-0 font-mono text-[9px]">
                            {t}
                          </Badge>
                        ))}
                      </span>
                    </span>
                    <ExternalLink className="mt-1 h-3 w-3 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </motion.a>
                ))}
              </div>
            )}
      </Panel>
    </div>
  );
}
