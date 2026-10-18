"""Torneos que da de alta el admin a mano (sin Excel de la federación).

- Los partidos se meten con un formulario o pegando una lista de líneas.
- La fase («Grupo A», «Semifinal»...) hace de jornada: se numeran por orden de
  su primer partido para que el calendario las agrupe.
- Los resultados de los anotadores son provisionales hasta que el admin los
  confirma; el admin también puede poner el resultado directamente.
- Cada fase tiene su clasificación salvo las eliminatorias (final, semifinal,
  cuartos, 3er puesto...), que solo muestran partidos.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, Match, ProvisionalResult
from ..parsers.calendar import SETS_RE, parse_score
from ..parsers.common import norm
from . import stats
from .importer import is_ours
from .provisional import match_key, prov_key

TZ = ZoneInfo("Europe/Madrid")

SEP_RE = re.compile(r"\s*[·|;\t]\s*")
DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b")
TIME_RE = re.compile(r"\b(\d{1,2})[:.h](\d{2})\s*h?\b")
TEAMS_RE = re.compile(r"\s+(?:-|–|—|vs\.?|contra)\s+", re.I)
PHASE_RE = re.compile(
    r"^(grupo|fase|jornada|semifinal|semis|final|cuartos|octavos|tercer|3[ºo]|liguilla|liga|eliminatoria|consolaci[oó]n|partido)",
    re.I,
)
KNOCKOUT_RE = re.compile(r"^(final|semifinal|semis|cuartos|octavos|tercer|3o|3er|consolacion|eliminatoria|play ?off)")
DEFAULT_PHASE = "Partidos"


class TournamentError(ValueError):
    pass


# --- lista pegada ------------------------------------------------------------------

@dataclass
class ParsedMatch:
    line: str
    phase: str = ""
    date: Optional[str] = None  # ISO (AAAA-MM-DD)
    time: Optional[str] = None  # HH:MM
    home: str = ""
    away: str = ""
    venue: str = ""
    error: Optional[str] = None

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _infer_year(day: int, month: int, today: date) -> int:
    """Sin año: el de hoy, salvo que la fecha quede muy atrás (entonces el siguiente)."""
    candidate = date(today.year, month, day)
    return today.year + 1 if candidate < today - timedelta(days=60) else today.year


def parse_lines(text: str, today: Optional[date] = None) -> List[ParsedMatch]:
    """«18/10 10:30 · Grupo A · Ancares - CV Laguna · Pabellón X», una línea por partido.

    Separadores: «·», «|», «;» o tabulador. Equipos con « - », « – » o « vs ».
    Lo que no es fecha, hora ni equipos: fase (si lo parece) y pabellón.
    """
    today = today or datetime.now(TZ).date()
    out: List[ParsedMatch] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pm = ParsedMatch(line=line)
        rest: List[str] = []
        for token in SEP_RE.split(line):
            m = DATE_RE.search(token)
            if m and not pm.date:
                d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
                try:
                    year = (2000 + int(y) if len(y) == 2 else int(y)) if y else _infer_year(d, mo, today)
                    pm.date = date(year, mo, d).isoformat()
                except ValueError:
                    pm.error = f"Fecha no válida: {m.group(0)}"
                token = (token[: m.start()] + token[m.end():]).strip()
            m = TIME_RE.search(token)
            if m and not pm.time:
                hh, mm = int(m.group(1)), int(m.group(2))
                if hh < 24 and mm < 60:
                    pm.time = f"{hh:02d}:{mm:02d}"
                    token = (token[: m.start()] + token[m.end():]).strip()
            if not token:
                continue
            teams = TEAMS_RE.split(token, maxsplit=1)
            if len(teams) == 2 and not pm.home:
                pm.home, pm.away = teams[0].strip(), teams[1].strip()
            else:
                rest.append(token)
        if rest and (len(rest) > 1 or PHASE_RE.match(rest[0])):
            pm.phase = rest.pop(0)
        pm.venue = " · ".join(rest)
        if not pm.home or not pm.away:
            pm.error = pm.error or "No encuentro los equipos (sepáralos con « - » o « vs »)"
        elif pm.date and not pm.time:
            pm.error = pm.error or "Falta la hora (p. ej. 10:30)"
        out.append(pm)
    return out


# --- partidos ---------------------------------------------------------------------

def starts_at_of(day: Optional[str], hour: Optional[str]) -> Optional[datetime]:
    if not day:
        return None
    if not hour:
        raise TournamentError("Si pones fecha, pon también la hora")
    local = datetime.combine(date.fromisoformat(day), time.fromisoformat(hour), tzinfo=TZ)
    return local.astimezone(timezone.utc)


def parse_result(text: Optional[str]) -> Tuple[Optional[int], Optional[int], list]:
    """«3-1» (solo sets) o «25-20 23-25 15-12» (parciales). Vacío: sin resultado."""
    text = (text or "").strip()
    if not text:
        return None, None, []
    if SETS_RE.match(text):
        hs, as_, _ = parse_score(text, "")
        return hs, as_, []
    hs, as_, partials = parse_score("", text)
    if not partials:
        raise TournamentError("No entiendo el resultado: usa «3-1» o los parciales «25-20 23-25 15-12»")
    return hs, as_, partials


def require_tournament(category: Category) -> None:
    if not category.is_tournament:
        raise TournamentError("Los partidos de liga vienen del Excel de la federación: no se editan a mano")


def save_match(session: Session, category: Category, data: dict, match: Optional[Match] = None) -> Match:
    """Crea o actualiza un partido del torneo (y conserva su resultado provisional si cambia de clave)."""
    require_tournament(category)
    home, away = (data.get("home") or "").strip(), (data.get("away") or "").strip()
    if not home or not away:
        raise TournamentError("Faltan los equipos")
    old_key = match_key(match) if match else None
    m = match or Match(category_id=category.id, order=0, round_no=0)
    m.home, m.away = home, away
    m.raw_teams = f"{home} {away}"
    m.round_name = (data.get("phase") or "").strip() or DEFAULT_PHASE
    m.starts_at = starts_at_of(data.get("date"), data.get("time"))
    m.venue = (data.get("venue") or "").strip() or None
    m.is_bye = False
    m.is_ours = is_ours(home) or is_ours(away)
    if "result" in data:
        m.home_sets, m.away_sets, m.partials = parse_result(data.get("result"))
        m.raw_result = (data.get("result") or "").strip() or None
    if match is None:
        session.add(m)
    session.flush()
    renumber(session, category, moved={m.id: old_key} if old_key else None)
    return m


def renumber(session: Session, category: Category, moved: Optional[Dict[int, tuple]] = None) -> None:
    """Numera las fases por su primer partido y ordena los partidos por fecha.

    Los resultados provisionales van por clave natural (categoría, jornada,
    equipos): si cambia, se arrastran con el partido.
    """
    session.expire(category, ["matches"])
    matches = list(category.matches)
    old_keys = {m.id: match_key(m) for m in matches}
    old_keys.update(moved or {})
    far = datetime.max.replace(tzinfo=timezone.utc)

    def when(m: Match) -> datetime:
        if m.starts_at is None:
            return far
        return m.starts_at if m.starts_at.tzinfo else m.starts_at.replace(tzinfo=timezone.utc)

    first: Dict[str, datetime] = {}
    for m in matches:
        first[m.round_name] = min(first.get(m.round_name, far), when(m))
    phase_no = {name: i for i, name in enumerate(sorted(first, key=lambda n: (first[n], n)), start=1)}
    for i, m in enumerate(sorted(matches, key=lambda m: (when(m), m.id)), start=1):
        m.order = i
        m.round_no = phase_no[m.round_name]
    session.flush()
    for m in matches:
        old, new = old_keys.get(m.id), match_key(m)
        if old and old != new:
            prov = _provisional_by_key(session, old)
            if prov:
                prov.round_no, prov.home_key, prov.away_key = new[1], new[2], new[3]
                prov.home, prov.away = m.home, m.away


def _provisional_by_key(session: Session, key: tuple) -> Optional[ProvisionalResult]:
    return session.scalars(
        select(ProvisionalResult).where(
            ProvisionalResult.category_id == key[0],
            ProvisionalResult.round_no == key[1],
            ProvisionalResult.home_key == key[2],
            ProvisionalResult.away_key == key[3],
        )
    ).first()


def confirm_provisional(session: Session, prov: ProvisionalResult) -> Match:
    """El admin da por bueno un resultado provisional de torneo: pasa a ser el resultado."""
    category = session.get(Category, prov.category_id)
    require_tournament(category)
    key = (prov.category_id, prov.round_no, prov.home_key, prov.away_key)
    match = next((m for m in category.matches if match_key(m) == key), None)
    if match is None:
        raise TournamentError("Ya no encuentro ese partido en el torneo")
    match.home_sets, match.away_sets = prov.home_sets, prov.away_sets
    match.partials = prov.partials
    session.delete(prov)
    return match


# --- clasificación por grupos ---------------------------------------------------

def is_group_phase(name: str) -> bool:
    return not KNOCKOUT_RE.match(norm(name))


def _result(m: Match, hs: int, as_: int, partials: list, provisional: bool) -> stats.Result:
    return stats.Result(m.round_no, m.round_name, m.order, m.starts_at, m.home, m.away, hs, as_, partials, provisional)


def _rows(table: List[stats.Row], logo, previous: Optional[Dict[str, int]] = None) -> List[dict]:
    rows = []
    for pos, r in enumerate(table, start=1):
        rows.append({
            "position": pos, "team": r.team, "logo": logo(r.team), "points": r.points, "played": r.played,
            "won": r.won, "lost": r.lost, "sets_for": r.sets_for, "sets_against": r.sets_against,
            "is_ours": is_ours(r.team),
            "delta": (previous[norm(r.team)] - pos) if previous and norm(r.team) in previous else 0,
        })
    return rows


def group_tables(category: Category, provisional_for, logo) -> List[dict]:
    """Una clasificación por fase de grupo; con provisionales, otra versión que los incluye."""
    rule = stats.points_rule(category)  # la del admin o la de la normativa según la categoría
    phases: Dict[str, List[Match]] = {}
    for m in sorted(category.matches, key=lambda m: m.order):
        if not m.is_bye and m.away and is_group_phase(m.round_name):
            phases.setdefault(m.round_name, []).append(m)
    out = []
    for name, matches in sorted(phases.items(), key=lambda kv: kv[1][0].round_no):
        teams = list(dict.fromkeys(t for m in matches for t in (m.home, m.away)))
        confirmed = [_result(m, m.home_sets, m.away_sets, m.partials or [], False) for m in matches if m.home_sets is not None]
        pending = []
        for m in matches:
            p = provisional_for(m) if m.home_sets is None else None
            if p:
                pending.append(_result(m, p.home_sets, p.away_sets, p.partials or [], True))
        table = stats.build_table(teams, confirmed, rule=rule)
        positions = {norm(r.team): i for i, r in enumerate(table, start=1)}
        out.append({
            "name": name,
            "standings": _rows(table, logo),
            "with_provisional": _rows(stats.build_table(teams, confirmed + pending, rule=rule), logo, positions) if pending else None,
        })
    return out
