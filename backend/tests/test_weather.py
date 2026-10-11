from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from conftest import CALENDAR_XLS, RANKING_XLS
from app.db import SessionLocal
from app.models import Match
from app.services import weather
from app.services.weather import forecast_for, locate

NOW = datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "venue,home,city",
    [
        ("Fuente la Mora", "CDF Voleibol Ancares UVa", "Valladolid"),
        ("P. Pajaritos Norte", "Sporting Santo Domingo A", "Soria"),  # pabellón conocido
        ("Marista Liceo Castilla Burgos", "Maristas Burgos A", "Burgos"),
        ("Pabellón José Arroyo, Ponferrada", "x", "Ponferrada"),
        (None, "Rio Duero Soria A", "Soria"),  # por el equipo local
        ("Polideportivo desconocido", "Equipo X", "Valladolid"),  # ciudad por defecto
    ],
)
def test_locate(venue, home, city):
    assert locate(venue, home).name == city


@pytest.fixture()
def open_meteo(monkeypatch):
    """Open-Meteo simulado: previsión horaria de 16 días desde NOW."""
    calls = []
    start = NOW.replace(minute=0)
    times = [(start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:00") for h in range(16 * 24)]

    hours = [int(t[11:13]) for t in times]  # hora del día (UTC) de cada dato

    def handler(request):
        calls.append(request)
        n = len(times)
        return httpx.Response(200, json={"hourly": {
            "time": times,
            "temperature_2m": [round(10 + h / 2, 1) for h in hours],
            "precipitation_probability": [h * 4 for h in hours],
            "weather_code": [61] * n,
            "wind_speed_10m": [12.5] * n,
            "is_day": [1 if 7 <= h <= 18 else 0 for h in hours],
        }})

    real = httpx.Client
    monkeypatch.setattr(weather.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    weather._forecast_cache.clear()
    return calls


def test_forecast_picks_match_hour(open_meteo):
    starts = NOW + timedelta(days=2, hours=5, minutes=40)  # 15:40 UTC -> hora más cercana 16:00
    f = forecast_for(starts, "Fuente la Mora", "Ancares", now=NOW)
    assert f["available"] and f["place"] == "Valladolid"
    assert f["time"] == "2026-10-13T16:00Z"
    assert f["temperature"] == 18.0 and f["weather_code"] == 61 and f["is_day"] is True
    forecast_for(starts, "Fuente la Mora", "Ancares", now=NOW)
    assert len(open_meteo) == 1  # la segunda vez sale de la caché


def test_forecast_unavailable(open_meteo):
    far = forecast_for(NOW + timedelta(days=30), "Fuente la Mora", "x", now=NOW)
    assert far["available"] is False and far["reason"] == "too_far" and far["available_from"] == "2026-10-26"
    assert forecast_for(NOW - timedelta(days=1), "Fuente la Mora", "x", now=NOW)["reason"] == "past"
    assert not open_meteo  # sin pedir nada a Open-Meteo


def test_forecast_network_error(monkeypatch):
    real = httpx.Client
    monkeypatch.setattr(weather.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(lambda r: httpx.Response(500)), **kw))
    weather._forecast_cache.clear()
    f = forecast_for(datetime.now(timezone.utc) + timedelta(days=1), "Fuente la Mora", "x")
    assert f == {"available": False, "place": "Valladolid", "reason": "error"}


def test_weather_endpoint_and_after_match(client, ranking_bytes, calendar_bytes, monkeypatch):
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    files = [("files", (RANKING_XLS.name, ranking_bytes, "application/vnd.ms-excel")),
             ("files", (CALENDAR_XLS.name, calendar_bytes, "application/vnd.ms-excel"))]
    client.post("/api/admin/upload", files=files, data={"category_id": cat["id"]})

    detail = client.get("/api/categories/infantil").json()
    nxt, after = detail["next_match"], detail["after_match"]
    assert nxt and after and nxt["id"] != after["id"]
    assert after["starts_at"] >= nxt["starts_at"]

    seen = {}
    monkeypatch.setattr("app.routers.public.forecast_for",
                        lambda starts, venue, home: seen.update(venue=venue, home=home) or {"available": True, "place": "Valladolid"})
    r = client.get(f"/api/weather/{nxt['id']}")
    assert r.status_code == 200 and r.json()["available"] and "max-age" in r.headers["cache-control"]
    assert seen == {"venue": nxt["venue"], "home": nxt["home"]}

    with SessionLocal() as s:
        undated = s.scalars(select(Match).where(Match.starts_at.is_(None), Match.is_bye.is_(False))).first()
        assert client.get(f"/api/weather/{undated.id}").json()["reason"] == "no_date"
    assert client.get("/api/weather/999999").status_code == 404
