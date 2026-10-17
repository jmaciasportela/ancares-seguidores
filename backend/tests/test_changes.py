from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from conftest import CALENDAR_XLS, RANKING_XLS
from app.db import SessionLocal
from app.models import Category, Match, Standing, SyncLog
from app.parsers.calendar import MatchRow
from app.services import fetcher
from app.services.changes import diff_calendar, summary
from app.services.importer import import_file, is_ours
from app.services.sync import sync_categories

OURS = "CDF Voleibol Ancares UVa"


def upload(client, data, name, cat_id):
    files = [("files", (name, data, "application/vnd.ms-excel"))]
    return client.post("/api/admin/upload", files=files, data={"category_id": cat_id}).json()["results"][0]


def make_league(client, ranking_bytes, calendar_bytes):
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil"}).json()
    first_cal = upload(client, calendar_bytes, CALENDAR_XLS.name, cat["id"])  # antes que la clasificación
    first_rank = upload(client, ranking_bytes, RANKING_XLS.name, cat["id"])
    return cat, first_cal, first_rank


def test_first_import_reports_news(client, ranking_bytes, calendar_bytes):
    cat, cal, rank = make_league(client, ranking_bytes, calendar_bytes)
    assert cal == {**cal, "status": "ok", "message": "Primera carga: 123 partidos"}
    assert rank["status"] == "ok" and rank["message"] == "Primera carga: 10 equipos"


def test_same_data_is_not_news(client, ranking_bytes, calendar_bytes):
    cat, *_ = make_league(client, ranking_bytes, calendar_bytes)
    with SessionLocal() as s:
        c = s.get(Category, cat["id"])
        # Como tras desplegar: huellas antiguas (de bytes) que ya no coinciden
        c.calendar_hash = c.ranking_hash = "hash-antiguo-de-bytes"
        updated = c.data_updated_at
        ids = sorted(m.id for m in c.matches)
        s.commit()
    assert upload(client, calendar_bytes, CALENDAR_XLS.name, cat["id"])["status"] == "unchanged"
    assert upload(client, ranking_bytes, RANKING_XLS.name, cat["id"])["message"] == "Sin cambios"
    with SessionLocal() as s:
        c = s.get(Category, cat["id"])
        assert c.data_updated_at == updated  # «actualizado hace…» no se mueve
        assert sorted(m.id for m in c.matches) == ids  # no se reescribe nada
        assert c.last_sync_at >= updated


def test_schedule_and_ranking_changes(client, ranking_bytes, calendar_bytes):
    cat, *_ = make_league(client, ranking_bytes, calendar_bytes)
    with SessionLocal() as s:
        m = s.scalars(select(Match).where(Match.home == OURS, Match.away == "VCV Castilla")).first()
        m.starts_at = m.starts_at + timedelta(hours=1)  # en la base de datos, a otra hora
        st = s.scalars(select(Standing).where(Standing.team == "VCV Colón")).first()
        st.points = 7
        before = s.get(Category, cat["id"]).data_updated_at
        s.commit()

    cal = upload(client, calendar_bytes, CALENDAR_XLS.name, cat["id"])
    assert cal["status"] == "ok"
    assert cal["message"].startswith("1 cambio de horario o pabellón")
    assert "CDF Voleibol Ancares UVa – VCV Castilla" in cal["message"]  # ejemplo de Ancares
    rank = upload(client, ranking_bytes, RANKING_XLS.name, cat["id"])
    assert rank["message"].startswith("1 equipo cambia en la clasificación")

    client.post("/api/admin/login", json={"password": "secreto"})
    logs = client.get("/api/admin/logs").json()
    assert any("VCV Colón" in d for d in logs[0]["details"])
    item = next(c for c in client.get("/api/admin/categories").json() if c["id"] == cat["id"])
    assert item["last_change"]["kind"] == "ranking"
    with SessionLocal() as s:
        assert s.get(Category, cat["id"]).data_updated_at > before
    home = client.get("/api/home").json()
    assert home["updated_at"] and home["checked_at"]


def test_diff_detects_new_result():
    old = Match(round_no=1, round_name="Jornada 1", home=OURS, away="VCV Castilla", is_bye=False, raw_teams="x",
                starts_at=datetime(2026, 10, 17, 15, tzinfo=timezone.utc), venue="Fuente la Mora",
                home_sets=None, away_sets=None, partials=[], is_ours=True)
    new = MatchRow(order=1, round_no=1, round_name="Jornada 1", raw_teams="x", home=OURS, away="VCV Castilla",
                   starts_at=datetime(2026, 10, 17, 17, tzinfo=timezone(timedelta(hours=2))), venue="Fuente la Mora",
                   home_sets=3, away_sets=1, partials=[[25, 20], [20, 25], [25, 18], [25, 22]])
    changes = diff_calendar([old], [new], is_ours)
    assert [c.kind for c in changes] == ["result_new"]  # misma hora (17:00 +02 = 15:00 UTC): sin cambio de horario
    assert summary(changes) == f"1 resultado nuevo ({OURS} 3-1 VCV Castilla (Jornada 1))"


def test_conditional_download(client, ranking_bytes, monkeypatch):
    """Si la FVCL manda ETag, la siguiente vez se pregunta y un 304 evita la descarga."""
    seen = []

    def server(request):
        if request.url.path != "/r/export-xls":
            return httpx.Response(404)  # p. ej. la búsqueda de escudos: no interesa aquí
        seen.append(request.headers.get("if-none-match"))
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304, headers={"etag": '"v1"'})
        return httpx.Response(200, headers={"etag": '"v1"', "content-type": "application/vnd.ms-excel"}, content=ranking_bytes)

    real = httpx.Client
    monkeypatch.setattr(fetcher.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(server), **kw))
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil", "ranking_url": "https://fvcl.example/r/export-xls"}).json()

    first = sync_categories([cat["id"]])
    second = sync_categories([cat["id"]])
    assert seen == [None, '"v1"']
    assert first[0]["status"] == "ok" and second[0]["status"] == "unchanged" and "304" in second[0]["message"]
    with SessionLocal() as s:
        assert s.get(Category, cat["id"]).http_validators == {"https://fvcl.example/r/export-xls": {"etag": '"v1"'}}
        last = s.scalars(select(SyncLog).order_by(SyncLog.id.desc())).first()
        assert last.status == "unchanged"
