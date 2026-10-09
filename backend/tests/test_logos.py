import io

import httpx
import pytest
from PIL import Image

from conftest import RANKING_XLS
from app.services import fetcher, logos
from app.services.logos import LogoError, check_public_url, normalize_image
from app.services.logos_fvcl import find_logos, ranking_page_url

TEAMS = ["CDF Voleibol Ancares UVa", "VCV Castilla", "VCV Colón", "Maristas Burgos A", "Rio Duero Soria A"]


def png(w=300, h=100, color=(200, 30, 30, 255)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


# Página simulada al estilo de una clasificación de Clupik
PAGE = """
<html><head><script>var img = '<img src="/no-es-un-escudo.png">';</script></head><body>
<img src="/img/logo-federacion.png" alt="FVCL">
<table>
 <tr><td>1</td><td><img src="https://cdn.example.com/shields/rio.png?v=2"><span>Rio Duero Soria A</span></td><td>12</td></tr>
 <tr><td>2</td><td><a href="/team/1" title="Maristas Burgos A"><img data-src="/shields/maristas.jpg" src="data:image/gif;base64,AAAA"></a></td></tr>
 <tr><td>3</td><td><img src="/shields/castilla.png" alt="Escudo de VCV Castilla"> VCV Castilla</td></tr>
 <tr><td>4</td><td><img src="/shields/colon.svg"> VCV Colón</td></tr>
 <tr><td>5</td><td><img src="/shields/ancares.png"> CDF Voleibol Ancares UVa 9 3</td></tr>
</table></body></html>
"""


def test_find_logos():
    found = find_logos(PAGE, "https://fvcl.es/es/tournament/1/ranking/2", TEAMS)
    assert found == {
        "Rio Duero Soria A": "https://cdn.example.com/shields/rio.png?v=2",
        "Maristas Burgos A": "https://fvcl.es/shields/maristas.jpg",
        "VCV Castilla": "https://fvcl.es/shields/castilla.png",
        "CDF Voleibol Ancares UVa": "https://fvcl.es/shields/ancares.png",
    }  # VCV Colón solo tiene SVG: se ignora


def test_ranking_page_url():
    assert ranking_page_url("https://fvcl.es/es/tournament/1340430/ranking/3706763/export-xls") == (
        "https://fvcl.es/es/tournament/1340430/ranking/3706763"
    )


def test_normalize_image_square_webp():
    out = Image.open(io.BytesIO(normalize_image(png())))
    assert out.format == "WEBP" and out.size == (160, 160)
    with pytest.raises(LogoError):
        normalize_image(b"<svg></svg>")


@pytest.mark.parametrize("url", ["http://127.0.0.1/x.png", "http://localhost/x.png", "file:///etc/passwd", "http://u:p@example.com/x"])
def test_check_public_url_rejects_internal(url):
    with pytest.raises(LogoError):
        check_public_url(url)


def _login_and_import(client, ranking_bytes):
    assert client.post("/api/admin/login", json={"password": "secreto"}).status_code == 200
    cat = client.post(
        "/api/admin/categories",
        json={"name": "Infantil", "fvcl_name": "CRE Infantil Femenino Liga Oro",
              "ranking_url": "https://fvcl.es/es/tournament/1/ranking/2/export-xls"},
    ).json()
    files = [("files", (RANKING_XLS.name, ranking_bytes, "application/vnd.ms-excel"))]
    assert client.post("/api/admin/upload", files=files).json()["results"][0]["status"] == "ok"
    return cat


def test_manual_logo_flow(client, ranking_bytes):
    _login_and_import(client, ranking_bytes)
    teams = client.get("/api/admin/teams").json()
    assert len(teams) == 10 and all(t["logo"] is None for t in teams)
    castilla = next(t for t in teams if t["name"] == "VCV Castilla")

    r = client.post(f"/api/admin/teams/{castilla['id']}/logo", files={"file": ("e.png", png(), "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["logo"]
    assert url.startswith("/logos/") and url.endswith(".webp")
    img = client.get(url)
    assert img.status_code == 200 and "immutable" in img.headers["cache-control"]

    detail = client.get("/api/categories/infantil").json()
    assert next(s for s in detail["standings"] if s["team"] == "VCV Castilla")["logo"] == url
    assert any(m["away_logo"] == url or m["home_logo"] == url for m in detail["matches"]) is False  # sin calendario
    bad = client.post(f"/api/admin/teams/{castilla['id']}/logo", files={"file": ("x.png", b"no", "image/png")})
    assert bad.status_code == 422

    assert client.delete(f"/api/admin/teams/{castilla['id']}/logo").json()["ok"]
    assert client.get(url).status_code == 404


def test_search_fvcl_logos(client, monkeypatch, ranking_bytes):
    _login_and_import(client, ranking_bytes)
    images = {"/shields/rio.png": png(color=(0, 0, 255, 255)), "/shields/castilla.png": png()}

    def server(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/es/tournament/1/ranking/2":
            html = PAGE.replace("https://cdn.example.com", "https://fvcl.es")
            return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=html)
        if path in images:
            return httpx.Response(200, headers={"content-type": "image/png"}, content=images[path])
        return httpx.Response(404)

    real = httpx.Client
    monkeypatch.setattr(fetcher.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(server), **kw))
    monkeypatch.setattr(logos, "check_public_url", lambda url: None)  # sin DNS en los tests

    report = client.post("/api/admin/teams/search-fvcl", json={}).json()["reports"][0]
    assert sorted(report["found"]) == ["Rio Duero Soria A", "VCV Castilla"]
    assert report["checked"] == 10 and report["error"] is None
    teams = {t["name"]: t for t in client.get("/api/admin/teams").json()}
    assert teams["VCV Castilla"]["logo_source"] == "fvcl"
    assert teams["Maristas Burgos A"]["logo"] is None  # su imagen da 404

    # Sin force solo se reintenta pasada una semana
    again = client.post("/api/admin/teams/search-fvcl", json={"force": False}).json()["reports"][0]
    assert again["checked"] == 0
