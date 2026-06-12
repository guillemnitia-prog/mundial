"""Modelo Dixon-Coles (Poisson bivariante con corrección de bajos marcadores y time-decay).

SPEC §3.1. Estimador PURO (numpy/scipy), sin acoplamiento a la base de datos: recibe partidos
en memoria y devuelve probabilidades de mercado a partir de la matriz de marcadores.

Forma log-lineal aditiva:
    λ_home = exp(μ + atk_home + def_away + γ·local)
    λ_away = exp(μ + atk_away + def_home)
SPEC escribe "media(atk)=1"; en esta forma aditiva el equivalente identificable es media(atk)=0
(y media(def)=0), absorbiendo la constante en μ. Tras el ajuste se recentran atk/def a media 0.

La ventaja local γ se aprende de partidos NO neutrales y, en el Mundial, se aplica SOLO cuando
juega un anfitrión (USA/Canadá/México) — al lado que corresponda.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

DEFAULT_XI = 0.0   # time-decay (1/día); se calibra por RPS/Brier en la Fase 7
MAX_GOALS = 10     # truncado de la matriz de marcadores (0..MAX_GOALS por equipo)


def tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Corrección Dixon-Coles de bajos marcadores."""
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def decay_weights(ages_days: np.ndarray, xi: float) -> np.ndarray:
    """Pesos de time-decay w = exp(−ξ·Δt_días). ξ=0 → todos 1."""
    return np.exp(-xi * np.asarray(ages_days, dtype=float))


