"""Qué ha cambiado de verdad entre lo que ya tenemos y un Excel nuevo de la FVCL.

Clupik genera cada Excel al vuelo y guarda en sus metadatos la hora de
creación, así que dos descargas con los mismos datos nunca son iguales byte a
byte. Por eso se comparan los **datos**: partido a partido y equipo a equipo.
"""
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence
from zoneinfo import ZoneInfo

from ..models import Match, Standing
from ..parsers.calendar import MatchRow
from ..parsers.common import norm
from ..parsers.ranking import StandingRow

TZ = ZoneInfo("Europe/Madrid")
DAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


@dataclass
class Change:
    kind: str  # result_new | result_changed | schedule | added | removed | standing
    text: str
    ours: bool = False


LABELS = {
    "result_new": ("resultado nuevo", "resultados nuevos"),
    "result_changed": ("resultado corregido", "resultados corregidos"),
    "schedule": ("cambio de horario o pabellón", "cambios de horario o pabellón"),
    "added": ("partido nuevo", "partidos nuevos"),
    "removed": ("partido eliminado", "partidos eliminados"),
    "standing": ("equipo cambia en la clasificación", "equipos cambian en la clasificación"),
}


# --- huella de contenido -------------------------------------------------------

def _utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def content_hash(kind: str, rows: Sequence) -> str:
    """SHA-256 de los datos parseados (no de los bytes del fichero)."""
    if kind == "ranking":
        data = [[r.position, r.team, r.points, r.played, r.won, r.lost, r.sets_for, r.sets_against,
                 r.points_for, r.points_against, r.promotion] for r in rows]
    else:
        data = [[r.round_no, r.round_name, r.raw_teams, _utc(r.starts_at), r.venue, r.home_sets, r.away_sets,
                 r.partials, r.raw_result] for r in rows]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


# --- calendario --------------------------------------------------------------------

def _key(m) -> tuple:
    """Partido por jornada y equipos; descansos aparte y, si aún no se pudo separar
    local/visitante (calendario antes que clasificación), por el texto original."""
    if m.is_bye:
        return (m.round_no, "·descansa", norm(m.home))
    if not m.away:
        return (m.round_no, "·texto", norm(m.raw_teams))
    return (m.round_no, norm(m.home), norm(m.away))


def _when(dt: Optional[datetime]) -> str:
    if dt is None:
        return "sin fecha"
    dt = (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(TZ)
    return f"{DAYS[dt.weekday()]} {dt.day}/{dt.month} {dt:%H:%M}"


def _sets(hs, as_) -> str:
    return f"{hs}-{as_}"


def _partials(p) -> list:
    return [list(x[:2]) for x in (p or [])]


def diff_calendar(old: Iterable[Match], new: Iterable[MatchRow], is_ours) -> List[Change]:
    old_map = {_key(m): m for m in old}
    new_map = {_key(r): r for r in new}
    changes: List[Change] = []
    for key, r in new_map.items():
        if r.is_bye:
            continue
        ours = is_ours(r.home) or is_ours(r.away) or is_ours(r.raw_teams)
        teams = f"{r.home} – {r.away}" if r.away else r.raw_teams
        m = old_map.get(key)
        if m is None:
            changes.append(Change("added", f"Nuevo partido: {teams} ({r.round_name}, {_when(r.starts_at)})", ours))
            continue
        # Resultado
        if m.home_sets is None and r.home_sets is not None:
            changes.append(Change("result_new", f"{r.home} {_sets(r.home_sets, r.away_sets)} {r.away} ({r.round_name})", ours))
        elif m.home_sets is not None and r.home_sets is None:
            changes.append(Change("result_changed", f"Se retira el resultado de {teams}", ours))
        elif m.home_sets is not None and (
            (m.home_sets, m.away_sets) != (r.home_sets, r.away_sets) or _partials(m.partials) != _partials(r.partials)
        ):
            changes.append(Change(
                "result_changed",
                f"{teams}: {_sets(m.home_sets, m.away_sets)} → {_sets(r.home_sets, r.away_sets)}", ours,
            ))
        # Fecha, hora o pabellón (en un solo cambio si varían a la vez)
        what = []
        if _utc(m.starts_at) != _utc(r.starts_at):
            before, after = _when(m.starts_at), _when(r.starts_at)
            same_day = before.rsplit(" ", 1)[0] == after.rsplit(" ", 1)[0]
            what.append(f"{before} → {after.rsplit(' ', 1)[1] if same_day else after}")
        if (m.venue or "") != (r.venue or ""):
            what.append(f"pabellón {m.venue or '?'} → {r.venue or '?'}")
        if what:
            changes.append(Change("schedule", f"{teams}: {' · '.join(what)}", ours))
    for key, m in old_map.items():
        if key not in new_map and not m.is_bye:
            teams = f"{m.home} – {m.away}" if m.away else m.raw_teams
            changes.append(Change("removed", f"Ya no aparece: {teams} ({m.round_name})", m.is_ours))
    return changes


# --- clasificación ---------------------------------------------------------------

def diff_ranking(old: Iterable[Standing], new: Iterable[StandingRow], is_ours) -> List[Change]:
    old_map = {norm(s.team): s for s in old}
    changes: List[Change] = []
    seen = set()
    for r in new:
        key = norm(r.team)
        seen.add(key)
        s = old_map.get(key)
        fields = ("position", "points", "played", "won", "lost", "sets_for", "sets_against")
        if s is None:
            changes.append(Change("standing", f"{r.team} entra en la clasificación ({r.position}º)", is_ours(r.team)))
        elif any(getattr(s, f) != getattr(r, f) for f in fields):
            pos = f"{s.position}º → {r.position}º" if s.position != r.position else f"{r.position}º"
            changes.append(Change("standing", f"{r.team}: {pos}, {r.points} pts", is_ours(r.team)))
    for key, s in old_map.items():
        if key not in seen:
            changes.append(Change("standing", f"{s.team} sale de la clasificación", s.is_ours))
    return changes


# --- resumen ---------------------------------------------------------------------

def summary(changes: List[Change]) -> str:
    """«3 resultados nuevos · 1 cambio de horario o pabellón (Ancares – Colón: dom 18/10 10:30 → 12:00)»"""
    if not changes:
        return "Sin cambios"
    counts = Counter(c.kind for c in changes)
    parts = []
    for kind in LABELS:
        if counts[kind]:
            one, many = LABELS[kind]
            parts.append(f"{counts[kind]} {one if counts[kind] == 1 else many}")
    # El primer cambio que afecta a Ancares, como ejemplo
    ours = next((c for c in changes if c.ours), None)
    text = " · ".join(parts)
    return f"{text} ({ours.text})" if ours else text
