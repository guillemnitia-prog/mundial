// Cliente de la API JSON (FastAPI). Cookie httpOnly → credentials:"include".

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
// Backend directo para el WebSocket del chat (no pasa por el proxy /api).
export const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE || "ws://localhost:8000";

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

export const api = {
  get: <T>(p: string) => req<T>(p),
  post: <T>(p: string, body?: unknown) =>
    req<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(p: string) => req<T>(p, { method: "DELETE" }),
};

// --- tipos compartidos ---
export interface MatchListItem {
  id: number;
  utc_date: string | null;
  stage: string;
  group_label: string | null;
  state: string;
  status: string;
  home: string | null;
  away: string | null;
  home_code: string | null;
  away_code: string | null;
  home_goals: number | null;
  away_goals: number | null;
  n_picks: number;
}

export interface TeamInfo {
  name: string;
  fifa_code: string | null;
  elo: number | null;
  is_host: boolean;
}

export interface Pick {
  prediction_id: number;
  market: string;
  outcome: string;
  model_prob: number;
  fair_prob: number;
  offered_odds: number;
  ev_pct: number;
  confidence: string | null;
  stake_eur: number;
  stake_pct: number;
  too_small: boolean;
  your_decision: string | null;
}

export interface MatchDetail {
  id: number;
  utc_date: string | null;
  stage: string;
  group_label: string | null;
  state: string;
  status: string;
  neutral_venue: boolean;
  home_goals: number | null;
  away_goals: number | null;
  analyzed_at: string | null;
  analysis_stage: string | null;
  home: TeamInfo | null;
  away: TeamInfo | null;
  home_form: string[];
  away_form: string[];
  picks: Pick[];
  message: string | null;
  odds_proxy_notice: string;
  stats: { x1x2?: { home: number; draw: number; away: number }; over25?: number; btts_yes?: number } | null;
}

export interface Me {
  id: number;
  username: string;
  role: string;
  has_onboarded: boolean;
  balance: number;
}
