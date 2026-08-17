const BASE = "/api";

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch only rejects on a transport failure — the server is down or
    // unreachable. Say that, rather than surfacing "Failed to fetch".
    throw new Error("Cannot reach the server. Is it still running?");
  }

  // Not every error response is JSON: an unhandled exception yields the
  // plain string "Internal Server Error", and res.json() would throw on it,
  // replacing a useful message with a parse error.
  const raw = await res.text();
  let parsed: unknown;
  try {
    parsed = raw ? JSON.parse(raw) : null;
  } catch {
    parsed = null;
  }

  if (!res.ok) {
    const detail =
      (parsed as { detail?: string; error?: string } | null)?.detail ??
      (parsed as { error?: string } | null)?.error ??
      (raw && raw.length < 300 ? raw : "") ??
      "";
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return parsed as T;
}

const get = <T>(path: string) => req<T>("GET", path);
const post = <T>(path: string, body: unknown) => req<T>("POST", path, body);
const del = <T>(path: string) => req<T>("DELETE", path);

// --- types ---

export interface Strategy {
  name: string;
  doc: string;
  editable?: boolean;
  params: Record<string, unknown>;
}

export interface StrategyStats {
  runs: number;
  trades: number;
  total_pnl: number;
  win_rate: number | null;
  profit_factor: number | null;
  best: number | null;
  worst: number | null;
  last_run: string;
}

export interface Provider {
  name: string;
  doc: string;
  status: "ready" | "stub";
  is_live?: boolean;
}

export interface ProviderGroups {
  data: Provider[];
  news: Provider[];
  execution: Provider[];
}

export interface SessionEntry {
  name: string;
  kind: "trades" | "result";
  modified: string;
  size: number;
  trades?: number | null;
  total_pnl?: number;
  win_rate?: number | null;
  ticker?: string | null;
  first_trade?: string | null;
  last_trade?: string | null;
}

export interface Instrument {
  symbol: string;
  name: string;
  type: string;
  exchange: string;
  /** Set when the symbol is a substitute — e.g. futures for spot metals. */
  note?: string;
}

export interface Alert {
  id: string;
  ticker: string;
  level: number;
  condition: string;
  note: string;
  repeat: boolean;
  status: "armed" | "fired";
  created_at: string;
  fired_at: string | null;
  fired_price: number | null;
}

export interface PendingOrder {
  id: string;
  account_id: string;
  ticker: string;
  direction: string;
  size: number;
  type: string;
  trigger_price: number;
  limit_price: number | null;
  position_id: string | null;
  status: string;
  placed_at: string;
}

export interface OrderMonitor {
  running: boolean;
  interval_seconds: number;
  last_sweep: string | null;
  error: string | null;
  working_orders: number;
}

export interface NewsItem {
  title: string;
  publisher: string;
  link: string;
  published: string;
  tickers: string[];
  thumbnail: string;
}

export interface QuickItem {
  id: string; label: string; sub: string; route: string;
}

export interface QuickGroup { group: string; items: QuickItem[] }

export interface IndicatorMeta {
  kind: string;
  label: string;
  pane: "price" | "lower";
  params: Record<string, number>;
}

export interface IndicatorSeries {
  kind: string;
  label: string;
  pane: "price" | "lower";
  period: number;
  points: { time: number; value: number }[];
}

