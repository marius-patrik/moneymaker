import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Job } from "@/lib/api";

const TERMINAL = ["succeeded", "failed", "cancelled"];

/**
 * Track a background job to completion.
 *
 * `start` takes the submit call (which returns a Job) and polls until the
 * job settles, exposing the live job the whole time so callers can show
 * progress and offer a cancel button.
 */
export function useJob<T>() {
  const [job, setJob] = useState<Job<T> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      clearTimeout(timer.current);
    };
  }, []);

  const poll = useCallback((id: string) => {
    const tick = async () => {
      try {
        const next = await api.jobs.get<T>(id);
        if (!alive.current) return;
        setJob(next);
        if (!TERMINAL.includes(next.status)) {
          timer.current = setTimeout(tick, 1500);
        }
      } catch {
        // Server restarts drop in-memory jobs; stop rather than loop.
        if (alive.current) {
          setJob((j) => (j ? { ...j, status: "failed", error: "lost contact with job" } : j));
        }
      }
    };
    tick();
  }, []);

  const start = useCallback(
    async (submit: () => Promise<Job<T>>) => {
      clearTimeout(timer.current);
      try {
        const started = await submit();
        if (!alive.current) return;
        setJob(started);
        poll(started.job_id);
      } catch (e) {
        setJob({
          job_id: "", kind: "", label: "", status: "failed",
          created_at: "", finished_at: null, progress: null,
          error: e instanceof Error ? e.message : "Failed to start",
        } as Job<T>);
      }
    },
    [poll]
  );

  const cancel = useCallback(async () => {
    if (job && !TERMINAL.includes(job.status)) {
      try {
        await api.jobs.cancel(job.job_id);
      } catch {
        /* the poll below reports the real state */
      }
    }
  }, [job]);

  const reset = useCallback(() => {
    clearTimeout(timer.current);
    setJob(null);
  }, []);

  return {
    job,
    start,
    cancel,
    reset,
    running: !!job && !TERMINAL.includes(job.status),
    result: job?.status === "succeeded" ? (job.result as T | undefined) : undefined,
  };
}
