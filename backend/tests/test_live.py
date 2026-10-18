from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from conftest import CALENDAR_XLS, RANKING_XLS, clear_ours_dates_except
from app.db import SessionLocal
from app.models import LiveScore, Match
from app.services import live
from app.services.live import hub

OURS = "CDF Voleibol Ancares UVa"
FMT = {"mode": "best_of", "sets": 3, "points": 25, "tiebreak": 15}


def state(*sets, status="playing", serve="home"):
    return {"format": FMT, "sets": [list(s) for s in sets] or [[0, 0, False]], "serve": serve, "status": status}


@pytest.fixture()
def league(client, ranking_bytes, calendar_bytes):
    """Categoría real con Ancares – VCV Castilla empezado hace 20 min. Devuelve su live_id."""
    hub.rooms.clear(), hub.ips.clear(), hub.seen.clear(), hub._pending.clear()
    hub.announce_delay, hub.max_per_ip = 0, 10
    client.post("/api/admin/login", json={"password": "secreto"})
    cat = client.post("/api/admin/categories", json={"name": "Infantil", "score_format": FMT}).json()
    files = [("files", (RANKING_XLS.name, ranking_bytes, "application/vnd.ms-excel")),
             ("files", (CALENDAR_XLS.name, calendar_bytes, "application/vnd.ms-excel"))]
    client.post("/api/admin/upload", files=files, data={"category_id": cat["id"]})
    clear_ours_dates_except("VCV Castilla")
    with SessionLocal() as s:
        m = s.scalars(select(Match).where(Match.home == OURS, Match.away == "VCV Castilla")).first()
        m.starts_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        s.commit()
    nm = client.get("/api/home").json()["categories"][0]["next_match"]
    assert nm["away"] == "VCV Castilla" and nm["live"] is None
    return nm["live_id"]


def scorers(client, *names):
    """Crea anotadores (como admin) y devuelve una función para entrar con cada uno."""
    codes = {n: client.post("/api/admin/scorers", json={"name": n}).json()["code"] for n in names}

    def as_scorer(name):
        client.cookies.clear()
        if name == "admin":
            assert client.post("/api/admin/login", json={"password": "secreto"}).status_code == 200
        else:
            assert client.post("/api/scorer/join", json={"code": codes[name]}).status_code == 200

    return as_scorer


def next_msg(ws, *types):
    """Siguiente mensaje de los tipos pedidos (se saltan los avisos de visores y los pings)."""
    while True:
        msg = ws.receive_json()
        if msg["type"] in types:
            return msg


def test_live_id_is_stable_and_resolves(client, league):
    lid = league
    cat_id, round_no, digest = lid.split("-")
    assert len(digest) == 8
    with SessionLocal() as s:
        m = live.find_match(s, lid)
        assert m.away == "VCV Castilla" and live.live_id(m) == lid
        assert live.find_match(s, "1-1-zzzz") is None and live.find_match(s, "x") is None


def test_scorer_broadcasts_to_viewers(client, league):
    lid = league
    as_scorer = scorers(client, "Ana")
    with client.websocket_connect(f"/api/live/{lid}/ws") as ws:
        assert next_msg(ws, "waiting", "state")["type"] == "waiting"

        as_scorer("Ana")
        r = client.post(f"/api/live/{lid}/claim", json={})
        assert r.status_code == 200 and r.json()["lead"] is True and r.json()["state"] is None

        r = client.post(f"/api/live/{lid}", json={"seq": 1, "state": state((1, 0, False))})
        assert r.status_code == 200, r.text
        assert r.json()["viewers"] == 1
        msg = next_msg(ws, "state")
        assert msg["state"]["sets"] == [[1, 0, False]] and msg["on"] is True and msg["seq"] == 1

        client.post(f"/api/live/{lid}", json={"seq": 2, "state": state((25, 20, True), (3, 1, False), serve="away")})
        assert next_msg(ws, "state")["state"]["serve"] == "away"

    # Plan B y tarjetas: el GET y la portada traen el estado y el resumen
    client.cookies.clear()
    got = client.get(f"/api/live/{lid}").json()
    assert got["live"]["seq"] == 2 and got["match"]["category"] == "Infantil" and got["match"]["score_format"]["sets"] == 3
    nm = client.get("/api/home").json()["categories"][0]["next_match"]
    assert nm["live"] == {"id": lid, "on": True, "status": "playing", "sets": [1, 0], "current": [3, 1], "set_no": 2}

    # Un visor nuevo recibe el estado al conectar
    with client.websocket_connect(f"/api/live/{lid}/ws") as ws:
        assert next_msg(ws, "state", "waiting")["state"]["sets"][1] == [3, 1, False]


