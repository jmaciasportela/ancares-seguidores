"""Llegan los resultados oficiales de la FVCL: el provisional deja de contar."""
from conftest import CALENDAR_J1_XLS, CALENDAR_XLS, RANKING_J1_XLS, RANKING_XLS
from app.db import SessionLocal
from app.models import Category
from app.services import stats

OURS = "CDF Voleibol Ancares UVa"


def upload(client, cat_id, *paths):
    files = [("files", (p.name, p.read_bytes(), "application/vnd.ms-excel")) for p in paths]
    r = client.post("/api/admin/upload", files=files, data={"category_id": cat_id})
    assert r.status_code == 200, r.text


def provisional(client, cat, **kw):
    """Resultado provisional (como admin) del Ancares – VCV Castilla de la jornada 1."""
    body = {"category_id": cat["id"], "round_no": 1, "home": OURS, "away": "VCV Castilla",
            "home_sets": 1, "away_sets": 3, "partials": [[14, 25], [11, 25], [25, 18], [12, 25]]}
    body.update(kw)
    r = client.post("/api/scoring/results", json=body)
    assert r.status_code == 200, r.text


def ancares_castilla(client, slug):
    d = client.get(f"/api/categories/{slug}").json()
    return d, next(m for m in d["matches"] if m["home"] == OURS and m["away"] == "VCV Castilla")


def test_official_result_replaces_provisional(client):
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    upload(client, cat["id"], RANKING_XLS, CALENDAR_XLS)
    provisional(client, cat)
    _, m = ancares_castilla(client, cat["slug"])
    assert not m["played"] and m["provisional"]["away_sets"] == 3
    assert client.get(f"/api/categories/{cat['slug']}/stats").json()["provisional_table"]

    # La FVCL publica la jornada 1: el oficial manda y el provisional desaparece
    upload(client, cat["id"], RANKING_J1_XLS, CALENDAR_J1_XLS)
    detail, m = ancares_castilla(client, cat["slug"])
    assert m["played"] and (m["home_sets"], m["away_sets"]) == (1, 3) and m["provisional"] is None
    assert client.get("/api/admin/provisional").json() == []
    st = client.get(f"/api/categories/{cat['slug']}/stats").json()
    assert st["provisional_table"] is None
    ours = next(s for s in detail["standings"] if s["is_ours"])
    assert (ours["points"], ours["played"]) == (1, 1)


def test_ranking_ahead_of_calendar_is_not_counted_twice(client):
    """La clasificación ya cuenta el partido pero el calendario aún no trae el resultado."""
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    upload(client, cat["id"], RANKING_J1_XLS, CALENDAR_XLS)
    provisional(client, cat)
    _, m = ancares_castilla(client, cat["slug"])
    assert m["provisional"]  # se sigue viendo como provisional en resultados...
    # ...pero no se suma otra vez a una tabla que ya lo cuenta
    assert client.get(f"/api/categories/{cat['slug']}/stats").json()["provisional_table"] is None


def test_points_rule_is_deduced_from_official_table(client):
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    upload(client, cat["id"], RANKING_J1_XLS, CALENDAR_J1_XLS)
    with SessionLocal() as s:
        c = s.get(Category, cat["id"])
        rule = stats.points_rule(c)
        # Infantil: 2 por ganar y 1 por perder (Castilla ganó 3-1 y suma 2; Ancares perdió 1-3 y suma 1)
        assert (rule(3, 1), rule(1, 3), rule(3, 0), rule(0, 3)) == (2, 1, 2, 1)
        # Con esa regla, la evolución reconstruida cuadra con la tabla oficial
        assert stats.evolution(c, None)["approximate"] is False


def test_table_behind_calendar_is_updated_with_official_results(client):
    """La web de la FVCL no actualiza su clasificación, pero el calendario ya trae los resultados oficiales."""
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    upload(client, cat["id"], RANKING_XLS, CALENDAR_J1_XLS)  # clasificación vieja (a cero) + calendario con la jornada 1
    detail = client.get(f"/api/categories/{cat['slug']}").json()
    assert detail["standings_missing"] == {"results": 2, "rounds": ["Jornada 1"]}
    calc = {r["team"]: (r["points"], r["played"], r["won"], r["lost"], r["sets_for"], r["sets_against"]) for r in detail["standings_updated"]}

    # Es exactamente lo que publica luego la federación
    upload(client, cat["id"], RANKING_J1_XLS)
    after = client.get(f"/api/categories/{cat['slug']}").json()
    assert after["standings_updated"] is None and after["standings_missing"] is None
    official = {s["team"]: (s["points"], s["played"], s["won"], s["lost"], s["sets_for"], s["sets_against"]) for s in after["standings"]}
    assert calc == official
    assert [r["team"] for r in detail["standings_updated"]][:2] == ["Maristas Inmaculada A", "VCV Castilla"]

    # La portada ya usaba la posición actualizada de Ancares
    assert detail["our_position"] == next(r["position"] for r in detail["standings_updated"] if r["is_ours"])
