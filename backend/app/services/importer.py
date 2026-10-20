"""Importa un Excel de la FVCL en la base de datos de forma atómica por categoría."""
from dataclasses import dataclass, field
from datetime import timezone
from typing import List, Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Category, Match, Standing, SyncLog, utcnow
from ..parsers.calendar import parse_calendar, split_teams
from ..parsers.common import ParseError, detect_kind, norm, read_rows
from ..parsers.ranking import parse_ranking
from .changes import content_hash, diff_calendar, diff_ranking, summary
from .logos import ensure_teams
from .provisional import drop_superseded
from .schedule import apply_overrides


@dataclass
class ImportResult:
    kind: str
    status: str  # ok | unchanged | error
    message: str = ""
    count: int = 0
    changes: List[str] = field(default_factory=list)


def is_ours(team: Optional[str]) -> bool:
    return bool(team) and norm(get_settings().team_keyword) in norm(team)


def sniff_kind(data: bytes) -> str:
    return detect_kind(read_rows(data))


def import_file(session: Session, category: Category, data: bytes, source: str) -> ImportResult:
    """Parsea, compara con lo que ya hay y solo guarda si los datos han cambiado.

    Se comparan datos, no bytes: Clupik mete la hora de exportación en cada
    Excel, así que dos descargas iguales nunca coinciden byte a byte.
    """
    kind = "?"
    try:
        rows = read_rows(data)
        kind = detect_kind(rows)
        if kind == "ranking":
            first_load = not category.standings
            parsed = parse_ranking(rows)
            found = diff_ranking(category.standings, parsed, is_ours)
        else:
            first_load = not category.matches
            parsed = parse_calendar(rows, [s.team for s in category.standings])
            found = diff_calendar(category.matches, parsed, is_ours)
        # Siempre se comparan los datos (son pocos): así también se corrige cualquier
        # desajuste con la FVCL. La huella de contenido queda solo como referencia.
        digest = content_hash(kind, parsed)
        hash_attr = f"{kind}_hash"
        if not found:
            # Mismos datos (aunque el fichero sea otro): no se toca nada
            setattr(category, hash_attr, digest)
            result = ImportResult(kind, "unchanged", "Sin cambios")
        else:
            if kind == "ranking":
                count = _store_ranking(session, category, parsed)
            else:
                count = _store_calendar(session, category, parsed)
            setattr(category, hash_attr, digest)
            category.data_updated_at = utcnow()
            message = f"Primera carga: {count} {'equipos' if kind == 'ranking' else 'partidos'}" if first_load else summary(found)
            result = ImportResult(kind, "ok", message, count, [] if first_load else [c.text for c in found][:60])
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
    session.add(SyncLog(category_id=category.id, kind=kind, source=source, status=result.status,
                        message=result.message, details=result.changes or None))
    session.commit()
    return result


def _store_ranking(session: Session, category: Category, parsed) -> int:
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
    ensure_teams(session, [s.team for s in parsed])
    # Si el calendario llegó antes que la clasificación, se vuelve a separar
    # local/visitante con los nombres de equipo ya conocidos.
    known = [s.team for s in parsed]
    for match in category.matches:
        home, away, is_bye = split_teams(match.raw_teams, known)
        match.home, match.away, match.is_bye = home, away, is_bye
        match.is_ours = is_ours(home) or is_ours(away)
    return len(parsed)


def _store_calendar(session: Session, category: Category, parsed) -> int:
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
                excel_starts_at=m.starts_at.astimezone(timezone.utc) if m.starts_at else None,
                excel_venue=m.venue,
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
    apply_overrides(session, category)  # los horarios que cambió el admin mandan sobre el Excel
    drop_superseded(session, category)  # la FVCL ya publicó esos resultados
    return len(parsed)
