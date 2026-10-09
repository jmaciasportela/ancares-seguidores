from conftest import CALENDAR_XLS, RANKING_XLS

from app.services import fetcher, sync
from app.services.fetcher import FetchResult


def login(client):
    assert client.post("/api/admin/login", json={"password": "secreto"}).status_code == 200


def create_category(client, **extra):
    payload = {"name": "Infantil Femenino", "fvcl_name": "CRE Infantil Femenino Liga Oro", **extra}
    r = client.post("/api/admin/categories", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_admin_requires_login(client):
    assert client.get("/api/admin/categories").status_code == 401
    assert client.post("/api/admin/login", json={"password": "mal"}).status_code == 401


def test_upload_by_filename_and_public_api(client, calendar_bytes, ranking_bytes):
    login(client)
    cat = create_category(client)
    assert cat["slug"] == "infantil-femenino"

    # Calendario antes que clasificación: se vuelve a separar al llegar la clasificación
    files = [("files", (CALENDAR_XLS.name, calendar_bytes, "application/vnd.ms-excel"))]
    r = client.post("/api/admin/upload", files=files)
    assert r.json()["results"][0]["status"] == "ok"
    files = [("files", (RANKING_XLS.name, ranking_bytes, "application/vnd.ms-excel"))]
    r = client.post("/api/admin/upload", files=files, data={"source": "share"})
    assert r.json()["results"][0]["category_id"] == cat["id"]

    detail = client.get("/api/categories/infantil-femenino").json()
    assert len(detail["standings"]) == 10
    assert detail["our_position"] == 5
    games = [m for m in detail["matches"] if not m["is_bye"]]
    assert all(m["away"] for m in games)
    assert sum(m["is_ours"] for m in detail["matches"]) > 0
    first = next(m for m in games if m["home"] == "CDF Voleibol Ancares UVa" and m["away"] == "VCV Castilla")
    assert first["starts_at"] == "2026-10-17T15:00:00+00:00"  # 17:00 GMT+2 guardado en UTC

    home = client.get("/api/home")
    assert home.status_code == 200 and home.json()["categories"][0]["slug"] == "infantil-femenino"
    assert client.get("/api/home", headers={"If-None-Match": home.headers["etag"]}).status_code == 304


def test_upload_unknown_category(client, ranking_bytes):
    login(client)
    files = [("files", ("otro.xls", ranking_bytes, "application/vnd.ms-excel"))]
    assert client.post("/api/admin/upload", files=files).json()["results"][0]["status"] == "needs_category"


def test_upload_rejects_html(client):
    login(client)
    files = [("files", ("x.xls", b"<html>bloqueado</html>", "application/vnd.ms-excel"))]
    assert client.post("/api/admin/upload", files=files).status_code == 422


def test_sync_blocked_and_ok(client, monkeypatch, ranking_bytes, calendar_bytes):
    login(client)
    cat = create_category(client, ranking_url="https://fvcl.example/r", calendar_url="https://fvcl.example/c")

    monkeypatch.setattr(sync, "fetch_xls", lambda url: FetchResult(ok=False, blocked=True, message="HTTP 429"))
    report = client.post("/api/admin/sync", json={"category_id": cat["id"]}).json()["report"]
    assert {r["status"] for r in report} == {"blocked"}
    cats = client.get("/api/admin/categories").json()
    assert cats[0]["sync_status"] == "blocked"

    data = {"https://fvcl.example/r": ranking_bytes, "https://fvcl.example/c": calendar_bytes}
    monkeypatch.setattr(sync, "fetch_xls", lambda url: FetchResult(ok=True, data=data[url]))
    report = client.post("/api/admin/sync", json={}).json()["report"]
    assert [r["status"] for r in report] == ["ok", "ok"]
    report = client.post("/api/admin/sync", json={}).json()["report"]
    assert [r["status"] for r in report] == ["unchanged", "unchanged"]
    assert client.get("/api/admin/categories").json()[0]["sync_status"] == "ok"
    assert len(client.get("/api/admin/logs").json()) == 6


def test_fetcher_detects_block(monkeypatch):
    import httpx

    def handler(request):
        return httpx.Response(429, headers={"content-type": "text/html"}, text="Comprobando tu navegador")

    real_client = httpx.Client
    monkeypatch.setattr(fetcher.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    res = fetcher.fetch_xls("https://fvcl.es/x")
    assert not res.ok and res.blocked


def test_feedback(client):
    r = client.post("/api/feedback", json={"kind": "mejora", "message": "¡Gracias por la app!"})
    assert r.status_code == 201
    client.post("/api/feedback", json={"message": "spam spam", "website": "http://spam"})
    login(client)
    items = client.get("/api/admin/feedback").json()
    assert len(items) == 1 and items[0]["kind"] == "mejora" and not items[0]["read"]
    assert client.patch(f"/api/admin/feedback/{items[0]['id']}", json={"read": True}).json()["read"]
