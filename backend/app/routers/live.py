"""Marcador en directo: el anotador principal emite y cualquiera lo ve (WebSocket, o consultas si falla)."""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from sqlalchemy.orm import Session

from ..auth import RateLimiter, client_ip
from ..db import SessionLocal, get_session
from ..schemas import LiveClaimIn, LiveIn
from ..scoring_format import format_of
from ..serializers import match_out
from ..services import live
from ..services.live import LiveError, hub
from .public import cached_json, make_ctx
from .scoring import Publisher, require_publisher

router = APIRouter(prefix="/api/live", tags=["live"])
push_limiter = RateLimiter(limit=300, window=60)
PING_EVERY = 25  # mantiene viva la conexión a través del proxy y avisa si el principal no da señal


def _fail(err: LiveError) -> HTTPException:
    return HTTPException(status_code=err.status, detail=err.detail)


def _who(who: Publisher):
    """(id de anotador, es admin): el admin publica sin id de anotador."""
    return (who.scorer.id if who.scorer else None), who.scorer is None


def _row_or_409(session: Session, live_id: str):
    row = live.row_for(session, live_id)
    if not row:
        raise HTTPException(status_code=409, detail="Este partido no se está retransmitiendo")
    return row


@router.post("/{live_id}/claim")
async def claim(live_id: str, data: LiveClaimIn, who: Publisher = Depends(require_publisher),
                session: Session = Depends(get_session)):
    m = live.find_match(session, live_id)
    if not m:
        raise HTTPException(status_code=404, detail="No encuentro ese partido de Ancares")
    scorer_id, admin = _who(who)
    try:
        row = live.claim(session, m, scorer_id, who.name, admin, takeover=data.takeover)
    except LiveError as err:
        raise _fail(err) from err
    hub.mark_seen(live_id)
    if not row.state:  # los que ya esperan saben al momento que la retransmisión está lista
        await hub.broadcast(live_id, {"type": "ready", "viewers": hub.viewers(live_id)})
    return {"lead": True, "id": row.live_id, "seq": row.seq, "state": row.state, "viewers": hub.viewers(live_id)}


@router.post("/{live_id}")
async def push(live_id: str, data: LiveIn, request: Request, who: Publisher = Depends(require_publisher),
               session: Session = Depends(get_session)):
    push_limiter.check(request)
    row = _row_or_409(session, live_id)
    scorer_id, admin = _who(who)
    try:
        changed = live.push(session, row, scorer_id, admin, data.seq, data.state.model_dump(mode="json"))
    except LiveError as err:
        raise _fail(err) from err
    hub.mark_seen(live_id)
    if changed:
        await hub.broadcast(live_id, live.state_message(row, hub.viewers(live_id), 0))
    return {"ok": True, "seq": row.seq, "viewers": hub.viewers(live_id)}


@router.delete("/{live_id}")
async def stop(live_id: str, who: Publisher = Depends(require_publisher), session: Session = Depends(get_session)):
    row = _row_or_409(session, live_id)
    scorer_id, admin = _who(who)
    try:
        live.release(session, row, scorer_id, admin)
    except LiveError as err:
        raise _fail(err) from err
    if row.state:
        await hub.broadcast(live_id, live.state_message(row, hub.viewers(live_id), hub.lead_age(live_id, row)))
    else:
        await hub.broadcast(live_id, {"type": "waiting", "viewers": hub.viewers(live_id)})
    return {"ok": True}


@router.get("/{live_id}")
def get_live(live_id: str, request: Request, session: Session = Depends(get_session)):
    """Partido y estado actual: carga inicial del visor y plan B cuando el WebSocket no conecta."""
    m = live.find_match(session, live_id)
    if not m:
        raise HTTPException(status_code=404, detail="No encuentro ese partido")
    row = live.row_for(session, live_id)
    cat = m.category
    match = match_out(m, make_ctx(session))
    match.update(category=cat.name, category_slug=cat.slug, score_format=format_of(cat.score_format))
    viewers = hub.viewers(live_id)
    state = live.state_message(row, viewers, hub.lead_age(live_id, row)) if row and row.state else None
    return cached_json(request, {"match": match, "live": state, "ready": live.is_ready(row), "viewers": viewers})


@router.websocket("/{live_id}/ws")
async def live_ws(ws: WebSocket, live_id: str):
    """Solo lectura: al conectar manda el estado (o `ready`/`waiting` si aún no hay tanteo) y luego cada cambio."""
    ip = client_ip(ws)
    with SessionLocal() as session:
        m = live.find_match(session, live_id)
        row = live.row_for(session, live_id) if m else None
        first = live.state_message(row, 0, hub.lead_age(live_id, row)) if row and row.state else live.idle_message(row)
    await ws.accept()
    if not m:
        await ws.close(code=4404)
        return
    if not hub.can_join(ip):
        await ws.close(code=4429)
        return
    hub.join(live_id, ws, ip)

    async def ping() -> None:
        try:
            while True:
                await asyncio.sleep(PING_EVERY)
                await ws.send_json({"type": "ping", "viewers": hub.viewers(live_id), "lead_age": hub.lead_age(live_id)})
        except Exception:  # noqa: BLE001 - el visor se ha ido: el bucle principal lo da de baja
            pass

    pinger = asyncio.create_task(ping())
    try:
        await ws.send_json({**first, "viewers": hub.viewers(live_id)})
        while True:  # lo que mande el visor se ignora; solo esperamos a que se vaya
            if (await ws.receive())["type"] == "websocket.disconnect":
                break
    except Exception:  # noqa: BLE001 - desconexiones bruscas
        pass
    finally:
        pinger.cancel()
        hub.leave(live_id, ws)