export interface Candle {
  /** UNIX seconds — what lightweight-charts indexes on. */
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceHistory {
  ticker: string;
  interval: string;
  candles: Candle[];
  last: number | null;
  change: number;
  change_pct: number;
  high: number | null;
  low: number | null;
}

export interface EquityPoint {
  i: number;
  t: string;
  equity: number;
}

export interface PnlBucket {
  lo: number; hi: number; mid: number; count: number; pnl: number;
}

export interface PnlDistribution {
  buckets: PnlBucket[];
  trades: number;
  wins: number;
  losses: number;
  gross_win: number;
  gross_loss: number;
}

export interface PositionRow {
  run: string;
  /** Present only for manual positions, which can be closed by hand. */
  id?: string;
  mark?: number | null;
  unrealised_pnl?: number | null;
  ticker: string;
  direction: string;
  size: number | null;
  entry_time: string;
  entry_price: number | null;
  exit_time: string;
  exit_price: number | null;
  exit_reason: string;
  pnl: number | null;
  pnl_pct: string;
  account_id: string;
}

export interface PositionDetail {
  id: string;
  account_id: string;
  ticker: string;
  direction: string;
  size: number;
  entry_price: number;
  entry_time: string;
  mark: number | null;
  unrealised_pnl: number | null;
}

export interface ClosedPosition extends PositionDetail {
  exit_price: number;
  exit_time: string;
  exit_reason: string;
  pnl: number;
}

export interface PositionsResponse {
  open: PositionRow[];
  closed: PositionRow[];
  open_count: number;
  closed_count: number;
  realised_pnl: number;
  unrealised_pnl: number;
  total_pnl: number;
}

export interface Stats {
  sessions: number;
  accounts: number;
  total_balance: number;
  trades: number;
  realised_pnl: number;
  unrealised_pnl: number;
  open_positions: number;
  /** Realised + unrealised, so an open trade shows in the headline. */
  total_pnl: number;
  win_rate: number | null;
  wins: number;
  losses: number;
  avg_win: number;
  avg_loss: number;
  best_trade: number | null;
  worst_trade: number | null;
  profit_factor: number | null;
  strategies: number;
  live_sessions: number;
}

export interface Account {
  account_id: string;
  name: string;
  provider: string;
  currency: string;
  /** Current balance. Creation takes `starting_balance`; the stored record
   *  and every read-back call it `balance`. */
  balance: number;
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
  entry_price: number | null;
  entry_time: string | null;
  stop_price: number | null;
  target_price: number | null;
  last_price: number | null;
  bars_seen: number;
  trades_taken: number;
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
  home_source?: string;
  default_home?: string;
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
    stats: () => get<{ stats: Record<string, StrategyStats> }>("/strategies/stats"),
    duplicate: (name: string, newName?: string) =>
      post<{ name: string; path: string }>(
        `/strategies/${name}/duplicate${newName ? `?new_name=${encodeURIComponent(newName)}` : ""}`, {}),
    source: (name: string) =>
      get<{ name: string; source: string; path: string }>(`/strategies/${name}/source`),
    create: (body: { name: string; source?: string; overwrite?: boolean }) =>
      post<{ name: string; path: string }>("/strategies", body),
    remove: (name: string) => del<{ deleted: string }>(`/strategies/${name}`),
  },
  providers: {
    list: (includeStubs = false) =>
      get<ProviderGroups & { providers: Provider[] }>(
        `/providers?include_stubs=${includeStubs}`),
  },
  stats: {
    get: () => get<Stats>("/stats"),
    equity: () => get<{ points: EquityPoint[]; trades: number; final: number }>("/equity"),
    distribution: () => get<PnlDistribution>("/pnl-distribution"),
  },
  config: {
    get: () => get<AppConfig>("/config"),
    setHome: (home: string) =>
      req<{ home: string; restart_required: boolean; overridden_by: string | null }>(
        "PUT", "/config/home", { home }),
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
  orders: {
    place: (body: {
      ticker: string; direction: "long" | "short";
      /** Give one or the other — units, or the cash to convert at fill. */
      size?: number; notional?: number;
      account_id?: string; closing?: boolean; reference_price?: number;
      stop_loss?: number; take_profit?: number;
    }) => post<{ position_id: string; attached_orders: string[];
                 account_id: string; ticker: string; direction: string;
                 size: number; fill_price: number; balance: number }>("/orders", body),
    pending: (accountId?: string, ticker?: string) => {
      const qs = new URLSearchParams();
      if (accountId) qs.set("account_id", accountId);
      if (ticker) qs.set("ticker", ticker);
      return get<{ orders: PendingOrder[]; types: { kind: string; description: string }[] }>(
        `/orders/pending${qs.toString() ? `?${qs}` : ""}`);
    },
    placePending: (body: {
      ticker: string; direction: "long" | "short"; size: number;
      order_type: string; trigger_price: number; limit_price?: number;
      account_id?: string; position_id?: string;
    }) => post<PendingOrder>("/orders/pending", body),
    cancelPending: (id: string) => del<PendingOrder>(`/orders/pending/${id}`),
    monitor: () => get<OrderMonitor>("/orders/monitor"),
    news: (q: string, limit = 20) =>
      get<{ query: string; items: NewsItem[] }>(
        `/news?q=${encodeURIComponent(q)}&limit=${limit}`),
    quickSearch: (q: string) =>
      get<{ groups: QuickGroup[] }>(`/quick-search?q=${encodeURIComponent(q)}`),
    alerts: (ticker?: string) =>
      get<{ alerts: Alert[]; conditions: { kind: string; description: string }[];
            recently_fired: Alert[] }>(
        `/alerts${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ""}`),
    createAlert: (body: { ticker: string; level: number; condition: string;
                          note?: string; repeat?: boolean }) =>
      post<Alert>("/alerts", body),
    deleteAlert: (id: string) => del<Alert>(`/alerts/${id}`),
    rearmAlert: (id: string) => post<Alert>(`/alerts/${id}/rearm`, {}),
    acknowledgeAlerts: () => post<{ acknowledged: number }>("/alerts/acknowledge", {}),
    indicators: () => get<{ indicators: IndicatorMeta[] }>("/indicators"),
    indicator: (kind: string, ticker: string, period: number,
                interval: string, days: number) =>
      get<IndicatorSeries>(
        `/indicator/${kind}/${encodeURIComponent(ticker)}` +
        `?period=${period}&interval=${interval}&days=${days}`),
    search: (q: string) =>
      get<{ results: Instrument[] }>(`/search?q=${encodeURIComponent(q)}`),
    history: (ticker: string, interval = "1h", days = 30) =>
      get<PriceHistory>(
        `/history/${encodeURIComponent(ticker)}?interval=${interval}&days=${days}`),
    quote: (ticker: string) =>
      get<{ ticker: string; price: number; time: string }>(
        `/quote/${encodeURIComponent(ticker)}`),
  },
  positions: {
    list: (accountId?: string) =>
      get<PositionsResponse>(
        `/positions${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ""}`),
    get: (id: string) => get<PositionDetail>(`/positions/${id}`),
    close: (id: string) => post<ClosedPosition>(`/positions/${id}/close`, {}),
  },
  jobs: {
    list: () => get<{ jobs: Job[] }>("/jobs"),
    get: <T>(id: string) => get<Job<T>>(`/jobs/${id}`),
    cancel: (id: string) => post<{ cancelling: string }>(`/jobs/${id}/cancel`, {}),
  },
  sessions: {
    list: () => get<{ sessions: SessionEntry[] }>("/sessions"),
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
