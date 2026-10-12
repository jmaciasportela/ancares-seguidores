import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Device, DeviceDay
from app.services import usage

NOW = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)
A, B, C = (str(uuid.UUID(int=i)) for i in (1, 2, 3))


def ping(session, dev, when, installed=True, platform="android", version="1.0.6"):
    return usage.record_ping(session, dev, installed, platform, version, now=when)


def test_visits_and_days(client):
    with SessionLocal() as s:
        d = ping(s, A, NOW)
        ping(s, A, NOW + timedelta(minutes=10))  # misma visita
        ping(s, A, NOW + timedelta(hours=2))  # visita nueva, mismo día
        ping(s, A, NOW + timedelta(days=1))  # otro día
        d = s.get(Device, d.id)
        assert d.visits == 3  # la primera, a las 2 h y al día siguiente
        assert len(s.scalars(select(DeviceDay).where(DeviceDay.device_id == d.id)).all()) == 2
        assert d.key != A and len(d.key) == 64  # solo se guarda el hash


def test_summary(client):
    with SessionLocal() as s:
        # A: instalada, entra 10 días seguidos. B: navegador iOS, 2 días. C: hace 40 días (fuera del mes)
        for i in range(10):
            ping(s, A, NOW - timedelta(days=i))
        ping(s, B, NOW - timedelta(days=3), installed=False, platform="ios", version="1.0.5")
        ping(s, B, NOW, installed=False, platform="ios", version="1.0.5")
        ping(s, C, NOW - timedelta(days=40), platform="desktop")
        data = usage.summary(s, now=NOW)

    assert (data["active_today"], data["active_7d"], data["active_30d"]) == (2, 2, 2)
    assert data["installed_30d"] == 1 and data["installed_7d"] == 1
    assert data["total_devices"] == 3
    assert data["platforms"] == {"android": 1, "ios": 1}
    assert data["versions"] == {"1.0.6": 1, "1.0.5": 1}
    freq = {f["label"]: f["devices"] for f in data["frequency"]}
    assert freq["8–14 días"] == 1 and freq["2–3 días"] == 1
    assert data["days_per_week"] == round((10 + 2) / 2 * 7 / 30, 1)
    assert len(data["daily"]) == 30 and data["daily"][-1] == {"day": "2026-10-12", "devices": 2}


def test_purge(client):
    with SessionLocal() as s:
        ping(s, A, NOW - timedelta(days=200))
        ping(s, B, NOW)
        assert usage.purge_old(s, now=NOW) == 1
        assert s.scalars(select(Device)).all()[0].key == usage.device_key(B)


def test_ping_endpoint_and_admin(client):
    assert client.post("/api/ping", json={"device": "no-es-uuid"}).status_code == 422
    r = client.post("/api/ping", json={"device": A, "installed": True, "platform": "ios", "version": "1.0.6"})
    assert r.status_code == 204
    client.post("/api/ping", json={"device": B, "platform": "nevera"})  # plataforma desconocida -> "otro"

    assert client.get("/api/admin/usage").status_code == 401
    client.post("/api/admin/login", json={"password": "secreto"})
    data = client.get("/api/admin/usage").json()
    assert data["active_today"] == 2 and data["installed_30d"] == 1
    assert data["platforms"] == {"ios": 1, "otro": 1}
