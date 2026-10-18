from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from conftest import CALENDAR_XLS, RANKING_XLS, clear_ours_dates_except
from app.db import SessionLocal, engine, init_db
from app.models import Category, Match
from app.scoring_format import ResultError, format_of, validate_partials
from app.services.provisional import drop_superseded

OURS = "CDF Voleibol Ancares UVa"


# --- validación de parciales ------------------------------------------------------

def test_validate_partials_ok():
    assert validate_partials([[25, 20], [23, 25, True], [25, 18, True]], 2, 1, False) == [
        [25, 20, True], [23, 25, True], [25, 18, True]
    ]
    # Terminado antes de tiempo: el último set puede quedar a medias y no cuenta
    assert validate_partials([[25, 20, True], [12, 8, False]], 1, 0, True)[-1] == [12, 8, False]


@pytest.mark.parametrize(
    "partials,home,away,early",
    [
        ([[25, 24, True]], 1, 0, False),  # sin 2 de diferencia
        ([[25, 20, True]], 0, 1, False),  # los sets no cuadran
        ([[12, 8, False]], 0, 0, False),  # set a medias sin terminar el partido
        ([[12, 8, False], [25, 20, True]], 1, 0, True),  # solo el último puede quedar a medias
        ([[0, 0, False]], 0, 0, True),  # marcador a cero
        ([[25, 120, True]], 0, 1, False),  # fuera de rango
        ([], 0, 0, False),
    ],
)
def test_validate_partials_rejects(partials, home, away, early):
    with pytest.raises(ResultError):
        validate_partials(partials, home, away, early)


def test_format_of_defaults():
    assert format_of(None) == {"mode": "best_of", "sets": 5, "points": 25, "tiebreak": 15}
    assert format_of({"mode": "fixed", "sets": 3, "points": 25, "tiebreak": None})["mode"] == "fixed"
    assert format_of({"sets": 99})["sets"] == 5  # inválido -> por defecto


# --- flujo completo -------------------------------------------------------------------

@pytest.fixture()
def league(client, ranking_bytes, calendar_bytes):
    """Categoría con datos reales y el primer partido de Ancares movido a 'hace una hora'."""
    assert client.post("/api/admin/login", json={"password": "secreto"}).status_code == 200
    fmt = {"mode": "best_of", "sets": 3, "points": 25, "tiebreak": 15}
    cat = client.post("/api/admin/categories", json={"name": "Infantil", "score_format": fmt}).json()
    files = [
        ("files", (RANKING_XLS.name, ranking_bytes, "application/vnd.ms-excel")),
        ("files", (CALENDAR_XLS.name, calendar_bytes, "application/vnd.ms-excel")),
    ]
    client.post("/api/admin/upload", files=files, data={"category_id": cat["id"]})
    clear_ours_dates_except("VCV Castilla")
    with SessionLocal() as s:
        m = s.scalars(select(Match).where(Match.home == OURS, Match.away == "VCV Castilla")).first()
        m.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
        s.commit()
        match = {"category_id": cat["id"], "round_no": m.round_no, "home": m.home, "away": m.away}
    return cat, match


def result(match, **kw):
    body = dict(match, home_sets=2, away_sets=1, partials=[[25, 20, True], [23, 25, True], [25, 18, True]])
    body.update(kw)
    return body


def make_scorer(client, name="Ana"):
    r = client.post("/api/admin/scorers", json={"name": name})
    assert r.status_code == 201
    return r.json()


def test_scorer_code_flow(client, league):
    cat, match = league
    created = make_scorer(client)
    code = created["code"]
    assert len(code) == 9 and code[4] == "-"
    assert "code" not in client.get("/api/admin/scorers").json()[0]  # no se vuelve a mostrar

    client.cookies.clear()  # una familia cualquiera, sin sesión
    assert client.get("/api/scorer/me").json()["can_publish"] is False
    assert client.post("/api/scoring/results", json=result(match)).status_code == 401
    assert client.post("/api/scorer/join", json={"code": "XXXX-XXXX"}).status_code == 401

    # El código se acepta en minúsculas y sin guion
    r = client.post("/api/scorer/join", json={"code": code.lower().replace("-", "")})
    assert r.status_code == 200 and r.json()["name"] == "Ana"
    assert client.get("/api/scorer/me").json() == {"scorer": True, "name": "Ana", "admin": False, "can_publish": True}

    r = client.post("/api/scoring/results", json=result(match))
    assert r.status_code == 200, r.text
    assert r.json()["provisional"]["by"] == "Ana"

    # Revocar desde el admin corta la publicación al instante
    scorer_cookie = client.cookies.get("ancares_scorer")
    client.post("/api/admin/login", json={"password": "secreto"})
    client.post(f"/api/admin/scorers/{created['id']}/revoke")
    client.cookies.clear()
    client.cookies.set("ancares_scorer", scorer_cookie)
    assert client.get("/api/scorer/me").json()["scorer"] is False
    assert client.post("/api/scoring/results", json=result(match)).status_code == 401


