"""Tests del replay de Elo histórico (Fase 7)."""

from datetime import date

from src.models.elo_history import draw_samples, replay_elo


def test_replay_winner_rises():
    # A gana siempre a B en campo neutral → A sube, B baja.
    matches = [(date(2020, 1, i + 1), "A", "B", 2, 0, True) for i in range(10)]
    records, ratings = replay_elo(matches)
    assert ratings["A"] > 1500 > ratings["B"]
    assert len(records) == 10
    # El primer partido parte de base 1500 para ambos.
    assert records[0]["pre_home"] == 1500.0 and records[0]["pre_away"] == 1500.0


def test_draw_samples_shape():
    matches = [
        (date(2020, 1, 1), "A", "B", 1, 1, True),
        (date(2020, 1, 2), "A", "B", 2, 0, False),
    ]
    records, _ = replay_elo(matches)
    samples = draw_samples(records)
    assert samples[0][1] is True   # empate
    assert samples[1][1] is False  # no empate
    # El segundo no neutral → dr incluye la ventaja local (+100 sobre la diferencia de rating).
    assert samples[1][0] > samples[0][0]
