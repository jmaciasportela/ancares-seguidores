from datetime import date

import pytest

from conftest import RANKING_XLS
from app.db import engine, init_db
from app.services.tournament import TournamentError, parse_lines, parse_result

OURS = "Ancares UVa"
LIST = """
# Torneo de Navidad
19/12 10:00 · Grupo A · Ancares UVa - CV Laguna · Pabellón Pisuerga
19/12 11:00 · Grupo A · CV Laguna vs VCV Castilla
19/12 12:00 · Grupo A · VCV Castilla – Ancares UVa
20/12 10:30 · Final · Ancares UVa - VCV Castilla · Pabellón Pisuerga
"""


def test_parse_lines():
    rows = parse_lines(LIST, today=date(2026, 10, 12))
    assert len(rows) == 4 and all(r.error is None for r in rows)
    first = rows[0]
    assert (first.date, first.time, first.phase, first.home, first.away, first.venue) == (
        "2026-12-19", "10:00", "Grupo A", OURS, "CV Laguna", "Pabellón Pisuerga")
    assert rows[1].home == "CV Laguna" and rows[1].away == "VCV Castilla"  # "vs"
    assert rows[3].phase == "Final"
    # Enero con "hoy" en octubre: año siguiente
    assert parse_lines("10/01 10:00 · A - B", today=date(2026, 10, 12))[0].date == "2027-01-10"
    errs = parse_lines("19/12 · A - B\nsolo texto", today=date(2026, 10, 12))
    assert "hora" in errs[0].error and "equipos" in errs[1].error


def test_parse_result():
    assert parse_result("3-1") == (3, 1, [])
    assert parse_result("25-20 23-25 15-12") == (2, 1, [[25, 20], [23, 25], [15, 12]])
    assert parse_result("") == (None, None, [])
    with pytest.raises(TournamentError):
        parse_result("ganamos")


@pytest.fixture()
def torneo(client):
    client.post("/api/admin/login", json={"password": "secreto"})
    fmt = {"mode": "fixed", "sets": 2, "points": 25, "tiebreak": None}
    cat = client.post("/api/admin/categories", json={"name": "Torneo de Navidad", "kind": "tournament", "score_format": fmt}).json()
    assert cat["kind"] == "tournament"
    rows = client.post(f"/api/admin/categories/{cat['id']}/matches/parse", json={"text": LIST}).json()["rows"]
    body = {"matches": [{k: r[k] for k in ("phase", "date", "time", "home", "away", "venue")} for r in rows]}
    assert client.post(f"/api/admin/categories/{cat['id']}/matches/bulk", json=body).json()["created"] == 4
    return cat


def matches(client, cat):
    return client.get(f"/api/admin/categories/{cat['id']}/matches").json()


def test_tournament_flow(client, torneo):
    ms = matches(client, torneo)
    assert [m["phase"] for m in ms] == ["Grupo A"] * 3 + ["Final"]
    assert [m["round_no"] for m in ms] == [1, 1, 1, 2] and ms[0]["time"] == "10:00"

    detail = client.get("/api/categories/torneo-de-navidad").json()
    assert detail["kind"] == "tournament" and detail["standings"] == []
    assert [g["name"] for g in detail["groups"]] == ["Grupo A"]  # la final no tiene tabla
    assert {r["team"] for r in detail["groups"][0]["standings"]} == {OURS, "CV Laguna", "VCV Castilla"}

    # Resultado puesto por el admin: cuenta directamente
    first = ms[0]
    payload = {k: first[k] for k in ("phase", "date", "time", "home", "away", "venue")}
    assert client.put(f"/api/admin/matches/{first['id']}", json={**payload, "result": "25-20 25-18"}).status_code == 200
    table = client.get("/api/categories/torneo-de-navidad").json()["groups"][0]["standings"]
    assert table[0]["team"] == OURS and table[0]["points"] == 3

    # Resultado de un anotador: provisional hasta que lo confirme el admin
    third = ms[2]
    pub = {"category_id": torneo["id"], "round_no": 1, "home": third["home"], "away": third["away"],
           "home_sets": 0, "away_sets": 2, "partials": [[20, 25, True], [22, 25, True]]}
    assert client.post("/api/scoring/results", json=pub).status_code == 200
    detail = client.get("/api/categories/torneo-de-navidad").json()
    m = next(x for x in detail["matches"] if x["id"] == third["id"])
    assert m["provisional"] and m["tournament"] is True and not m["played"]
    group = detail["groups"][0]
    assert group["standings"][0]["points"] == 3  # sin provisionales
    ours = next(r for r in group["with_provisional"] if r["team"] == OURS)
    assert ours["points"] == 6 and ours["position"] == 1

    prov = client.get("/api/admin/provisional").json()[0]
    assert prov["tournament"] is True
    assert client.post(f"/api/admin/provisional/{prov['id']}/confirm").json()["ok"]
    detail = client.get("/api/categories/torneo-de-navidad").json()
    m = next(x for x in detail["matches"] if x["id"] == third["id"])
    assert m["played"] and m["provisional"] is None and (m["home_sets"], m["away_sets"]) == (0, 2)
    assert detail["groups"][0]["with_provisional"] is None
    assert client.get("/api/admin/provisional").json() == []


def test_edit_keeps_provisional_and_delete(client, torneo):
    ms = matches(client, torneo)
    final = ms[3]
    pub = {"category_id": torneo["id"], "round_no": 2, "home": final["home"], "away": final["away"],
           "home_sets": 2, "away_sets": 0, "partials": [[25, 10, True], [25, 12, True]]}
    assert client.post("/api/scoring/results", json=pub).status_code == 200
    # Se adelanta la final al día anterior: pasa a ser la primera fase y el provisional la sigue
    edit = {"phase": "Final", "date": "2026-12-18", "time": "18:00", "home": final["home"], "away": final["away"], "venue": None}
    assert client.put(f"/api/admin/matches/{final['id']}", json=edit).status_code == 200
    moved = next(m for m in matches(client, torneo) if m["id"] == final["id"])
    assert moved["round_no"] == 1 and moved["provisional"]["home_sets"] == 2
    # Borrar el partido borra su provisional
    assert client.delete(f"/api/admin/matches/{final['id']}").json()["ok"]
    assert client.get("/api/admin/provisional").json() == []
    assert len(matches(client, torneo)) == 3


def test_league_matches_are_not_editable(client, torneo, ranking_bytes):
    league = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    one = {"home": "A", "away": "B"}
    assert client.post(f"/api/admin/categories/{league['id']}/matches", json=one).status_code == 422
    assert client.post(f"/api/admin/categories/{torneo['id']}/matches", json={**one, "date": "2026-12-19"}).status_code == 422  # falta la hora
    files = [("files", (RANKING_XLS.name, ranking_bytes, "application/vnd.ms-excel"))]
    r = client.post("/api/admin/upload", files=files, data={"category_id": torneo["id"]}).json()["results"][0]
    assert r["status"] == "error" and "torneo" in r["message"]


def test_migration_adds_kind_column(client):
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE categories DROP COLUMN kind")
    init_db()
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(categories)")}
    assert "kind" in cols
