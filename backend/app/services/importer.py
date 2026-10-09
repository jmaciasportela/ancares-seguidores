"""Importa un Excel de la FVCL en la base de datos de forma atómica por categoría."""
import hashlib
from datetime import timezone
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Category, Match, Standing, SyncLog, utcnow
from ..parsers.calendar import parse_calendar, split_teams
from ..parsers.common import ParseError, detect_kind, norm, read_rows
from ..parsers.ranking import parse_ranking


@dataclass
class ImportResult:
    kind: str
    status: str  # ok | unchanged | error
    message: str = ""
    count: int = 0


def is_ours(team: Optional[str]) -> bool:
    return bool(team) and norm(get_settings().team_keyword) in norm(team)


def sniff_kind(data: bytes) -> str:
    return detect_kind(read_rows(data))


def import_file(
    session: Session, category: Category, data: bytes, source: str, force: bool = False
) -> ImportResult:
    """Parsea y guarda el fichero. Si falla, no toca los datos existentes."""
    kind = "?"
    try:
        rows = read_rows(data)
        kind = detect_kind(rows)
        digest = hashlib.sha256(data).hexdigest()
        hash_attr = f"{kind}_hash"
        if not force and getattr(category, hash_attr) == digest:
            result = ImportResult(kind, "unchanged", "Sin cambios desde la última importación")
        else:
            count = _store_ranking(session, category, rows) if kind == "ranking" else _store_calendar(session, category, rows)
            setattr(category, hash_attr, digest)
            category.data_updated_at = utcnow()
            result = ImportResult(kind, "ok", f"{count} filas importadas", count)
    except ParseError as exc:
        session.rollback()
        result = ImportResult(kind, "error", str(exc))

    category.last_sync_at = utcnow()
    if result.status == "error":
        category.sync_status = "error"
        category.last_error = result.message
    else:
        category.sync_status = "ok" if source == "auto" else "manual"
        category.last_error = None
    session.add(SyncLog(category_id=category.id, kind=kind, source=source, status=result.status, message=result.message))
    session.commit()
    return result


def _store_ranking(session: Session, category: Category, rows) -> int:
    parsed = parse_ranking(rows)
    session.execute(delete(Standing).where(Standing.category_id == category.id))
    for s in parsed:
        session.add(
            Standing(
                category_id=category.id,
                position=s.position,
                team=s.team,
                points=s.points,
                played=s.played,
                won=s.won,
                lost=s.lost,
                sets_for=s.sets_for,
                sets_against=s.sets_against,
                points_for=s.points_for,
                points_against=s.points_against,
                promotion=s.promotion,
                is_ours=is_ours(s.team),
                extra=s.extra,
            )
        )
    session.flush()
    session.expire(category, ["standings"])
    # Si el calendario llegó antes que la clasificación, se vuelve a separar
    # local/visitante con los nombres de equipo ya conocidos.
    known = [s.team for s in parsed]
    for match in category.matches:
        home, away, is_bye = split_teams(match.raw_teams, known)
        match.home, match.away, match.is_bye = home, away, is_bye
        match.is_ours = is_ours(home) or is_ours(away)
    return len(parsed)


def _store_calendar(session: Session, category: Category, rows) -> int:
    known = [s.team for s in category.standings]
    parsed = parse_calendar(rows, known)
    session.execute(delete(Match).where(Match.category_id == category.id))
    for m in parsed:
        session.add(
            Match(
                category_id=category.id,
                order=m.order,
                round_no=m.round_no,
                round_name=m.round_name,
                home=m.home,
                away=m.away,
                is_bye=m.is_bye,
                # SQLite no guarda la zona: todo se almacena en UTC
                starts_at=m.starts_at.astimezone(timezone.utc) if m.starts_at else None,
                venue=m.venue,
                home_sets=m.home_sets,
                away_sets=m.away_sets,
                partials=m.partials,
                raw_teams=m.raw_teams,
                raw_result=m.raw_result,
                is_ours=is_ours(m.home) or is_ours(m.away),
            )
        )
    session.flush()
    session.expire(category, ["matches"])
    return len(parsed)
