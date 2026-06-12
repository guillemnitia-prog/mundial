// Cliente de la API JSON (FastAPI). Cookie httpOnly → credentials:"include".

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

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
  home: string | null;
  away: string | null;
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
  neutral_venue: boolean;
  analyzed_at: string | null;
  analysis_stage: string | null;
  home: TeamInfo | null;
  away: TeamInfo | null;
  home_form: string[];
  away_form: string[];
  picks: Pick[];
  message: string | null;
  odds_proxy_notice: string;
}

export interface Me {
  id: number;
  username: string;
  role: string;
  has_onboarded: boolean;
  balance: number;
}
