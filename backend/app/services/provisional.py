"""Resultados provisionales: clave natural del partido, carga y limpieza."""
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, Match, ProvisionalResult
from ..parsers.common import norm

Key = Tuple[int, int, str, str]


def prov_key(category_id: int, round_no: int, home: Optional[str], away: Optional[str]) -> Key:
    return (category_id, round_no, norm(home), norm(away))


def match_key(m: Match) -> Key:
    return prov_key(m.category_id, m.round_no, m.home, m.away)


def provisional_map(session: Session) -> Dict[Key, ProvisionalResult]:
    return {
        (p.category_id, p.round_no, p.home_key, p.away_key): p
        for p in session.scalars(select(ProvisionalResult)).all()
    }


def drop_superseded(session: Session, category: Category) -> int:
    """Borra los provisionales de partidos que ya tienen resultado oficial."""
    official = {match_key(m) for m in category.matches if m.home_sets is not None}
    removed = 0
    for p in session.scalars(select(ProvisionalResult).where(ProvisionalResult.category_id == category.id)).all():
        if (p.category_id, p.round_no, p.home_key, p.away_key) in official:
            session.delete(p)
            removed += 1
    return removed
