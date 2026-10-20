"""Horarios cambiados a mano por el admin: mandan siempre sobre el Excel de la FVCL.

A veces un partido se juega otro día, a otra hora o en otro pabellón que los
del Excel. El admin lo cambia y ese horario se mantiene aunque se vuelva a
importar el calendario: los partidos se recrean en cada importación, así que
el cambio se guarda aparte por clave natural y se vuelve a aplicar después.
El horario del Excel se conserva en `excel_starts_at`/`excel_venue` para
compararlo en la detección de cambios y poder volver a él.
"""
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, Match, ScheduleOverride, utcnow
from .provisional import Key, match_key


def overrides_map(session: Session, category_id: int) -> Dict[Key, ScheduleOverride]:
    rows = session.scalars(select(ScheduleOverride).where(ScheduleOverride.category_id == category_id))
    return {(o.category_id, o.round_no, o.home_key, o.away_key): o for o in rows}


def _apply(m: Match, o: ScheduleOverride) -> None:
    if not m.schedule_override:  # lo que hay ahora es lo del Excel: se guarda antes de cambiarlo
        m.excel_starts_at, m.excel_venue = m.starts_at, m.venue
    m.starts_at = o.starts_at or m.excel_starts_at
    m.venue = o.venue or m.excel_venue
    m.schedule_override = True


def apply_overrides(session: Session, category: Category) -> int:
    """Tras importar el calendario: vuelve a aplicar los horarios del admin."""
    found = overrides_map(session, category.id)
    applied = 0
    for m in category.matches:
        o = found.get(match_key(m)) if not m.is_bye and m.away else None
        if o:
            _apply(m, o)
            applied += 1
    return applied


def set_override(session: Session, m: Match, starts_at: Optional[datetime], venue: Optional[str]) -> ScheduleOverride:
    key = match_key(m)
    o = overrides_map(session, m.category_id).get(key)
    if o is None:
        o = ScheduleOverride(category_id=key[0], round_no=key[1], home_key=key[2], away_key=key[3], home=m.home, away=m.away)
        session.add(o)
    o.starts_at, o.venue, o.updated_at = starts_at, venue, utcnow()
    _apply(m, o)
    return o


def clear_override(session: Session, m: Match) -> None:
    o = overrides_map(session, m.category_id).get(match_key(m))
    if o:
        session.delete(o)
    if m.schedule_override:
        m.starts_at, m.venue = m.excel_starts_at, m.excel_venue
        m.schedule_override = False