@dataclass
class DixonColesModel:
    teams: list[str] = field(default_factory=list)
    attack: dict[str, float] = field(default_factory=dict)
    defense: dict[str, float] = field(default_factory=dict)
    home_adv: float = 0.0
    rho: float = 0.0
    mu: float = 0.0

    # --- ajuste -----------------------------------------------------------

    def fit(self, matches, xi: float = DEFAULT_XI, as_of=None, maxiter: int = 500) -> "DixonColesModel":
        """Ajusta por máxima verosimilitud ponderada (time-decay).

        `matches`: iterable de (home, away, home_goals, away_goals, date, neutral).
        `date` puede ser datetime/date o None; si hay fechas y xi>0 se aplica decay respecto a
        `as_of` (o la fecha máxima observada).
        """
        rows = [m for m in matches if m[2] is not None and m[3] is not None]
        if not rows:
            raise ValueError("No hay partidos con marcador para ajustar.")

        teams = sorted({r[0] for r in rows} | {r[1] for r in rows})
        idx = {t: i for i, t in enumerate(teams)}
        n = len(teams)

        home_i = np.array([idx[r[0]] for r in rows])
        away_i = np.array([idx[r[1]] for r in rows])
        hg = np.array([r[2] for r in rows], dtype=int)
        ag = np.array([r[3] for r in rows], dtype=int)
        not_neutral = np.array([0.0 if r[5] else 1.0 for r in rows])  # γ solo si no neutral

        weights = self._compute_weights(rows, xi, as_of)

        # Vector de parámetros: [attack(n), defense(n), home_adv, rho, mu]
        def unpack(p):
            atk = p[:n]
            dfn = p[n:2 * n]
            gamma, rho, mu = p[2 * n], p[2 * n + 1], p[2 * n + 2]
            return atk, dfn, gamma, rho, mu

        def neg_log_lik(p):
            atk, dfn, gamma, rho, mu = unpack(p)
            log_lh = mu + atk[home_i] + dfn[away_i] + gamma * not_neutral
            log_la = mu + atk[away_i] + dfn[home_i]
            lam = np.exp(np.clip(log_lh, -10, 10))
            mua = np.exp(np.clip(log_la, -10, 10))

            # log Poisson para ambos marcadores.
            ll = poisson.logpmf(hg, lam) + poisson.logpmf(ag, mua)

            # Corrección τ (solo afecta a celdas con goles <=1).
            tau_vals = self._tau_vectorized(hg, ag, lam, mua, rho)
            ll = ll + np.log(np.clip(tau_vals, 1e-12, None))

            return -np.sum(weights * ll)

        x0 = np.zeros(2 * n + 3)
        x0[2 * n] = 0.25  # γ inicial razonable
        x0[2 * n + 1] = -0.05  # ρ inicial
        bounds = [(-3, 3)] * (2 * n) + [(-1, 2), (-0.2, 0.2), (-2, 2)]

        res = minimize(neg_log_lik, x0, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": maxiter})

        atk, dfn, gamma, rho, mu = unpack(res.x)
        # Recentrar a media 0 (identificabilidad); la media se absorbe en μ.
        atk = atk - atk.mean()
        dfn = dfn - dfn.mean()

        self.teams = teams
        self.attack = {t: float(atk[idx[t]]) for t in teams}
        self.defense = {t: float(dfn[idx[t]]) for t in teams}
        self.home_adv = float(gamma)
        self.rho = float(rho)
        self.mu = float(mu)
        return self

    def _compute_weights(self, rows, xi, as_of):
        dates = [r[4] for r in rows]
        if xi <= 0 or any(d is None for d in dates):
            return np.ones(len(rows))
        ref = as_of or max(dates)
        ages = np.array([(ref - d).days for d in dates], dtype=float)
        return decay_weights(ages, xi)

    @staticmethod
    def _tau_vectorized(hg, ag, lam, mua, rho):
        out = np.ones_like(lam, dtype=float)
        m00 = (hg == 0) & (ag == 0)
        m01 = (hg == 0) & (ag == 1)
        m10 = (hg == 1) & (ag == 0)
        m11 = (hg == 1) & (ag == 1)
        out[m00] = 1.0 - lam[m00] * mua[m00] * rho
        out[m01] = 1.0 + lam[m01] * rho
        out[m10] = 1.0 + mua[m10] * rho
        out[m11] = 1.0 - rho
        return out

    # --- predicción -------------------------------------------------------

    def _rates(self, home: str, away: str, neutral: bool, host_side: str | None):
        atk_h, def_h = self.attack[home], self.defense[home]
        atk_a, def_a = self.attack[away], self.defense[away]
        gh = ga = 0.0
        if not neutral:
            # En el Mundial, host_side indica a qué lado se aplica γ; por defecto al local.
            if host_side == "away":
                ga = self.home_adv
            else:
                gh = self.home_adv
        lam = math.exp(self.mu + atk_h + def_a + gh)
        mua = math.exp(self.mu + atk_a + def_h + ga)
        return lam, mua

    def score_matrix(self, home: str, away: str, neutral: bool = True,
                     host_side: str | None = None, max_goals: int = MAX_GOALS) -> np.ndarray:
        """Matriz P(home=x, away=y) con corrección τ, normalizada a suma 1."""
        lam, mua = self._rates(home, away, neutral, host_side)
        xs = np.arange(0, max_goals + 1)
        ph = poisson.pmf(xs, lam)
        pa = poisson.pmf(xs, mua)
        mat = np.outer(ph, pa)
        # Aplicar τ a las 4 celdas especiales.
        mat[0, 0] *= 1.0 - lam * mua * self.rho
        mat[0, 1] *= 1.0 + lam * self.rho
        mat[1, 0] *= 1.0 + mua * self.rho
        mat[1, 1] *= 1.0 - self.rho
        mat = np.clip(mat, 0.0, None)
        total = mat.sum()
        return mat / total if total > 0 else mat

    def predict_markets(self, home: str, away: str, neutral: bool = True,
                        host_side: str | None = None, ou_lines=(2.5,),
                        top_scores: int = 5) -> dict:
        """Deriva todos los mercados de la matriz de marcadores."""
        mat = self.score_matrix(home, away, neutral, host_side)
        n = mat.shape[0]
        idx = np.indices((n, n))
        home_win = float(np.tril(mat, -1).sum())   # x>y
        away_win = float(np.triu(mat, 1).sum())    # x<y
        draw = float(np.trace(mat))

        total_goals = idx[0] + idx[1]
        over_under = {}
        for line in ou_lines:
            over = float(mat[total_goals > line].sum())
            over_under[f"over_{line}"] = over
            over_under[f"under_{line}"] = 1.0 - over

        btts_yes = float(mat[1:, 1:].sum())  # ambos marcan (x>=1 e y>=1)

        flat = [((x, y), float(mat[x, y])) for x in range(n) for y in range(n)]
        flat.sort(key=lambda kv: kv[1], reverse=True)
        correct_score = {f"{x}-{y}": p for (x, y), p in flat[:top_scores]}

        return {
            "1x2": {"home": home_win, "draw": draw, "away": away_win},
            "over_under": over_under,
            "btts": {"yes": btts_yes, "no": 1.0 - btts_yes},
            "correct_score": correct_score,
        }

    def team_strength(self, team: str) -> dict:
        return {"attack": self.attack[team], "defense": self.defense[team]}

    # --- serialización ----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "teams": self.teams,
            "attack": self.attack,
            "defense": self.defense,
            "home_adv": self.home_adv,
            "rho": self.rho,
            "mu": self.mu,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DixonColesModel":
        return cls(
            teams=list(d["teams"]),
            attack=dict(d["attack"]),
            defense=dict(d["defense"]),
            home_adv=float(d["home_adv"]),
            rho=float(d["rho"]),
            mu=float(d["mu"]),
        )
