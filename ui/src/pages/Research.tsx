import React, { useEffect, useState } from "react";
import { motion } from "motion/react";
import { FlaskConical, Loader2, Trophy, GitFork, Dna, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api, type Strategy, type ForkSetResult, type EvolveResult, type Job } from "@/lib/api";
import { useJob } from "@/lib/useJob";
import { fmt, fmtDollar, pnlColor } from "@/lib/utils";
import { LineChart, Line, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, ReferenceLine } from "recharts";

/** Windows are entered as "start:end,start:end" — same syntax the CLI uses. */
function parseWindows(raw: string): [string, string][] {
  return raw
    .split(",")
    .map((w) => w.trim())
    .filter(Boolean)
    .map((w) => {
      const [a, b] = w.split(":");
      return [a?.trim() ?? "", b?.trim() ?? ""] as [string, string];
    })
    .filter(([a, b]) => a && b);
}

/** Small status chip so a running job is visible without watching the button. */
function JobBadge({ job }: { job: Job }) {
  const variant =
    job.status === "succeeded" ? "profit"
    : job.status === "failed" ? "loss"
    : job.status === "cancelled" ? "outline"
    : "secondary";
  return (
    <Badge variant={variant} className="font-mono text-[10px]">
      {job.progress ?? job.status}
      {job.job_id ? ` · ${job.job_id.slice(0, 6)}` : ""}
    </Badge>
  );
}

