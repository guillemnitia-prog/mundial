"""Modelo Elo de selecciones (SPEC §3.2). Estimador PURO (sin BD/red).

Da una probabilidad 1X2 a partir de los ratings Elo de eloratings.net. La ventaja de anfitrión
se modela como +100 Elo al lado anfitrión (USA/Canadá/México), nunca en campo neutral.

Mapeo Elo→3 vías:
- W_e = 1 / (1 + 10^(−dr/400))  con dr = R_home − R_away (+100 al anfitrión si aplica).
  W_e es el resultado esperado (1=victoria, 0.5=empate, 0=derrota) = P(home) + 0.5·P(draw).
- P(draw) = d, calibrada por bin de |dr| (frecuencia empírica). Entonces:
      P(home) = W_e − d/2 ;  P(away) = (1 − W_e) − d/2
  Se recortan negativos y se renormaliza por seguridad.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

HOST_ELO_BONUS = 100.0
DEFAULT_BIN_WIDTH = 50.0     # ancho de bin de |dr| para la tasa de empate
_DEFAULT_DRAW_BASE = 0.30    # tasa de empate con equipos igualados
_DEFAULT_DRAW_SCALE = 350.0  # decaimiento con |dr|


def expected_score(r_home: float, r_away: float, host_side: str | None = None) -> float:
    """Resultado esperado del local (0..1). Ventaja de anfitrión = +100 Elo al lado host."""
    dr = r_home - r_away
    if host_side == "home":
        dr += HOST_ELO_BONUS
    elif host_side == "away":
        dr -= HOST_ELO_BONUS
    return 1.0 / (1.0 + 10.0 ** (-dr / 400.0))


def _default_draw_rate(abs_dr: float) -> float:
    """Curva paramétrica por defecto (si no se ha calibrado): decae con |dr|."""
    return _DEFAULT_DRAW_BASE * math.exp(-abs_dr / _DEFAULT_DRAW_SCALE)


@dataclass
class EloModel:
    bin_width: float = DEFAULT_BIN_WIDTH
    draw_rates: dict[int, float] = field(default_factory=dict)  # bin de |dr| → P(draw)

    def fit_draw_rates(self, matches, prior_weight: float = 5.0) -> "EloModel":
        """Calibra P(empate) por bin de |dr|.

        `matches`: iterable de (dr, is_draw). Suavizado bayesiano simple hacia la curva por defecto
        (prior_weight pseudo-observaciones) para bins con pocos datos.
        """
        sums: dict[int, float] = {}
        counts: dict[int, int] = {}
        for dr, is_draw in matches:
            b = int(abs(dr) // self.bin_width)
            sums[b] = sums.get(b, 0.0) + (1.0 if is_draw else 0.0)
            counts[b] = counts.get(b, 0) + 1

        rates: dict[int, float] = {}
        for b, c in counts.items():
            center = (b + 0.5) * self.bin_width
            prior = _default_draw_rate(center)
            rates[b] = (sums[b] + prior_weight * prior) / (c + prior_weight)
        self.draw_rates = rates
        return self

    def _draw_prob(self, abs_dr: float) -> float:
        if not self.draw_rates:
            return _default_draw_rate(abs_dr)
        b = int(abs_dr // self.bin_width)
        if b in self.draw_rates:
            return self.draw_rates[b]
        # Bin fuera de rango → usar el mayor bin calibrado o la curva por defecto.
        max_bin = max(self.draw_rates)
        return self.draw_rates[max_bin] if b > max_bin else _default_draw_rate(abs_dr)

    def predict_1x2(self, r_home: float, r_away: float, host_side: str | None = None) -> dict:
        we = expected_score(r_home, r_away, host_side)
        dr = (r_home - r_away) + (HOST_ELO_BONUS if host_side == "home"
                                  else -HOST_ELO_BONUS if host_side == "away" else 0.0)
        d = self._draw_prob(abs(dr))
        p_home = max(0.0, we - d / 2.0)
        p_away = max(0.0, (1.0 - we) - d / 2.0)
        p_draw = max(0.0, d)
        total = p_home + p_draw + p_away
        return {"home": p_home / total, "draw": p_draw / total, "away": p_away / total}

    # --- serialización ----------------------------------------------------

    def to_dict(self) -> dict:
        return {"bin_width": self.bin_width,
                "draw_rates": {str(k): v for k, v in self.draw_rates.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "EloModel":
        return cls(
            bin_width=float(d.get("bin_width", DEFAULT_BIN_WIDTH)),
            draw_rates={int(k): float(v) for k, v in d.get("draw_rates", {}).items()},
        )
