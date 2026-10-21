import pytest
from sqlalchemy import select

from conftest import CALENDAR_XLS, RANKING_XLS
from app.db import SessionLocal
from app.models import Match, Standing
from app.services.stats import Result, build_table, match_points

OURS = "CDF Voleibol Ancares UVa"
HOME_WIN = [[25, 20], [20, 25], [25, 18], [25, 22]]  # 3-1


@pytest.mark.parametrize(
    "own,opp,points",
    [(3, 0, 3), (3, 1, 3), (3, 2, 2), (2, 3, 1), (1, 3, 0), (0, 3, 0), (2, 0, 3), (2, 1, 2), (1, 2, 1), (0, 2, 0)],
)
def test_match_points(own, opp, points):
    assert match_points(own, opp) == points


def r(home, away, hs, as_, partials, round_no=1):
    return Result(round_no, f"Jornada {round_no}", 0, None, home, away, hs, as_, partials)


def test_table_tiebreakers():
    results = [
        r("A", "B", 3, 2, [[25, 20], [20, 25], [25, 20], [20, 25], [15, 10]]),  # A 2 pts, B 1
        r("C", "D", 3, 2, [[25, 23], [23, 25], [25, 23], [23, 25], [15, 13]]),  # C 2 pts, D 1
        r("A", "D", 0, 3, [[10, 25], [10, 25], [10, 25]]),  # D 3 pts
        r("C", "B", 0, 3, [[20, 25], [20, 25], [20, 25]]),  # B 3 pts
    ]
    table = build_table(["A", "B", "C", "D"], results)
    # B y D: 4 pts, 1 victoria y sets 5-3; D tiene mejor cociente de puntos (184/141 frente a 175/165)
    # A y C: 2 pts, 1 victoria y sets 3-5; C pierde por menos y queda por delante (171/184 frente a 135/175)
    assert [(t.team, t.points) for t in table] == [("D", 4), ("B", 4), ("C", 2), ("A", 2)]
    assert table[0].sets_for == 5 and table[0].sets_against == 3


@pytest.fixture()
def league(client, ranking_bytes, calendar_bytes):
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    files = [("files", (RANKING_XLS.name, ranking_bytes, "application/vnd.ms-excel")),
             ("files", (CALENDAR_XLS.name, calendar_bytes, "application/vnd.ms-excel"))]
    client.post("/api/admin/upload", files=files, data={"category_id": cat["id"]})
    return cat


def play_rounds(rounds=(1, 2)):
    """Resultados oficiales simulados: Ancares gana 3-2 a Castilla y 3-0 a Colón; el resto gana el local 3-1."""
    with SessionLocal() as s:
        for m in s.scalars(select(Match).where(Match.round_no.in_(rounds), Match.is_bye.is_(False))).all():
            if m.home == OURS and m.away == "VCV Castilla":
                m.home_sets, m.away_sets = 3, 2
                m.partials = [[25, 20], [20, 25], [25, 23], [23, 25], [15, 13]]
            elif m.home == OURS and m.away == "VCV Colón":
                m.home_sets, m.away_sets, m.partials = 3, 0, [[25, 10], [25, 12], [31, 29]]
            elif m.away:
                m.home_sets, m.away_sets, m.partials = 3, 1, HOME_WIN
        s.commit()


def test_stats_empty_before_first_round(client, league):
    data = client.get("/api/categories/infantil/stats").json()
    assert data["rounds"] == [] and data["teams"] == []
    assert data["ours"]["played"] == 0 and data["ours"]["position"] == 5
    assert data["provisional_table"] is None


def test_stats_with_results(client, league):
    play_rounds()
    data = client.get("/api/categories/infantil/stats").json()
    assert [x["round_no"] for x in data["rounds"]] == [1, 2]
    ours = next(t for t in data["teams"] if t["is_ours"])
    # Infantil puntúa 2-1-0 (normativa FVCL): dos victorias son 4 puntos; descansa en la jornada 2
    assert len(ours["positions"]) == 2 and ours["points"] == [4, 4]
    assert data["approximate"] is True  # la tabla oficial de muestra sigue a cero

    o = data["ours"]
    assert (o["played"], o["won"], o["lost"], o["sets_for"], o["sets_against"]) == (2, 2, 0, 6, 2)
    assert o["best_streak"] == 2 and [x["result"] for x in o["streak"]] == ["W", "W"]
    assert o["longest_set"] == {"score": "31-29", "rival": "VCV Colón", "round_name": "Jornada 1"}
    assert o["clearest_win"]["score"] == "3-0" and o["clearest_win"]["rival"] == "VCV Colón"
    assert o["sets_won_pct"] == 75

    # Si la tabla oficial coincide con la reconstrucción, deja de ser aproximada
    final = {t["team"]: t["points"][-1] for t in data["teams"]}
    with SessionLocal() as s:
        for st in s.scalars(select(Standing)).all():
            st.points = final.get(st.team, 0)
            st.played = sum(1 for m in s.scalars(select(Match).where(Match.home_sets.is_not(None))).all()
                            if st.team in (m.home, m.away))
        s.commit()
    assert client.get("/api/categories/infantil/stats").json()["approximate"] is False


def test_provisional_table(client, league):
    play_rounds()
    with SessionLocal() as s:
        m = s.scalars(select(Match).where(Match.round_no == 3, Match.home == OURS)).first()
        body = {"category_id": league["id"], "round_no": 3, "home": m.home, "away": m.away,
                "home_sets": 3, "away_sets": 0, "partials": [[25, 10, True], [25, 10, True], [25, 10, True]]}
    assert client.post("/api/scoring/results", json=body).status_code == 200

    data = client.get("/api/categories/infantil/stats").json()
    table = data["provisional_table"]
    assert table is not None
    ours = next(row for row in table if row["is_ours"])
    # La tabla oficial de muestra está a cero, pero el calendario ya trae las jornadas 1 y 2: la app suma
    # esos resultados oficiales (dos victorias, 4 puntos en Infantil) y encima el 3-0 provisional (2 más)
    assert ours["position"] == 1 and ours["points"] == 6
    detail = client.get("/api/categories/infantil").json()
    updated = {r["team"]: r for r in detail["standings_updated"]}
    assert updated["CDF Voleibol Ancares UVa"]["points"] == 4
    assert detail["standings_missing"]["rounds"] == ["Jornada 1", "Jornada 2"]
    # En 2-1-0 el que pierde también suma: Maristas Burgos A, 1 punto más que en la tabla actualizada
    rows = {row["team"]: row for row in table}
    assert rows["Maristas Burgos A"]["points"] == updated["Maristas Burgos A"]["points"] + 1
    assert data["ours"]["has_provisional"] is True
    assert data["ours"]["streak"][-1] == {"round_name": "Jornada 3", "rival": "Maristas Burgos A",
                                          "result": "W", "score": "3-0", "provisional": True}
    # La evolución solo usa resultados oficiales
    assert [x["round_no"] for x in data["rounds"]] == [1, 2]