def test_only_one_lead_and_takeover(client, league):
    lid = league
    as_scorer = scorers(client, "Ana", "Luis")
    as_scorer("Ana")
    assert client.post(f"/api/live/{lid}/claim", json={}).status_code == 200
    client.post(f"/api/live/{lid}", json={"seq": 1, "state": state((5, 3, False))})
    # Ana desde otro móvil (mismo código) sigue siendo la principal
    assert client.post(f"/api/live/{lid}/claim", json={}).json()["seq"] == 1

    as_scorer("Luis")
    r = client.post(f"/api/live/{lid}/claim", json={"takeover": True})
    detail = r.json()["detail"]
    assert r.status_code == 409 and detail["by"] == "Ana" and detail["stale"] is False and detail["can_takeover"] is False
    assert detail["state"]["sets"] == [[5, 3, False]]
    assert client.post(f"/api/live/{lid}", json={"seq": 9, "state": state((9, 9, False))}).status_code == 409

    # Ana lleva 11 minutos sin dar señal: Luis puede tomar el relevo y hereda el estado
    with SessionLocal() as s:
        s.scalars(select(LiveScore)).first().updated_at = datetime.now(timezone.utc) - timedelta(minutes=11)
        s.commit()
    assert client.get("/api/home").json()["categories"][0]["next_match"]["live"]["on"] is False
    r = client.post(f"/api/live/{lid}/claim", json={})
    assert r.status_code == 409 and r.json()["detail"]["can_takeover"] is True
    r = client.post(f"/api/live/{lid}/claim", json={"takeover": True})
    assert r.status_code == 200 and r.json()["state"]["sets"] == [[5, 3, False]] and r.json()["seq"] == 1
    assert client.post(f"/api/live/{lid}", json={"seq": 2, "state": state((6, 3, False))}).status_code == 200

    # Ana vuelve: ya no es la principal
    as_scorer("Ana")
    r = client.post(f"/api/live/{lid}", json={"seq": 3, "state": state((5, 4, False))})
    assert r.status_code == 409 and r.json()["detail"]["lost"] is True and "Luis" in r.json()["detail"]["message"]

    # El admin puede tomar el relevo siempre
    as_scorer("admin")
    assert client.post(f"/api/live/{lid}/claim", json={}).status_code == 409
    assert client.post(f"/api/live/{lid}/claim", json={"takeover": True}).status_code == 200


def test_push_rules_and_validation(client, league):
    lid = league
    as_scorer = scorers(client, "Ana")
    client.cookies.clear()
    assert client.post(f"/api/live/{lid}/claim", json={}).status_code == 401  # una familia cualquiera
    assert client.post(f"/api/live/{lid}", json={"seq": 1, "state": state((1, 0, False))}).status_code == 401

    as_scorer("Ana")
    assert client.post(f"/api/live/{lid}", json={"seq": 1, "state": state((1, 0, False))}).status_code == 409  # sin reclamar
    client.post(f"/api/live/{lid}/claim", json={})
    bad = [
        {"seq": 1, "state": state((120, 0, False))},  # fuera de rango
        {"seq": 1, "state": state((25, 20, True), (25, 20, True), (25, 20, True), (1, 0, False))},  # más sets que el formato
        {"seq": 1, "state": state((1, 0, False), status="ganando")},
        {"seq": -1, "state": state((1, 0, False))},
    ]
    for body in bad:
        assert client.post(f"/api/live/{lid}", json=body).status_code == 422, body

    assert client.post(f"/api/live/{lid}", json={"seq": 5, "state": state((10, 8, False))}).json()["seq"] == 5
    # Un envío atrasado (reintento que llega tarde) no pisa el estado
    r = client.post(f"/api/live/{lid}", json={"seq": 4, "state": state((9, 8, False))})
    assert r.status_code == 200 and r.json()["seq"] == 5
    assert client.get(f"/api/live/{lid}").json()["live"]["state"]["sets"] == [[10, 8, False]]


