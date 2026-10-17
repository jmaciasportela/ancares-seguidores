"""Ánimos del día de partido: un contador colectivo y anónimo por partido y frase.

Sin texto libre (las jugadoras son menores): solo frases predefinidas.
Límites para que nadie infle el contador: 25 toques por envío y 300 por
móvil, partido y día (en memoria; se reinicia con el servidor, sin problema).
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Cheer, Match, utcnow
from .provisional import Key, match_key

KINDS = {
    "vamos": "💚 ¡Vamos Ancares!",
    "aporellas": "🔥 ¡A por ellas!",
    "defensa": "🛡️ ¡Defensa!",
    "bloqueo": "🧱 ¡Bloqueo!",
    "saque": "🎯 ¡Ese saque!",
}
OPENS_BEFORE = timedelta(hours=24)
CLOSES_AFTER = timedelta(hours=4)
MAX_PER_REQUEST = 25
MAX_PER_DEVICE = 300

_per_device: Dict[tuple, int] = defaultdict(int)


class CheerError(ValueError):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_open(m: Match, now: Optional[datetime] = None) -> bool:
    if not m.is_ours or m.is_bye or not m.starts_at:
        return False
    now = now or datetime.now(timezone.utc)
    start = _aware(m.starts_at)
    return start - OPENS_BEFORE <= now <= start + CLOSES_AFTER


def totals_map(session: Session) -> Dict[Key, Dict[str, int]]:
    out: Dict[Key, Dict[str, int]] = {}
    for c in session.scalars(select(Cheer)).all():
        out.setdefault((c.category_id, c.round_no, c.home_key, c.away_key), {})[c.kind] = c.count
    return out


def summary(by_kind: Dict[str, int], m: Match, now: Optional[datetime] = None) -> dict:
    return {"total": sum(by_kind.values()), "by_kind": by_kind, "open": is_open(m, now)}


def add(session: Session, m: Match, kind: str, n: int, device_hash: str, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if kind not in KINDS:
        raise CheerError("Ánimo desconocido", 422)
    if not m.is_ours or m.is_bye:
        raise CheerError("Solo se puede animar a Ancares 💚", 422)
    if not is_open(m, now):
        raise CheerError("Los ánimos se abren el día del partido", 409)
    key = match_key(m)
    quota_key = (device_hash, key, now.date())
    allowed = max(0, min(n, MAX_PER_REQUEST, MAX_PER_DEVICE - _per_device[quota_key]))
    if allowed:
        _per_device[quota_key] += allowed
        row = session.scalars(
            select(Cheer).where(
                Cheer.category_id == key[0], Cheer.round_no == key[1],
                Cheer.home_key == key[2], Cheer.away_key == key[3], Cheer.kind == kind,
            )
        ).first()
        if row is None:
            row = Cheer(category_id=key[0], round_no=key[1], home_key=key[2], away_key=key[3], kind=kind, count=0)
            session.add(row)
        row.count += allowed
        row.updated_at = utcnow()
        session.commit()
    return summary(totals_map(session).get(key, {}), m, now)