def test_provisional_shown_until_official(client, league):
    cat, match = league
    assert client.post("/api/scoring/results", json=result(match)).status_code == 200  # como admin

    detail = client.get(f"/api/categories/{cat['slug']}").json()
    m = next(x for x in detail["matches"] if x["home"] == OURS and x["away"] == "VCV Castilla")
    assert m["played"] is False and m["provisional"]["home_sets"] == 2 and m["provisional"]["by"] == "Admin"
    assert detail["last_result"]["provisional"] is not None
    assert detail["next_match"]["away"] != "VCV Castilla"  # ya no es el próximo
    assert client.get("/api/home").json()["categories"][0]["last_result"]["provisional"]

    # Republicar sobrescribe
    client.post("/api/scoring/results", json=result(match, home_sets=2, away_sets=0, partials=[[25, 10], [25, 12]]))
    assert len(client.get("/api/admin/provisional").json()) == 1

    # Llega el oficial: el provisional deja de mostrarse, la importación lo borra y no se puede republicar
    with SessionLocal() as s:
        mm = s.scalars(select(Match).where(Match.home == OURS, Match.away == "VCV Castilla")).first()
        mm.home_sets, mm.away_sets = 3, 1
        s.commit()
        m = next(x for x in client.get(f"/api/categories/{cat['slug']}").json()["matches"] if x["id"] == mm.id)
        assert m["played"] and m["provisional"] is None
        assert client.post("/api/scoring/results", json=result(match)).status_code == 409
        assert drop_superseded(s, s.get(Category, cat["id"])) == 1
        s.commit()
    assert client.get("/api/admin/provisional").json() == []


def test_publish_validation(client, league):
    cat, match = league
    bad = client.post("/api/scoring/results", json=result(match, home_sets=3))
    assert bad.status_code == 422 and "no cuadran" in bad.json()["detail"]
    other = dict(match, home="VCV Castilla", away="Sporting Santo Domingo A", round_no=2)
    assert client.post("/api/scoring/results", json=result(other)).status_code == 422  # no es de Ancares
    missing = dict(match, round_no=99)
    assert client.post("/api/scoring/results", json=result(missing)).status_code == 404


def test_scoring_matches_suggests_nearest(client, league):
    cat, match = league
    items = client.get("/api/scoring/matches").json()
    assert items and items[0]["away"] == "VCV Castilla"
    assert -70 <= items[0]["minutes_from_now"] <= -50
    assert items[0]["score_format"]["sets"] == 3 and items[0]["category_slug"] == cat["slug"]


def test_admin_can_score_matches_out_of_date(client, league):
    """A veces se juega otro día u otra hora: el admin ve todos los partidos sin resultado."""
    cat, match = league
    items = client.get("/api/scoring/matches").json()  # como admin
    assert items[0]["in_window"] and items[0]["away"] == "VCV Castilla"
    later = [i for i in items if not i["in_window"]]
    assert later and all(not i["played"] for i in later)
    assert any(i["minutes_from_now"] is None for i in later)  # también los que aún no tienen fecha
    assert items[-1]["minutes_from_now"] is None  # los sin fecha, al final

    # Un anotador solo ve los de estos días
    code = make_scorer(client)["code"]
    client.cookies.clear()
    client.post("/api/scorer/join", json={"code": code})
    assert all(i["in_window"] for i in client.get("/api/scoring/matches").json())


def test_admin_scorer_management(client, league):
    s = make_scorer(client, "Luis")
    regen = client.post(f"/api/admin/scorers/{s['id']}/regenerate").json()
    assert regen["code"] != s["code"]
    client.cookies.clear()
    assert client.post("/api/scorer/join", json={"code": s["code"]}).status_code == 401  # el viejo ya no vale
    assert client.post("/api/scorer/join", json={"code": regen["code"]}).status_code == 200


def test_migration_adds_score_format_column():
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE categories DROP COLUMN score_format")
    init_db()
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(categories)")}
    assert "score_format" in cols


def test_first_result_wins(client, league):
    cat, match = league
    ana, luis = make_scorer(client, "Ana"), make_scorer(client, "Luis")

    def as_scorer(code):
        client.cookies.clear()
        assert client.post("/api/scorer/join", json={"code": code}).status_code == 200

    # Ana publica primero
    as_scorer(ana["code"])
    assert client.post("/api/scoring/results", json=result(match)).status_code == 200

    # Luis no puede pisarla, y el marcador ya no le ofrece publicar ese partido
    as_scorer(luis["code"])
    item = next(i for i in client.get("/api/scoring/matches").json() if i["away"] == "VCV Castilla")
    assert item["provisional"]["by"] == "Ana" and item["can_publish"] is False
    r = client.post("/api/scoring/results", json=result(match, home_sets=0, away_sets=2, partials=[[10, 25], [10, 25]]))
    assert r.status_code == 409 and "publicado por Ana" in r.json()["detail"]

    # Ana sí puede corregir su propio resultado
    as_scorer(ana["code"])
    assert next(i for i in client.get("/api/scoring/matches").json() if i["away"] == "VCV Castilla")["can_publish"]
    fixed = result(match, home_sets=2, away_sets=0, partials=[[25, 20], [25, 18]])
    assert client.post("/api/scoring/results", json=fixed).status_code == 200

    # El admin siempre puede sustituirlo
    client.cookies.clear()
    client.post("/api/admin/login", json={"password": "secreto"})
    r = client.post("/api/scoring/results", json=result(match))
    assert r.status_code == 200 and r.json()["provisional"]["by"] == "Admin"
    provisional = client.get("/api/admin/provisional").json()
    assert len(provisional) == 1 and provisional[0]["home_sets"] == 2 and provisional[0]["away_sets"] == 1

    # Sin código no se puede publicar nada
    client.cookies.clear()
    assert next(i for i in client.get("/api/scoring/matches").json() if i["away"] == "VCV Castilla")["can_publish"] is False
