"""Marcador en directo: el anotador principal emite el tanteo y las familias lo ven al momento.

- Por partido emite un solo anotador, el «principal»: el primero que lo reclama.
  Si deja de dar señal 10 min (móvil sin batería, sin cobertura...), otro anotador
  puede tomar el relevo y sigue desde el estado emitido. El admin puede siempre.
- Cada envío lleva el estado completo del marcador, así que un reintento nunca
  descuadra nada (y un `seq` antiguo se ignora).
- Los visores lo reciben por WebSocket. La app corre en un solo proceso, así que
  basta con un hub en memoria; el estado se guarda además en SQLite para que un
  reinicio no lo pierda.
"""
import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Union

from fastapi import WebSocket
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import LiveScore, Match, utcnow
from .provisional import Key, match_key

LEAD_TIMEOUT = timedelta(minutes=10)  # sin señal del principal: otro puede tomar el relevo
OPENS_BEFORE = timedelta(hours=3)
CLOSES_AFTER = timedelta(hours=6)
SHOW_FOR = timedelta(hours=12)  # cuánto se ve el resumen en las tarjetas tras el último envío
KEEP_FOR = timedelta(days=2)


class LiveError(Exception):
    def __init__(self, status: int, detail: Union[str, dict]):
        super().__init__(detail if isinstance(detail, str) else detail.get("message"))
        self.status, self.detail = status, detail


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --- identificación ----------------------------------------------------------------

def live_id_of(key: Key) -> str:
    """Id corto y estable para la URL del visor: no cambia aunque se reimporte el calendario."""
    category_id, round_no, home_key, away_key = key
    digest = hashlib.sha1(f"{home_key}|{away_key}".encode()).hexdigest()[:8]
    return f"{category_id}-{round_no}-{digest}"


def live_id(m: Match) -> str:
    return live_id_of(match_key(m))


def find_match(session: Session, lid: str) -> Optional[Match]:
    parts = lid.split("-")
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit() or len(parts[2]) != 8:
        return None
    query = select(Match).where(Match.category_id == int(parts[0]), Match.round_no == int(parts[1]))
    return next((m for m in session.scalars(query) if m.is_ours and not m.is_bye and live_id(m) == lid), None)


def row_for(session: Session, lid: str) -> Optional[LiveScore]:
    return session.scalars(select(LiveScore).where(LiveScore.live_id == lid)).first()


def live_map(session: Session, now: Optional[datetime] = None) -> Dict[Key, LiveScore]:
    since = (now or datetime.now(timezone.utc)) - SHOW_FOR
    rows = session.scalars(select(LiveScore).where(LiveScore.updated_at >= since))
    return {(r.category_id, r.round_no, r.home_key, r.away_key): r for r in rows}


# --- reglas del anotador principal -------------------------------------------------

def is_stale(row: LiveScore, now: Optional[datetime] = None) -> bool:
    return (now or datetime.now(timezone.utc)) - _aware(row.updated_at) > LEAD_TIMEOUT


def is_lead(row: LiveScore, scorer_id: Optional[int], admin: bool) -> bool:
    if scorer_id is None:  # el admin no tiene id de anotador
        return admin and row.scorer_id is None
    return row.scorer_id == scorer_id


def check_open(m: Match, now: datetime, admin: bool = False) -> None:
    if m.home_sets is not None:
        raise LiveError(409, "La federación ya ha publicado el resultado oficial de este partido")
    if admin:  # a veces se juega otro día u otra hora que la del Excel: el admin puede emitirlo igual
        return
    if not m.starts_at:
        raise LiveError(409, "Este partido todavía no tiene fecha ni hora")
    start = _aware(m.starts_at)
    if now < start - OPENS_BEFORE:
        raise LiveError(409, "El directo se abre 3 horas antes del partido")
    if now > start + CLOSES_AFTER:
        raise LiveError(409, "Este partido ya ha terminado")


def claim(session: Session, m: Match, scorer_id: Optional[int], name: str, admin: bool,
          takeover: bool = False, now: Optional[datetime] = None) -> LiveScore:
    """Convierte a quien pregunta en el anotador principal, o explica por qué no (409)."""
    now = now or datetime.now(timezone.utc)
    check_open(m, now, admin)
    key = match_key(m)
    row = session.scalars(
        select(LiveScore).where(
            LiveScore.category_id == key[0], LiveScore.round_no == key[1],
            LiveScore.home_key == key[2], LiveScore.away_key == key[3],
        )
    ).first()
    if row is None:
        row = LiveScore(
            live_id=live_id_of(key), category_id=key[0], round_no=key[1], home_key=key[2], away_key=key[3],
            scorer_id=scorer_id, lead_name=name, seq=0, started_at=now, updated_at=now,
        )
        session.add(row)
    elif row.ended_at is None and not is_lead(row, scorer_id, admin):
        stale = is_stale(row, now)
        if not (takeover and (stale or admin)):
            raise LiveError(409, {
                "message": f"{row.lead_name} ya está retransmitiendo este partido",
                "by": row.lead_name,
                "stale": stale,
                "can_takeover": stale or admin,
                "state": row.state,
                "seq": row.seq,
            })
    # Nuevo principal, el mismo desde otro móvil, retomar una emisión parada o tomar el relevo
    row.scorer_id, row.lead_name = scorer_id, name
    row.ended_at, row.updated_at = None, now
    try:
        session.commit()
    except IntegrityError as exc:  # dos anotadores empezando a la vez: solo uno crea la fila
        session.rollback()
        raise LiveError(409, "Otra persona acaba de empezar a retransmitir este partido. Inténtalo de nuevo.") from exc
    return row


