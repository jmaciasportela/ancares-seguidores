import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from conftest import CALENDAR_XLS, RANKING_XLS
from app.db import SessionLocal
from app.models import Match
from app.services import cheers

OURS = "CDF Voleibol Ancares UVa"
DEV = str(uuid.UUID(int=7))


@pytest.fixture()
def league(client, ranking_bytes, calendar_bytes):
    cheers._per_device.clear()
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    files = [("files", (RANKING_XLS.name, ranking_bytes, "application/vnd.ms-excel")),
             ("files", (CALENDAR_XLS.name, calendar_bytes, "application/vnd.ms-excel"))]
    client.post("/api/admin/upload", files=files, data={"category_id": cat["id"]})
    client.cookies.clear()  # los ánimos son de cualquiera, sin sesión
    return cat


def set_start(home, away, delta):
    with SessionLocal() as s:
        m = s.scalars(select(Match).where(Match.home == home, Match.away == away)).first()
        m.starts_at = datetime.now(timezone.utc) + delta
        s.commit()
        return {"category_id": m.category_id, "round_no": m.round_no, "home": m.home, "away": m.away}


def test_cheer_window_and_totals(client, league):
    match = set_start(OURS, "VCV Castilla", timedelta(hours=2))  # hoy, en 2 horas
    r = client.post("/api/cheers", json={**match, "kind": "vamos", "n": 3, "device": DEV})
    assert r.status_code == 200 and r.json() == {"total": 3, "by_kind": {"vamos": 3}, "open": True}
    client.post("/api/cheers", json={**match, "kind": "defensa", "n": 2, "device": DEV})

    home = client.get("/api/home").json()["categories"][0]["next_match"]
    assert home["away"] == "VCV Castilla" and home["cheers"] == {"total": 5, "by_kind": {"vamos": 3, "defensa": 2}, "open": True}
    detail = client.get("/api/categories/infantil").json()
    m = next(x for x in detail["matches"] if x["home"] == OURS and x["away"] == "VCV Castilla")
    assert m["cheers"]["total"] == 5

    # Fuera de la ventana (dentro de 3 días): todavía cerrado
    later = set_start(OURS, "VCV Colón", timedelta(days=3))
    r = client.post("/api/cheers", json={**later, "kind": "vamos", "device": DEV})
    assert r.status_code == 409 and "día del partido" in r.json()["detail"]


def test_cheer_validation_and_limits(client, league):
    match = set_start(OURS, "VCV Castilla", timedelta(hours=1))
    assert client.post("/api/cheers", json={**match, "kind": "insulto", "device": DEV}).status_code == 422
    rival = set_start("VCV Castilla", "C.D. San José", timedelta(hours=1))
    assert client.post("/api/cheers", json={**rival, "kind": "vamos", "device": DEV}).status_code == 422
    assert client.post("/api/cheers", json={**match, "kind": "vamos", "device": "x"}).status_code == 422

    # 25 por envío como mucho
    assert client.post("/api/cheers", json={**match, "kind": "vamos", "n": 999, "device": DEV}).json()["total"] == 25
    # 300 por móvil, partido y día: el resto se ignora sin error
    for _ in range(20):
        client.post("/api/cheers", json={**match, "kind": "vamos", "n": 25, "device": DEV})
    r = client.post("/api/cheers", json={**match, "kind": "vamos", "n": 25, "device": DEV})
    assert r.status_code == 200 and r.json()["total"] == 300
    other = str(uuid.UUID(int=8))
    assert client.post("/api/cheers", json={**match, "kind": "vamos", "n": 1, "device": other}).json()["total"] == 301


def test_cheers_survive_calendar_reimport(client, league, calendar_bytes):
    match = set_start(OURS, "VCV Castilla", timedelta(hours=1))
    client.post("/api/cheers", json={**match, "kind": "saque", "n": 4, "device": DEV})
    client.post("/api/admin/login", json={"password": "secreto"})
    files = [("files", (CALENDAR_XLS.name, calendar_bytes, "application/vnd.ms-excel"))]
    client.post("/api/admin/upload", files=files, data={"category_id": league["id"]})  # ids nuevos
    detail = client.get("/api/categories/infantil").json()
    m = next(x for x in detail["matches"] if x["home"] == OURS and x["away"] == "VCV Castilla")
    assert m["cheers"]["by_kind"] == {"saque": 4}
