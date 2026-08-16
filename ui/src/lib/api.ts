const BASE = "/api";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json();
  if (!res.ok) throw new Error(json.detail || json.error || res.statusText);
  return json as T;
}

const get = <T>(path: string) => req<T>("GET", path);
const post = <T>(path: string, body: unknown) => req<T>("POST", path, body);
const del = <T>(path: string) => req<T>("DELETE", path);

// --- types ---

export interface Strategy {
  name: string;
  doc: string;
  source: "built-in" | "custom";
  params: Record<string, unknown>;
}

export interface Provider {
  name: string;
  doc: string;
  status: "ready" | "stub";
}

export interface Account {
  account_id: string;
  name: string;
  provider: string;
  currency: string;
  starting_balance: number;
  is_live: boolean;
}

export interface Trade {
  timestamp: string;
  side: string;
  price: string;
  qty: string;
  pnl: string;
  balance: string;
  [key: string]: string;
}

/** Flattened by the server from Simulator.status() — see _status_payload(). */
export interface StatusPayload {
  running: boolean;
  trade_count: number;
  total_pnl: number;
  win_rate: number;
  open_pnl: number;
  position_open: boolean;
  direction: string | null;
  last_price: number | null;
  bars_seen: number;
  summary: Record<string, number>;
}

export type LiveStatus = StatusPayload;

export type BacktestResult = StatusPayload & {
  session_name: string;
  account_id: string;
};

export type JobStatus = "running" | "succeeded" | "failed" | "cancelled";

export interface Job<T = unknown> {
  job_id: string;
  kind: string;
  label: string;
  status: JobStatus;
  created_at: string;
  finished_at: string | null;
  progress: string | null;
  error: string | null;
  result?: T;
}

export interface AppConfig {
  version: string;
  home: string;
  data_providers: string[];
  execution_providers: string[];
}

export interface ForkResult {
  label: string;
  score: number;
  params: Record<string, unknown>;
  aggregate: Record<string, number>;
}

export interface ForkSetResult {
  ticker: string;
  forks: ForkResult[];
  [k: string]: unknown;
}

export interface EvolveResult {
  best_params: Record<string, unknown>;
  best_score: number;
  generations: { generation: number; score: number; params: Record<string, unknown> }[];
  [k: string]: unknown;
}

export interface MultiWindowResult {
  total_pnl: number;
  windows_profitable: number;
  window_count: number;
  pnl_std: number;
  windows: { start: string; end: string; total_pnl: number; trades: number }[];
  [k: string]: unknown;
}

export interface OptimizeResult {
  results: {
    params: Record<string, unknown>;
    train_score: number;
    test_score?: number;
    overfit?: boolean;
  }[];
  [k: string]: unknown;
}

// --- strategies ---
export const api = {
  strategies: {
    list: () => get<{ strategies: Strategy[] }>("/strategies"),
  },
  providers: {
    list: () => get<{ providers: Provider[] }>("/providers"),
  },
  config: {
    get: () => get<AppConfig>("/config"),
  },
  accounts: {
    list: () => get<{ accounts: Account[] }>("/accounts"),
    get: (id: string) => get<Account>(`/accounts/${id}`),
    create: (body: { name: string; provider?: string; starting_balance?: number }) =>
      post<Account>("/accounts", body),
    remove: (id: string) => del<{ deleted: string }>(`/accounts/${id}`),
    prune: (prefix = "mw_", dryRun = true) =>
      post<{ matched: number; deleted: number; dry_run: boolean; sample: string[] }>(
        `/accounts/prune?prefix=${encodeURIComponent(prefix)}&dry_run=${dryRun}`, {}),
  },
  credentials: {
    list: () => get<{ credentials: Record<string, Record<string, string>> }>("/credentials"),
    set: (body: { provider: string; key: string; env_var?: string; value?: string }) =>
      post<{ ok: boolean }>("/credentials", body),
    clear: (provider: string) => del<{ cleared: string }>(`/credentials/${provider}`),
  },
  // These return a Job, not a result — poll jobs.get() until it settles.
  research: {
    forkEval: (body: {
      strategy: string; ticker: string; windows: [string, string][];
      interval?: string; account?: number;
    }) => post<Job<ForkSetResult>>("/fork-eval", body),
    evolve: (body: {
      strategy: string; ticker: string; windows: [string, string][];
      interval?: string; generations?: number; perturbation?: number;
    }) => post<Job<EvolveResult>>("/evolve", body),
    rankings: () => get<{ rankings: Record<string, unknown>[] }>("/rankings"),
    optimize: (body: {
      strategy: string; ticker: string; param_grid: Record<string, unknown[]>;
      train_windows: [string, string][]; test_windows?: [string, string][];
      interval?: string;
    }) => post<Job<OptimizeResult>>("/optimize", body),
  },
  jobs: {
    list: () => get<{ jobs: Job[] }>("/jobs"),
    get: <T>(id: string) => get<Job<T>>(`/jobs/${id}`),
    cancel: (id: string) => post<{ cancelling: string }>(`/jobs/${id}/cancel`, {}),
  },
  sessions: {
    list: () => get<{ sessions: string[] }>("/sessions"),
    get: (filename: string) => get<{ trades: Trade[] } | Record<string, unknown>>(`/sessions/${filename}`),
  },
  backtest: {
    run: (body: {
      strategy: string;
      ticker: string;
      start: string;
      end: string;
      interval?: string;
      account?: number;
      risk_pct?: number;
      params?: Record<string, unknown>;
      data_provider?: string;
      data_provider_path?: string;
    }) => post<BacktestResult>("/backtest", body),
    runMulti: (body: {
      strategy: string;
      ticker: string;
      windows: [string, string][];
      interval?: string;
      account?: number;
    }) => post<MultiWindowResult>("/backtest-multi", body),
  },
  live: {
    list: () => get<{ session_ids: string[] }>("/live/list"),
    status: (id: string) => get<LiveStatus>(`/live/${id}/status`),
    start: (body: {
      strategy: string;
      ticker: string;
      end_time?: string;
      poll_seconds?: number;
      account?: number;
    }) => post<{ session_id: string; account_id: string }>("/live/start", body),
    stop: (id: string) => post<{ stopped: string }>(`/live/${id}/stop`, {}),
  },
};
