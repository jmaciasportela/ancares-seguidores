from datetime import timedelta

import pytest

from app.parsers.calendar import parse_calendar, parse_score, parse_when, split_teams
from app.parsers.common import ParseError, detect_kind, read_rows
from app.parsers.ranking import parse_ranking

TEAMS = ["CDF Voleibol Ancares UVa", "VCV Castilla", "VCV Colón", "Maristas Burgos A", "C.D. San José"]


def test_detect_kind(ranking_bytes, calendar_bytes):
    assert detect_kind(read_rows(ranking_bytes)) == "ranking"
    assert detect_kind(read_rows(calendar_bytes)) == "calendar"


def test_not_xls_raises():
    with pytest.raises(ParseError):
        read_rows(b"<html>Comprobando tu navegador</html>")


def test_ranking_sample(ranking_bytes):
    standings = parse_ranking(read_rows(ranking_bytes))
    assert len(standings) == 10
    assert [s.position for s in standings] == list(range(1, 11))
    ours = [s for s in standings if "Ancares" in s.team]
    assert len(ours) == 1 and ours[0].position == 5
    assert "Partidos jugados" in ours[0].extra


def test_calendar_sample(ranking_bytes, calendar_bytes):
    teams = [s.team for s in parse_ranking(read_rows(ranking_bytes))]
    matches = parse_calendar(read_rows(calendar_bytes), teams)
    assert len(matches) == 123  # 125 filas menos 2 vacías
    assert {m.round_no for m in matches} == set(range(1, 19))
    games = [m for m in matches if not m.is_bye]
    # Todos los partidos quedan separados en dos equipos conocidos
    assert all(m.home in teams and m.away in teams for m in games)
    assert all(m.home in teams for m in matches if m.is_bye)
    first = next(m for m in games if m.home == "CDF Voleibol Ancares UVa")
    assert first.away == "VCV Castilla"
    assert first.starts_at.isoformat() == "2026-10-17T17:00:00+02:00"
    assert first.venue == "Fuente la Mora"
    assert first.home_sets is None and first.partials == []
    # Partido con solo pabellón
    assert any(m.starts_at is None and m.venue == "Polideportivo Manuel Sánchez Cisneros" for m in games)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("CDF Voleibol Ancares UVa VCV Castilla", ("CDF Voleibol Ancares UVa", "VCV Castilla", False)),
        ("descansa Maristas Burgos A", ("Maristas Burgos A", None, True)),
        ("Maristas Burgos A descansa", ("Maristas Burgos A", None, True)),
        ("VCV Colón Equipo Nuevo", ("VCV Colón", "Equipo Nuevo", False)),
        ("Equipo Nuevo C.D. San José", ("Equipo Nuevo", "C.D. San José", False)),
        ("Nadie Conocido Otro", ("Nadie Conocido Otro", None, False)),
    ],
)
def test_split_teams(raw, expected):
    assert split_teams(raw, TEAMS) == expected


def test_parse_when():
    when, venue = parse_when("Dom, 18/10/2026 10:30 GMT+2 Fuente la Mora")
    assert when.isoformat() == "2026-10-18T10:30:00+02:00" and venue == "Fuente la Mora"
    assert parse_when("Polideportivo X") == (None, "Polideportivo X")
    assert parse_when("") == (None, None)
    when, _ = parse_when("Sáb, 05/12/2026 12:00")
    assert when.utcoffset() == timedelta(hours=1)  # Europe/Madrid en invierno
    # Clupik pone GMT+2 también en noviembre: manda la hora de reloj en Madrid
    when, _ = parse_when("Dom, 08/11/2026 10:30 GMT+2 Fuente la Mora")
    assert when.isoformat() == "2026-11-08T10:30:00+01:00"


def test_parse_score():
    assert parse_score("3 - 1", "25-20, 22-25, 25-18, 25-10") == (3, 1, [[25, 20], [22, 25], [25, 18], [25, 10]])
    assert parse_score("", "25-20 25-18 25-10") == (3, 0, [[25, 20], [25, 18], [25, 10]])
    assert parse_score("", "----------") == (None, None, [])
