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

// --- strategies ---
export const api = {
  strategies: {
    list: () => get<{ strategies: Strategy[] }>("/strategies"),
  },
  providers: {
    list: () => get<{ providers: Provider[] }>("/providers"),
  },
  accounts: {
    list: () => get<{ accounts: Account[] }>("/accounts"),
    get: (id: string) => get<Account>(`/accounts/${id}`),
    create: (body: { name: string; provider?: string; starting_balance?: number }) =>
      post<Account>("/accounts", body),
  },
  credentials: {
    list: () => get<{ credentials: unknown[] }>("/credentials"),
    set: (body: { provider: string; key: string; env_var?: string; value?: string }) =>
      post<{ ok: boolean }>("/credentials", body),
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
    }) => post<BacktestResult>("/backtest", body),
    runMulti: (body: {
      strategy: string;
      ticker: string;
      windows: [string, string][];
      interval?: string;
      account?: number;
    }) => post<Record<string, unknown>>("/backtest-multi", body),
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
