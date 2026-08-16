import { useCallback, useEffect, useRef, useState } from "react";

export type ResourceState<T> = {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  /** True once a fetch has settled — lets a view tell "empty" from "not yet". */
  settled: boolean;
  reload: () => void;
};

/**
 * Fetch a resource while keeping loading, error and empty distinct.
 *
 * Every page used `.catch(() => {})`, which renders a failed request as an
 * empty list — so a server restart mid-load looked like "you have no
 * accounts". An error must say so, and must be retryable.
 */
export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: { pollMs?: number } = {}
): ResourceState<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [settled, setSettled] = useState(false);
  const [nonce, setNonce] = useState(0);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  const run = useCallback(() => {
    setLoading(true);
    fetcher()
      .then((v) => {
        if (!alive.current) return;
        setData(v); setError(null);
      })
      .catch((e: unknown) => {
        if (!alive.current) return;
        setError(e instanceof Error ? e.message : "Request failed");
      })
      .finally(() => {
        if (!alive.current) return;
        setLoading(false); setSettled(true);
      });
    // fetcher identity changes every render; deps are the real trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
    if (!options.pollMs) return;
    const t = setInterval(run, options.pollMs);
    return () => clearInterval(t);
  }, [run, nonce, options.pollMs]);

  return { data, error, loading, settled, reload: () => setNonce((n) => n + 1) };
}
