"""Test del parseo del histórico martj42 (Fase 7)."""

from datetime import date

from src.ingest.historical import parse_results

SAMPLE = """date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
1872-11-30,Scotland,England,0,0,Friendly,Glasgow,Scotland,FALSE
2018-07-15,France,Croatia,4,2,FIFA World Cup,Moscow,Russia,TRUE
2026-06-27,Panama,England,NA,NA,FIFA World Cup,East Rutherford,United States,TRUE
"""


def test_parse_results_filters_na_and_parses():
    rows = parse_results(SAMPLE)
    assert len(rows) == 2  # la fila NA (futura) se descarta
    d, home, away, hg, ag, neutral = rows[0]
    assert d == date(1872, 11, 30)
    assert (home, away, hg, ag) == ("Scotland", "England", 0, 0)
    assert neutral is False
    # La final 2018 fue en campo neutral.
    assert rows[1][5] is True