function StrategyPicker({
  strategies, value, onValueChange,
}: { strategies: Strategy[]; value: string; onValueChange: (v: string) => void }) {
  // Bind the label to the trigger so it is announced and clickable.
  const id = React.useId();
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-xs">Strategy</Label>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger id={id} className="h-8 text-sm">
          <SelectValue placeholder="Select strategy" />
        </SelectTrigger>
        <SelectContent>
          {strategies.map((s) => <SelectItem key={s.name} value={s.name}>{s.name}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}

// ---------------------------------------------------------------- fork-eval

function ForkEvalPanel({ strategies }: { strategies: Strategy[] }) {
  const { toast } = useToast();
  const [form, setForm] = useState({ strategy: "", ticker: "ES=F", windows: "2026-06-01:2026-08-01", interval: "5m" });
  const { job, start, cancel, running, result } = useJob<ForkSetResult>();

  useEffect(() => {
    if (!form.strategy && strategies[0]) setForm((f) => ({ ...f, strategy: strategies[0].name }));
  }, [strategies]);

  // Report failures once, when the job settles.
  useEffect(() => {
    if (job?.status === "failed") toast(job.error ?? "Fork-eval failed", "error");
  }, [job?.status]);

  async function run() {
    const windows = parseWindows(form.windows);
    if (!windows.length) return toast("Enter at least one window as start:end", "error");
    start(() => api.research.forkEval({ ...form, windows }));
  }

  const loading = running;
  const forks = result?.forks ?? [];
  const best = forks.length ? Math.max(...forks.map((f) => f.score)) : 0;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Fork evaluation</CardTitle>
          <CardDescription>
            Runs every variant in the strategy's <code className="font-mono">FORKS</code> over identical
            windows and ranks them, so differences come from the parameters rather than the data.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:grid-cols-4">
            <StrategyPicker strategies={strategies} value={form.strategy}
                            onValueChange={(v) => setForm((f) => ({ ...f, strategy: v }))} />
            <Field label="Ticker" value={form.ticker} onValueChange={(v) => setForm((f) => ({ ...f, ticker: v }))} />
            <Field label="Interval" value={form.interval} onValueChange={(v) => setForm((f) => ({ ...f, interval: v }))} />
            <Field label="Windows" value={form.windows} mono
                   onValueChange={(v) => setForm((f) => ({ ...f, windows: v }))} placeholder="start:end,start:end" />
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={run} disabled={loading || !form.strategy}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitFork className="h-4 w-4" />}
              {loading ? "Evaluating…" : "Run fork-eval"}
            </Button>
            {running && (
              <Button size="sm" variant="ghost" onClick={cancel}>
                <XCircle className="h-4 w-4" /> Cancel
              </Button>
            )}
            {job && <JobBadge job={job} />}
          </div>
        </CardContent>
      </Card>

      {forks.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Ranked variants</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {forks.map((f, i) => (
                <div key={f.label} className="flex items-center gap-3 rounded-md border p-3">
                  <Badge variant={i === 0 ? "profit" : "outline"} className="w-7 shrink-0 justify-center">
                    {i + 1}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm">{f.label}</span>
                      {i === 0 && <Trophy className="h-3.5 w-3.5 text-profit" />}
                    </div>
                    <div className="truncate font-mono text-[11px] text-muted-foreground">
                      {Object.entries(f.params).map(([k, v]) => `${k}=${v}`).join("  ") || "defaults"}
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className={`text-sm font-bold ${pnlColor(f.score)}`}>{fmt(f.score, 3)}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {f.aggregate?.total_pnl != null ? fmtDollar(f.aggregate.total_pnl) : "score"}
                    </div>
                  </div>
                  {/* score bar */}
                  <div className="hidden h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-muted sm:block">
                    <div className="h-full rounded-full bg-primary"
                         style={{ width: `${best > 0 ? Math.max(0, (f.score / best) * 100) : 0}%` }} />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ evolve

function EvolvePanel({ strategies }: { strategies: Strategy[] }) {
  const { toast } = useToast();
  const [form, setForm] = useState({
    strategy: "", ticker: "ES=F", windows: "2026-06-01:2026-08-01",
    interval: "5m", generations: "20", perturbation: "0.20",
  });
  const { job, start, cancel, running, result } = useJob<EvolveResult>();

  useEffect(() => {
    if (!form.strategy && strategies[0]) setForm((f) => ({ ...f, strategy: strategies[0].name }));
  }, [strategies]);

  useEffect(() => {
    if (job?.status === "failed") toast(job.error ?? "Evolve failed", "error");
  }, [job?.status]);

  async function run() {
    const windows = parseWindows(form.windows);
    if (!windows.length) return toast("Enter at least one window as start:end", "error");
    start(() => api.research.evolve({
      strategy: form.strategy, ticker: form.ticker, windows, interval: form.interval,
      generations: Number(form.generations), perturbation: Number(form.perturbation),
    }));
  }

  const loading = running;
  const gens = result?.generations ?? [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Parameter evolution</CardTitle>
          <CardDescription>
            Hill-climbs the strategy's numeric parameters, keeping a change only when it improves the
            objective score. Few parameters beat many — the sample sizes here are small.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:grid-cols-3">
            <StrategyPicker strategies={strategies} value={form.strategy}
                            onValueChange={(v) => setForm((f) => ({ ...f, strategy: v }))} />
            <Field label="Ticker" value={form.ticker} onValueChange={(v) => setForm((f) => ({ ...f, ticker: v }))} />
            <Field label="Interval" value={form.interval} onValueChange={(v) => setForm((f) => ({ ...f, interval: v }))} />
            <Field label="Generations" value={form.generations}
                   onValueChange={(v) => setForm((f) => ({ ...f, generations: v }))} />
            <Field label="Perturbation" value={form.perturbation}
                   onValueChange={(v) => setForm((f) => ({ ...f, perturbation: v }))} />
            <Field label="Windows" value={form.windows} mono
                   onValueChange={(v) => setForm((f) => ({ ...f, windows: v }))} />
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={run} disabled={loading || !form.strategy}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Dna className="h-4 w-4" />}
              {loading ? "Evolving…" : "Run evolve"}
            </Button>
            {running && (
              <Button size="sm" variant="ghost" onClick={cancel}>
                <XCircle className="h-4 w-4" /> Cancel
              </Button>
            )}
            {job && <JobBadge job={job} />}
          </div>
          {loading && (
            <p className="text-xs text-muted-foreground">
              Running in the background — one full backtest per generation. You can
              navigate away; the job keeps going and appears under Jobs.
            </p>
          )}
        </CardContent>
      </Card>

      {result && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Best parameters</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className={`text-2xl font-bold ${pnlColor(result.best_score)}`}>
                {fmt(result.best_score, 4)}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(result.best_params ?? {}).map(([k, v]) => (
                  <Badge key={k} variant="secondary" className="font-mono text-[11px]">{k}={String(v)}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          {gens.length > 1 && (
            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-sm">Score by generation</CardTitle></CardHeader>
              <CardContent>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={gens} margin={{ left: 4, right: 4, top: 4, bottom: 4 }}>
                      <XAxis dataKey="generation" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <RTooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", fontSize: 12 }} />
                      <ReferenceLine y={0} stroke="hsl(var(--border))" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="score" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}
        </motion.div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- rankings

function RankingsPanel() {
  const [rankings, setRankings] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.research.rankings()
      .then((r) => setRankings(r.rankings))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;

  if (rankings.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <FlaskConical className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No rolling evaluations recorded yet.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Run <code className="font-mono">moneymaker fork-eval --rolling</code> to build score trajectories over time.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {rankings.map((r, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-mono">
              {String(r.strategy ?? "—")} · {String(r.ticker ?? "—")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded bg-muted p-3 text-[11px] leading-relaxed">
              {JSON.stringify(r, null, 2).slice(0, 1200)}
            </pre>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/** Last few background runs, so the page shows history rather than nothing. */
function RecentRuns() {
  const [jobs, setJobs] = useState<Job[]>([]);
  useEffect(() => {
    let alive = true;
    const tick = () => api.jobs.list()
      .then((r) => { if (alive) setJobs(r.jobs.slice(0, 5)); })
      .catch(() => {});
    tick();
    const t = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  if (jobs.length === 0) return null;

  return (
    <Card className="elevated">
      <CardContent className="p-0">
        <div className="border-b px-4 py-2.5">
          <span className="text-[10px] font-medium uppercase tracking-[0.08em] text-muted-foreground">
            Recent runs
          </span>
        </div>
        <div className="divide-y">
          {jobs.map((j) => (
            <div key={j.job_id} className="flex items-center gap-3 px-4 py-2.5">
              {j.status === "running"
                ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
                : <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                    j.status === "succeeded" ? "bg-profit"
                    : j.status === "failed" ? "bg-loss" : "bg-muted-foreground"}`} />}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium">{j.kind}</span>
                  <span className="truncate font-mono text-[11px] text-muted-foreground">{j.label}</span>
                </div>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                {j.created_at.slice(11, 16)}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// -------------------------------------------------------------------- jobs

function JobsPanel() {
  const { toast } = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      api.jobs.list()
        .then((r) => { if (alive) setJobs(r.jobs); })
        .catch(() => {})
        .finally(() => { if (alive) setLoading(false); });
    tick();
    const t = setInterval(tick, 3000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  async function cancel(id: string) {
    try {
      await api.jobs.cancel(id);
      toast("Cancellation requested", "info");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Cancel failed", "error");
    }
  }

  if (loading) return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;

  if (jobs.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <FlaskConical className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No background jobs yet.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Fork-eval, evolve and optimize all run here. Jobs live in memory and clear on restart.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {jobs.map((j) => (
        <motion.div key={j.job_id} layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          <Card>
            <CardContent className="flex items-center gap-3 py-3">
              {j.status === "running"
                ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                : <Badge variant={j.status === "succeeded" ? "profit" : j.status === "failed" ? "loss" : "outline"}
                         className="shrink-0">{j.status}</Badge>}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{j.kind}</span>
                  <span className="truncate font-mono text-xs text-muted-foreground">{j.label}</span>
                </div>
                <div className="font-mono text-[11px] text-muted-foreground">
                  {j.created_at}{j.finished_at ? ` → ${j.finished_at}` : ""} · {j.job_id.slice(0, 8)}
                </div>
                {j.error && <p className="mt-1 break-words text-[11px] text-destructive">{j.error}</p>}
              </div>
              {j.status === "running" && (
                <Button size="sm" variant="ghost" onClick={() => cancel(j.job_id)}>
                  <XCircle className="h-4 w-4" />
                </Button>
              )}
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------- page

export function Research() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);

  useEffect(() => {
    api.strategies.list().then((r) => setStrategies(r.strategies)).catch(() => {});
  }, []);

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="page-header">
        <h1 className="text-[15px] font-semibold tracking-tight">Research</h1>
        <p className="text-sm text-muted-foreground">
          Compare strategy variants, evolve parameters, and review accumulated rankings.
        </p>
      </div>

      <Tabs defaultValue="fork">
        <TabsList className="w-full justify-start overflow-x-auto sm:w-auto">
          <TabsTrigger value="fork">Fork-eval</TabsTrigger>
          <TabsTrigger value="evolve">Evolve</TabsTrigger>
          <TabsTrigger value="rankings">Rankings</TabsTrigger>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
        </TabsList>
        <TabsContent value="fork" className="space-y-4 pt-4">
          <ForkEvalPanel strategies={strategies} />
          <RecentRuns />
        </TabsContent>
        <TabsContent value="evolve" className="space-y-4 pt-4">
          <EvolvePanel strategies={strategies} />
          <RecentRuns />
        </TabsContent>
        <TabsContent value="rankings" className="pt-4"><RankingsPanel /></TabsContent>
        <TabsContent value="jobs" className="pt-4"><JobsPanel /></TabsContent>
      </Tabs>
    </div>
  );
}
