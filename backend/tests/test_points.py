"""Puntuación de las ligas según la normativa de la FVCL (Normas Generales de Voleibol 2026-27)."""
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from conftest import CALENDAR_J1_XLS, CALENDAR_XLS, RANKING_J1_XLS, RANKING_XLS
from app.db import SessionLocal, engine, init_db
from app.models import Category, Match, Standing
from app.services import stats


@pytest.mark.parametrize("name,expected", [
    ("Infantil Femenino", "2-1-0"), ("Cadete Masculino", "2-1-0"), ("CRE Alevín", "2-1-0"), ("Benjamín", "2-1-0"),
    ("Juvenil Femenino", "3-2-1-0"), ("Júnior", "3-2-1-0"), ("Sénior 2ª División", "3-2-1-0"), ("Liga Oro", "3-2-1-0"),
])
def test_default_by_category(name, expected):
    assert stats.default_points_system(name) == expected


def test_rules():
    two, three = stats.RULES["2-1-0"], stats.RULES["3-2-1-0"]
    assert [two(3, 0), two(3, 2), two(2, 3), two(0, 3)] == [2, 2, 1, 1]
    assert [three(3, 0), three(3, 1), three(3, 2), three(2, 3), three(1, 3)] == [3, 3, 2, 1, 0]


def upload(client, name, *paths):
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": name}).json()
    files = [("files", (p.name, p.read_bytes(), "application/vnd.ms-excel")) for p in paths]
    assert client.post("/api/admin/upload", files=files, data={"category_id": cat["id"]}).status_code == 200
    return cat


def applied(client, slug):
    return client.get(f"/api/categories/{slug}").json()["points_system"]


def test_without_results_uses_the_rules(client):
    cadete = upload(client, "Cadete Femenino", RANKING_XLS, CALENDAR_XLS)
    assert applied(client, cadete["slug"]) == {
        "id": "2-1-0", "label": "2 por partido ganado y 1 por perdido", "source": "rules", "source_label": "normativa FVCL",
    }
    juvenil = upload(client, "Juvenil Femenino", RANKING_XLS, CALENDAR_XLS)
    assert applied(client, juvenil["slug"])["id"] == "3-2-1-0"


def test_official_table_confirms_or_overrides(client):
    # Real: jornada 1 de Infantil. Aunque la categoría se llamara «Juvenil», la tabla oficial manda
    cat = upload(client, "Juvenil (mal nombrada)", RANKING_J1_XLS, CALENDAR_J1_XLS)
    ps = applied(client, cat["slug"])
    assert (ps["id"], ps["source"]) == ("2-1-0", "official")
    with SessionLocal() as s:
        assert stats.evolution(s.get(Category, cat["id"]), None)["approximate"] is False


def test_ambiguous_results_keep_the_rules(client):
    """Si solo hay partidos 3-2, las dos reglas dan lo mismo: manda la normativa."""
    cat = upload(client, "Infantil", RANKING_XLS, CALENDAR_XLS)
    with SessionLocal() as s:
        m = s.scalars(select(Match).where(Match.category_id == cat["id"], Match.is_bye.is_(False))).first()
        m.home_sets, m.away_sets, m.partials = 3, 2, [[25, 20], [20, 25], [25, 20], [20, 25], [15, 10]]
        for st in s.scalars(select(Standing).where(Standing.team.in_([m.home, m.away]))):
            st.played, st.points = 1, 2 if st.team == m.home else 1
        s.commit()
        assert stats.deduce_points_system(s.get(Category, cat["id"])) is None
    assert applied(client, cat["slug"])["source"] == "rules"


def test_admin_choice_wins(client):
    cat = upload(client, "Infantil", RANKING_J1_XLS, CALENDAR_J1_XLS)
    body = {"name": "Infantil", "points_system": "3-2-1-0"}
    assert client.put(f"/api/admin/categories/{cat['id']}", json=body).status_code == 200
    ps = applied(client, cat["slug"])
    assert (ps["id"], ps["source"]) == ("3-2-1-0", "admin")
    admin = next(c for c in client.get("/api/admin/categories").json() if c["id"] == cat["id"])
    assert admin["points_system"] == "3-2-1-0" and admin["points_applied"]["id"] == "3-2-1-0"
    assert client.put(f"/api/admin/categories/{cat['id']}", json={"name": "Infantil", "points_system": "4-0"}).status_code == 422


def test_tournament_groups_use_category_rules():
    """Un torneo no tiene tabla oficial: vale la normativa según su nombre."""
    from app.services.tournament import group_tables

    def match(home, away, hs, as_, order):
        return SimpleNamespace(round_name="Grupo A", round_no=1, order=order, home=home, away=away, is_bye=False,
                               home_sets=hs, away_sets=as_, partials=[], starts_at=None)

    cat = SimpleNamespace(name="Torneo Infantil", points_system="auto", standings=[], matches=[
        match("A", "B", 3, 0, 1), match("B", "C", 3, 1, 2), match("C", "A", 0, 3, 3),
    ])
    table = group_tables(cat, lambda m: None, lambda name: None)[0]["standings"]
    assert {r["team"]: r["points"] for r in table} == {"A": 4, "B": 3, "C": 2}


def test_migration_adds_points_system_column():
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE categories DROP COLUMN points_system")
    init_db()
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(categories)")}
    assert "points_system" in cols
