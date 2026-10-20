"""Horarios cambiados a mano por el admin: mandan siempre sobre el Excel."""
import pytest
from sqlalchemy import select

from conftest import CALENDAR_J1_XLS, CALENDAR_XLS, RANKING_J1_XLS, RANKING_XLS
from app.db import SessionLocal, engine, init_db
from app.models import Match, SyncLog

OURS = "CDF Voleibol Ancares UVa"


def upload(client, cat_id, *paths):
    files = [("files", (p.name, p.read_bytes(), "application/vnd.ms-excel")) for p in paths]
    r = client.post("/api/admin/upload", files=files, data={"category_id": cat_id})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def cat(client):
    client.post("/api/admin/login", json={"password": "secreto"})
    c = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    upload(client, c["id"], RANKING_XLS, CALENDAR_XLS)
    return c


def colon(client, cat):
    """Ancares – VCV Colón (jornada 1): en el Excel, dom 18/10/2026 10:30 en Fuente la Mora."""
    return next(m for m in client.get(f"/api/admin/categories/{cat['id']}/schedule").json() if m["away"] == "VCV Colón")


def public(client, cat):
    d = client.get(f"/api/categories/{cat['slug']}").json()
    return next(m for m in d["matches"] if m["home"] == OURS and m["away"] == "VCV Colón")


def test_admin_changes_schedule_and_it_survives_imports(client, cat):
    m = colon(client, cat)
    assert (m["date"], m["time"], m["venue"], m["override"]) == ("2026-10-18", "10:30", "Fuente la Mora", False)

    r = client.put(f"/api/admin/matches/{m['id']}/schedule", json={"date": "2026-10-18", "time": "12:15", "venue": "Pabellón Pisuerga"})
    assert r.status_code == 200, r.text
    changed = r.json()
    assert (changed["time"], changed["venue"], changed["override"]) == ("12:15", "Pabellón Pisuerga", True)
    assert changed["excel"] == {"date": "2026-10-18", "time": "10:30", "venue": "Fuente la Mora"}
    p = public(client, cat)
    assert p["starts_at"] == "2026-10-18T10:15:00+00:00" and p["venue"] == "Pabellón Pisuerga" and p["schedule_override"]

    # Se vuelve a importar el mismo Excel: el horario del admin se mantiene y no hay «cambios» falsos
    report = upload(client, cat["id"], RANKING_XLS, CALENDAR_XLS)
    with SessionLocal() as s:
        last = s.scalars(select(SyncLog).where(SyncLog.kind == "calendar").order_by(SyncLog.id.desc())).first()
        assert last.status == "unchanged", (last.message, report)
    p = public(client, cat)
    assert p["starts_at"] == "2026-10-18T10:15:00+00:00" and p["venue"] == "Pabellón Pisuerga"

    # Llega un Excel distinto (con resultados): el horario del admin sigue mandando
    upload(client, cat["id"], RANKING_J1_XLS, CALENDAR_J1_XLS)
    p = public(client, cat)
    assert p["starts_at"] == "2026-10-18T10:15:00+00:00" and p["schedule_override"]

    # Volver al del Excel
    back = client.delete(f"/api/admin/matches/{colon(client, cat)['id']}/schedule").json()
    assert (back["time"], back["venue"], back["override"]) == ("10:30", "Fuente la Mora", False)
    assert public(client, cat)["schedule_override"] is False
    upload(client, cat["id"], RANKING_J1_XLS, CALENDAR_J1_XLS)
    assert public(client, cat)["starts_at"] == "2026-10-18T08:30:00+00:00"


def test_only_time_or_only_venue(client, cat):
    m = colon(client, cat)
    # Solo el pabellón: la fecha y la hora siguen siendo las del Excel
    r = client.put(f"/api/admin/matches/{m['id']}/schedule", json={"venue": "Polideportivo Huerta del Rey"}).json()
    assert (r["date"], r["time"], r["venue"]) == ("2026-10-18", "10:30", "Polideportivo Huerta del Rey")
    # Solo la fecha y la hora: el pabellón vuelve a ser el del Excel
    r = client.put(f"/api/admin/matches/{m['id']}/schedule", json={"date": "2026-10-25", "time": "17:00", "venue": ""}).json()
    assert (r["date"], r["time"], r["venue"]) == ("2026-10-25", "17:00", "Fuente la Mora")


def test_excel_change_is_still_reported(client, cat):
    """Si la FVCL cambia el horario de un partido que el admin ya cambió, el registro lo cuenta."""
    m = colon(client, cat)
    client.put(f"/api/admin/matches/{m['id']}/schedule", json={"date": "2026-10-18", "time": "12:15"})
    with SessionLocal() as s:  # simula que lo que había en el Excel era otra hora
        row = s.get(Match, m["id"])
        row.excel_starts_at = row.excel_starts_at.replace(hour=7)
        s.commit()
    upload(client, cat["id"], RANKING_XLS, CALENDAR_XLS)
    with SessionLocal() as s:
        last = s.scalars(select(SyncLog).where(SyncLog.kind == "calendar").order_by(SyncLog.id.desc())).first()
        assert last.status == "ok" and "horario" in last.message
    assert public(client, cat)["starts_at"] == "2026-10-18T10:15:00+00:00"  # manda el admin


def test_validation(client, cat):
    m = colon(client, cat)
    assert client.put(f"/api/admin/matches/{m['id']}/schedule", json={"date": "2026-10-18"}).status_code == 422
    assert client.put(f"/api/admin/matches/{m['id']}/schedule", json={"time": "10:00"}).status_code == 422
    assert client.put(f"/api/admin/matches/{m['id']}/schedule", json={}).status_code == 422
    assert client.put("/api/admin/matches/999999/schedule", json={"venue": "X"}).status_code == 404
    t = client.post("/api/admin/categories", json={"name": "Torneo", "kind": "tournament"}).json()
    assert client.get(f"/api/admin/categories/{t['id']}/schedule").status_code == 422
    client.cookies.clear()
    assert client.put(f"/api/admin/matches/{m['id']}/schedule", json={"venue": "X"}).status_code == 401


def test_migration_adds_match_columns():
    with engine.begin() as conn:
        for col in ("excel_starts_at", "excel_venue", "schedule_override"):
            conn.exec_driver_sql(f"ALTER TABLE matches DROP COLUMN {col}")
    init_db()
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(matches)")}
    assert {"excel_starts_at", "excel_venue", "schedule_override"} <= cols
