import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { GitFork, Dna, Trophy, XCircle, Loader2 } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";
import { Panel, Stat, DataTable } from "@/components/terminal/Panel";
import { EmptyState } from "@/components/terminal/States";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { useJob } from "@/lib/useJob";
import { useResource } from "@/lib/useResource";
import { api, type Strategy, type ForkSetResult, type EvolveResult, type Job } from "@/lib/api";
import { fmt, fmtDollar, pnlColor } from "@/lib/utils";

function parseWindows(raw: string): [string, string][] {
  return raw.split(",").map((w) => w.trim()).filter(Boolean)
    .map((w) => w.split(":").map((x) => x.trim()) as [string, string])
    .filter(([a, b]) => a && b);
}

function JobChip({ job }: { job: Job }) {
  const variant = job.status === "succeeded" ? "profit"
    : job.status === "failed" ? "loss"
    : job.status === "cancelled" ? "outline" : "secondary";
  return (
    <Badge variant={variant} className="font-mono text-[10px]">
      {job.progress ?? job.status}
    </Badge>
  );
}

/**
 * Optimisation over the selected system: compare its declared variants, or
 * hill-climb its numeric parameters. Both are long-running, so both go
 * through the job queue.
 */
export function LabPanel({ strategy, ticker }: { strategy: Strategy; ticker: string }) {
  const { toast } = useToast();
  const [windows, setWindows] = useState("2025-01-01:2026-01-01");
  const [interval, setInterval] = useState("1d");
  const [generations, setGenerations] = useState("20");

  const fork = useJob<ForkSetResult>();
  const evolve = useJob<EvolveResult>();
  const jobs = useResource(() => api.jobs.list(), [], { pollMs: 4000 });

  useEffect(() => {
    if (fork.job?.status === "failed") toast(fork.job.error ?? "Fork-eval failed", "error");
  }, [fork.job?.status]);
  useEffect(() => {
    if (evolve.job?.status === "failed") toast(evolve.job.error ?? "Evolve failed", "error");
  }, [evolve.job?.status]);

  const w = parseWindows(windows);
  const forks = fork.result?.forks ?? [];
  const gens = evolve.result?.generations ?? [];
  const best = forks.length ? Math.max(...forks.map((f) => f.score)) : 0;

  return (
    <div className="space-y-3">
      <Panel title="Optimisation">
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Windows" value={windows} mono onValueChange={setWindows}
                   hint="start:end, comma separated" />
            <Field label="Interval" value={interval} onValueChange={setInterval} />
            <Field label="Generations" type="number" value={generations}
                   onValueChange={setGenerations} hint="evolve only" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={fork.running || !w.length}
                    onClick={() => fork.start(() => api.research.forkEval({
                      strategy: strategy.name, ticker, windows: w, interval }))}>
              {fork.running ? <Loader2 className="h-4 w-4 animate-spin" />
                : <AnimatedIcon icon={GitFork} motionType="pop" className="h-4 w-4" />}
              Compare variants
            </Button>
            <Button size="sm" variant="outline" disabled={evolve.running || !w.length}
                    onClick={() => evolve.start(() => api.research.evolve({
                      strategy: strategy.name, ticker, windows: w, interval,
                      generations: Number(generations) }))}>
              {evolve.running ? <Loader2 className="h-4 w-4 animate-spin" />
                : <AnimatedIcon icon={Dna} motionType="wiggle" className="h-4 w-4" />}
              Evolve parameters
            </Button>
            {(fork.running || evolve.running) && (
              <Button size="sm" variant="ghost"
                      onClick={() => { fork.cancel(); evolve.cancel(); }}>
                <XCircle className="h-4 w-4" /> Cancel
              </Button>
            )}
            {fork.job && <JobChip job={fork.job} />}
            {evolve.job && <JobChip job={evolve.job} />}
          </div>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            Variants come from the system's <code className="font-mono">FORKS</code> and run over
            identical windows, so differences are the parameters rather than the data. Evolution
            hill-climbs numeric parameters — few beat many, since the sample sizes here are small.
          </p>
        </div>
      </Panel>

      {forks.length > 0 && (
        <Panel title="Ranked variants" dense>
          <DataTable head={<><th className="w-8">#</th><th>Variant</th><th>Parameters</th>
                            <th className="!text-right">Score</th><th className="!text-right">P&L</th></>}>
            {forks.map((f, i) => (
              <tr key={f.label}>
                <td>
                  <Badge variant={i === 0 ? "profit" : "outline"} className="w-6 justify-center text-[10px]">
                    {i + 1}
                  </Badge>
                </td>
                <td className="font-mono">
                  <span className="flex items-center gap-1.5">
                    {f.label}
                    {i === 0 && <Trophy className="h-3 w-3 text-profit" />}
                  </span>
                </td>
                <td className="max-w-0 truncate font-mono text-[10px] text-muted-foreground">
                  {Object.entries(f.params).map(([k, v]) => `${k}=${v}`).join(" ") || "defaults"}
                </td>
                <td className={`text-right font-mono tabular-nums ${pnlColor(f.score)}`}>
                  {fmt(f.score, 3)}
                </td>
                <td className="text-right font-mono tabular-nums text-muted-foreground">
                  {f.aggregate?.total_pnl != null ? fmtDollar(f.aggregate.total_pnl) : "—"}
                </td>
              </tr>
            ))}
          </DataTable>
        </Panel>
      )}

      {evolve.result && (
        <Panel title="Evolved parameters">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-4">
              <Stat label="Best score" value={fmt(evolve.result.best_score, 4)}
                    tone={evolve.result.best_score > 0 ? "profit" : "loss"} />
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(evolve.result.best_params ?? {}).map(([k, v]) => (
                  <Badge key={k} variant="secondary" className="font-mono text-[10px]">
                    {k}={String(v)}
                  </Badge>
                ))}
              </div>
            </div>
            {gens.length > 1 && (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={gens} margin={{ left: 0, right: 4, top: 4, bottom: 0 }}>
                    <XAxis dataKey="generation" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                           axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                           axisLine={false} tickLine={false} width={44} />
                    <ReferenceLine y={0} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                    <Tooltip contentStyle={{ background: "hsl(var(--popover))",
                                             border: "1px solid hsl(var(--border))",
                                             borderRadius: 10, fontSize: 11 }} />
                    <Line type="monotone" dataKey="score" stroke="hsl(var(--primary))"
                          strokeWidth={1.6} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </Panel>
      )}

      <Panel title="Job queue" dense>
        {(jobs.data?.jobs ?? []).length === 0 ? (
          <EmptyState title="No runs yet"
                      hint="Comparisons and evolutions run in the background and appear here." />
        ) : (
          <DataTable head={<><th>Kind</th><th>Target</th><th>Status</th><th className="!text-right">Started</th></>}>
            {(jobs.data?.jobs ?? []).slice(0, 8).map((j) => (
              <tr key={j.job_id}>
                <td className="font-medium">{j.kind}</td>
                <td className="max-w-0 truncate font-mono text-muted-foreground">{j.label}</td>
                <td>
                  {j.status === "running"
                    ? <span className="flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin text-primary" />running</span>
                    : <Badge variant={j.status === "succeeded" ? "profit" : j.status === "failed" ? "loss" : "outline"}
                             className="text-[10px]">{j.status}</Badge>}
                </td>
                <td className="text-right font-mono text-muted-foreground">{j.created_at.slice(11, 16)}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </Panel>
    </div>
  );
}