def push(session: Session, row: LiveScore, scorer_id: Optional[int], admin: bool, seq: int, state: dict,
         now: Optional[datetime] = None) -> bool:
    """Guarda el estado que manda el principal. Devuelve si ha cambiado (False = latido o reintento)."""
    if row.ended_at is not None:
        raise LiveError(409, "La retransmisión de este partido está parada")
    if not is_lead(row, scorer_id, admin):
        raise LiveError(409, {"message": f"{row.lead_name} ha tomado el relevo", "by": row.lead_name, "lost": True})
    row.updated_at = now or datetime.now(timezone.utc)
    changed = seq > row.seq
    if changed:
        row.seq, row.state = seq, state
    session.commit()
    return changed


def release(session: Session, row: LiveScore, scorer_id: Optional[int], admin: bool) -> None:
    if not admin and not is_lead(row, scorer_id, admin):
        raise LiveError(409, "Solo quien retransmite puede pararlo")
    row.ended_at = utcnow()
    session.commit()


def purge_old(session: Session, now: Optional[datetime] = None) -> int:
    limit = (now or datetime.now(timezone.utc)) - KEEP_FOR
    res = session.execute(delete(LiveScore).where(LiveScore.updated_at < limit))
    session.commit()
    return res.rowcount or 0


# --- lo que se envía --------------------------------------------------------------

def summary(row: Optional[LiveScore], now: Optional[datetime] = None) -> Optional[dict]:
    """Resumen para las tarjetas: sets, set en curso y si sigue en directo."""
    if row is None or not row.state:
        return None
    now = now or datetime.now(timezone.utc)
    if now - _aware(row.updated_at) > SHOW_FOR:
        return None
    sets = row.state.get("sets") or [[0, 0, False]]
    cur = sets[-1]
    return {
        "id": row.live_id,
        "on": row.ended_at is None and not is_stale(row, now),
        "status": row.state.get("status"),
        "sets": [sum(1 for h, a, d in sets if d and h > a), sum(1 for h, a, d in sets if d and a > h)],
        "current": [cur[0], cur[1]],
        "set_no": len(sets),
    }


def is_ready(row: Optional[LiveScore], now: Optional[datetime] = None) -> bool:
    """Alguien ya lleva el marcador de este partido, aunque aún no haya mandado el primer tanteo."""
    return row is not None and row.ended_at is None and not is_stale(row, now)


def idle_message(row: Optional[LiveScore]) -> dict:
    """Sin tanteo todavía: `ready` si el anotador ya está dentro, `waiting` si aún no."""
    return {"type": "ready" if is_ready(row) else "waiting"}


def state_message(row: LiveScore, viewers: int, lead_age: Optional[int]) -> dict:
    return {
        "type": "state",
        "seq": row.seq,
        "state": row.state,
        "on": row.ended_at is None,
        "viewers": viewers,
        "lead_age": lead_age,  # segundos desde la última señal del principal
    }


# --- visores conectados ----------------------------------------------------------------

class Hub:
    """Conexiones WebSocket por partido, en memoria (un solo proceso)."""

    max_total = 300
    max_per_ip = 10
    announce_delay = 3.0  # agrupa altas y bajas antes de avisar del número de visores
    send_timeout = 5.0

    def __init__(self):
        self.rooms: Dict[str, Dict[WebSocket, str]] = defaultdict(dict)  # live_id -> {socket: ip}
        self.ips: Dict[str, int] = defaultdict(int)
        self.seen: Dict[str, datetime] = {}  # última señal del principal por partido
        self._pending: Dict[str, asyncio.Task] = {}

    def total(self) -> int:
        return sum(len(r) for r in self.rooms.values())

    def can_join(self, ip: str) -> bool:
        return self.total() < self.max_total and self.ips[ip] < self.max_per_ip

    def join(self, lid: str, ws: WebSocket, ip: str) -> None:
        self.rooms[lid][ws] = ip
        self.ips[ip] += 1
        self._announce(lid)

    def leave(self, lid: str, ws: WebSocket) -> None:
        room = self.rooms.get(lid)
        ip = room.pop(ws, None) if room is not None else None
        if ip is None:
            return
        self.ips[ip] -= 1
        if self.ips[ip] <= 0:
            del self.ips[ip]
        if not room:
            del self.rooms[lid]
        self._announce(lid)

    def viewers(self, lid: str) -> int:
        return len(self.rooms.get(lid, ()))

    def mark_seen(self, lid: str) -> None:
        self.seen[lid] = datetime.now(timezone.utc)

    def lead_age(self, lid: str, row: Optional[LiveScore] = None) -> Optional[int]:
        if lid not in self.seen and row is not None:  # tras un reinicio, lo que diga la base de datos
            self.seen[lid] = _aware(row.updated_at)
        seen = self.seen.get(lid)
        return int((datetime.now(timezone.utc) - seen).total_seconds()) if seen else None

    async def broadcast(self, lid: str, payload: dict) -> None:
        room = list(self.rooms.get(lid, {}))
        if not room:
            return
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        async def send(ws: WebSocket) -> None:
            try:
                await asyncio.wait_for(ws.send_text(text), timeout=self.send_timeout)
            except Exception:  # noqa: BLE001 - socket muerto o atascado: se cierra y su bucle lo da de baja
                self.leave(lid, ws)
                try:
                    await ws.close()
                except Exception:  # noqa: BLE001
                    pass

        await asyncio.gather(*(send(ws) for ws in room))

    def _announce(self, lid: str) -> None:
        if lid in self._pending:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def later() -> None:
            await asyncio.sleep(self.announce_delay)
            self._pending.pop(lid, None)
            await self.broadcast(lid, {"type": "viewers", "viewers": self.viewers(lid)})

        self._pending[lid] = loop.create_task(later())


hub = Hub()
