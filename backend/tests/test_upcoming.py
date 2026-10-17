from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.serializers import Ctx, upcoming
from app.services.live import live_id_of
from app.services.provisional import match_key

NOW = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)


def m(round_no, days=None, *, home="CDF Voleibol Ancares UVa", away="Rival", sets=None, bye=False, order=None):
    return SimpleNamespace(
        category_id=1, round_no=round_no, order=order or round_no * 10, home=home, away=away, is_ours=True, is_bye=bye,
        home_sets=sets, starts_at=NOW + timedelta(days=days) if days is not None else None,
    )


def rounds(matches):
    return [x.round_no for x in upcoming(matches, limit=5, now=NOW)]


def test_undated_round_goes_before_later_dated_rounds():
    # Juvenil/Cadete: la jornada 2 aún no tiene fecha y la 11 sí: después de la 1 va la 2
    season = [m(1, 1), m(2), m(3), m(11, 30), m(12, 37)]
    assert rounds(season) == [1, 2, 3, 11, 12]


def test_dated_matches_keep_date_order():
    # Partido aplazado: la jornada 3 se juega después que la 4
    assert rounds([m(3, 14), m(4, 7), m(5, 21)]) == [4, 3, 5]


def test_played_or_past_rounds_are_skipped():
    season = [
        m(6, -20, sets=3),          # jugado, con resultado
        m(7, -6),                   # fecha pasada sin resultado: ya jugado
        m(7, away="Otro rival"),    # mismo turno sin fecha: jornada superada, se descarta
        m(8, 2),
        m(9),
        m(10, bye=True),
    ]
    assert rounds(season) == [8, 9]


def test_match_in_progress_still_counts():
    assert rounds([m(1, -0.05), m(2, 7)]) == [1, 2]  # empezó hace un rato (menos de 3 h)


def test_live_match_goes_first_even_if_excel_date_passed():
    # Aplazado: el Excel dice la semana pasada, pero el admin lo está emitiendo ahora
    postponed = m(3, -7)
    key = match_key(postponed)
    row = SimpleNamespace(
        live_id=live_id_of(key), ended_at=None, updated_at=NOW - timedelta(minutes=1),
        state={"sets": [[10, 8, False]], "status": "playing"},
    )
    ctx = Ctx(live={key: row})
    assert [x.round_no for x in upcoming([postponed, m(4, 2), m(5, 9)], ctx, limit=5, now=NOW)] == [3, 4, 5]
    # Sin directo, el partido de fecha pasada se da por jugado
    assert rounds([postponed, m(4, 2), m(5, 9)]) == [4, 5]