def test_stop_and_resume(client, league):
    lid = league
    as_scorer = scorers(client, "Ana", "Luis")
    as_scorer("Ana")
    client.post(f"/api/live/{lid}/claim", json={})
    client.post(f"/api/live/{lid}", json={"seq": 1, "state": state((25, 10, True), status="set_over")})
    with client.websocket_connect(f"/api/live/{lid}/ws") as ws:
        next_msg(ws, "state")
        as_scorer("Luis")
        assert client.delete(f"/api/live/{lid}").status_code == 409  # solo quien retransmite
        as_scorer("Ana")
        assert client.delete(f"/api/live/{lid}").status_code == 200
        assert next_msg(ws, "state")["on"] is False
    assert client.post(f"/api/live/{lid}", json={"seq": 2, "state": state((25, 10, True))}).status_code == 409
    assert client.get(f"/api/live/{lid}").json()["live"]["on"] is False

    # Parada la emisión, cualquier anotador puede retomarla desde donde iba
    as_scorer("Luis")
    r = client.post(f"/api/live/{lid}/claim", json={})
    assert r.status_code == 200 and r.json()["state"]["status"] == "set_over"


def test_claim_window_and_unknown(client, league):
    lid = league
    as_scorer = scorers(client, "Ana")
    as_scorer("Ana")
    assert client.post("/api/live/1-1-abcdef12/claim", json={}).status_code == 404
    assert client.get("/api/live/1-1-abcdef12").status_code == 404
    with SessionLocal() as s:
        m = s.scalars(select(Match).where(Match.home == OURS, Match.away == "VCV Castilla")).first()
        m.starts_at = datetime.now(timezone.utc) + timedelta(days=1)
        s.commit()
    r = client.post(f"/api/live/{lid}/claim", json={})
    assert r.status_code == 409 and "3 horas antes" in r.json()["detail"]
    # El admin sí puede: a veces se juega otro día que el del Excel
    as_scorer("admin")
    assert client.post(f"/api/live/{lid}/claim", json={}).status_code == 200


def test_ws_unknown_match_and_limits(client, league):
    lid = league
    with client.websocket_connect("/api/live/1-1-abcdef12/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4404

    hub.max_per_ip = 1
    with client.websocket_connect(f"/api/live/{lid}/ws") as first:
        next_msg(first, "waiting")
        assert hub.viewers(lid) == 1
        with client.websocket_connect(f"/api/live/{lid}/ws") as second:
            with pytest.raises(WebSocketDisconnect) as exc:
                second.receive_json()
        assert exc.value.code == 4429
    assert hub.viewers(lid) == 0 and not hub.ips


def test_scoring_matches_shows_who_is_live(client, league):
    lid = league
    as_scorer = scorers(client, "Ana", "Luis")
    as_scorer("Ana")
    client.post(f"/api/live/{lid}/claim", json={})
    mine = next(i for i in client.get("/api/scoring/matches").json() if i["away"] == "VCV Castilla")
    assert mine["live_by"] is None and mine["live_id"] == lid
    as_scorer("Luis")
    other = next(i for i in client.get("/api/scoring/matches").json() if i["away"] == "VCV Castilla")
    assert other["live_by"] == "Ana"


def test_purge_old(client, league):
    lid = league
    as_scorer = scorers(client, "Ana")
    as_scorer("Ana")
    client.post(f"/api/live/{lid}/claim", json={})
    with SessionLocal() as s:
        assert live.purge_old(s) == 0
        assert live.purge_old(s, now=datetime.now(timezone.utc) + timedelta(days=3)) == 1
