"""Estadísticas de temporada: clasificación jornada a jornada, datos de Ancares y
clasificación provisional.

El Excel de la FVCL solo trae la clasificación actual, así que la evolución se
reconstruye con los resultados del calendario. La puntuación depende de la
categoría (Normas Generales de Voleibol de la FVCL 2026-27, «Sistema de puntuación»):
  - «3-2-1-0» (Sénior, Júnior y Juvenil): 3 puntos por ganar sin llegar al set
    decisivo (3-0, 3-1, 2-0), 2 por ganar en el decisivo (3-2, 2-1), 1 por
    perderlo y 0 por perder sin llegar.
  - «2-1-0» (Cadete, Infantil, Alevín y Benjamín): 2 por ganar y 1 por perder,
    sea cual sea el resultado.
  - En los dos casos, 0 por no presentarse. Ver `points_system`.
Si la reconstrucción no cuadra con la tabla oficial (sanciones, aplazamientos...)
se marca como aproximada; la tabla que se enseña siempre es la oficial.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional

from ..models import Category, Match, Standing
from ..parsers.common import norm


def match_points(own: int, opp: int) -> int:
    """Puntos de clasificación de un equipo según los sets del partido."""
    if own > opp:
        return 2 if own >= 2 and opp == own - 1 else 3
    if own < opp:
        return 1 if opp >= 2 and own == opp - 1 else 0
    return 0  # empate (solo posible con sets fijos): sin regla oficial conocida


PointsRule = Callable[[int, int], int]


def win_loss_points(own: int, opp: int) -> int:
    """2 por ganar y 1 por perder, sea cual sea el resultado (categorías de cantera)."""
    return 2 if own > opp else 1 if own < opp else 0


# Los dos sistemas de la normativa de la FVCL
RULES: Dict[str, PointsRule] = {"3-2-1-0": match_points, "2-1-0": win_loss_points}
POINTS_LABELS = {
    "3-2-1-0": "3 por ganar 3-0 o 3-1, 2 por ganar 3-2 y 1 por perder 2-3",
    "2-1-0": "2 por partido ganado y 1 por perdido",
}
POINTS_SOURCES = {"admin": "elegida por el admin", "official": "según la clasificación oficial", "rules": "normativa FVCL"}
_CANTERA = re.compile(r"alev|benj|infantil|cadete")
_MAYORES = re.compile(r"juvenil|junior|senior|division")


def default_points_system(name: Optional[str]) -> str:
    """La de la normativa de la FVCL según la categoría (por su nombre)."""
    n = norm(name or "")
    if _CANTERA.search(n):
        return "2-1-0"
    return "3-2-1-0"  # Juvenil, Júnior, Sénior... y lo que no se reconozca


@dataclass
class Result:
    """Partido con resultado, oficial o provisional."""

    round_no: int
    round_name: str
    order: int
    starts_at: Optional[datetime]
    home: str
    away: str
    home_sets: int
    away_sets: int
    partials: List[list]
    provisional: bool = False

    def sets_of(self, team_key: str) -> tuple:
        if norm(self.home) == team_key:
            return self.home_sets, self.away_sets
        return self.away_sets, self.home_sets

    def points_of(self, team_key: str) -> tuple:
        """Puntos (tantos) a favor y en contra sumando los parciales."""
        own = opp = 0
        home = norm(self.home) == team_key
        for p in self.partials:
            h, a = p[0], p[1]
            own += h if home else a
            opp += a if home else h
        return own, opp

    def rival_of(self, team_key: str) -> str:
        return self.away if norm(self.home) == team_key else self.home


@dataclass
class Row:
    team: str
    played: int = 0
    won: int = 0
    lost: int = 0
    points: int = 0
    sets_for: int = 0
    sets_against: int = 0
    points_for: int = 0
    points_against: int = 0
    is_ours: bool = False
    official_position: Optional[int] = None

    def apply(self, r: Result, rule: PointsRule = match_points) -> None:
        key = norm(self.team)
        own, opp = r.sets_of(key)
        pf, pa = r.points_of(key)
        self.played += 1
        self.won += own > opp
        self.lost += own < opp
        self.points += rule(own, opp)
        self.sets_for += own
        self.sets_against += opp
        self.points_for += pf
        self.points_against += pa


def _ratio(a: int, b: int) -> float:
    return a / b if b else (float("inf") if a else 0.0)


def sort_rows(rows: Iterable[Row]) -> List[Row]:
    """Puntos, partidos ganados, cociente de sets, cociente de puntos y nombre."""
    return sorted(
        rows,
        key=lambda r: (
            -r.points,
            -r.won,
            -_ratio(r.sets_for, r.sets_against),
            -_ratio(r.points_for, r.points_against),
            norm(r.team),
        ),
    )


def build_table(teams: Iterable[str], results: Iterable[Result], ours_key: Optional[str] = None,
                rule: PointsRule = match_points) -> List[Row]:
    rows = {norm(t): Row(team=t, is_ours=norm(t) == ours_key) for t in teams}
    for r in results:
        for name in (r.home, r.away):
            key = norm(name)
            if key not in rows:  # rival que no figura en la clasificación
                rows[key] = Row(team=name, is_ours=key == ours_key)
            rows[key].apply(r, rule)
    return sort_rows(rows.values())


def deduce_points_system(category: Category) -> Optional[str]:
    """La que cuadra con la tabla oficial, comparándola con los resultados del calendario.

    Solo cuentan los equipos cuyos partidos jugados en la tabla coinciden con los
    resultados que trae el calendario. Si las dos reglas cuadran igual (sin
    resultados, o solo partidos 3-2), no se puede saber: None.
    """
    results = collect_results(category, lambda m: None, include_provisional=False)
    if not results or not category.standings:
        return None
    teams = [s.team for s in category.standings]
    official = {norm(s.team): s for s in category.standings}
    hits = {}
    for key, rule in RULES.items():
        rows = build_table(teams, results, rule=rule)
        hits[key] = sum(
            1 for r in rows
            if norm(r.team) in official and r.played and official[norm(r.team)].played == r.played
            and official[norm(r.team)].points == r.points
        )
    best = max(hits, key=hits.get)
    return best if hits[best] > min(hits.values()) else None


def points_system(category: Category) -> dict:
    """Puntuación que se aplica: la del admin, la que confirma la tabla oficial o la de la normativa."""
    chosen = category.points_system if category.points_system in RULES else None
    source = "admin"
    if not chosen:
        chosen, source = deduce_points_system(category), "official"
    if not chosen:
        chosen, source = default_points_system(category.name), "rules"
    return {"id": chosen, "label": POINTS_LABELS[chosen], "source": source, "source_label": POINTS_SOURCES[source]}


def points_rule(category: Category) -> PointsRule:
    return RULES[points_system(category)["id"]]


def collect_results(category: Category, provisional_for, include_provisional: bool) -> List[Result]:
    """Resultados de la categoría; `provisional_for(m)` es Ctx.provisional_for."""
    out: List[Result] = []
    for m in category.matches:
        if m.is_bye or not m.away:
            continue
        if m.home_sets is not None:
            out.append(_result(m, m.home_sets, m.away_sets, m.partials or [], False))
        elif include_provisional:
            p = provisional_for(m)
            if p:
                out.append(_result(m, p.home_sets, p.away_sets, p.partials or [], True))
    return sorted(out, key=lambda r: (r.round_no, _ts(r.starts_at), r.order))


def _result(m: Match, hs: int, as_: int, partials: list, provisional: bool) -> Result:
    return Result(m.round_no, m.round_name, m.order, m.starts_at, m.home, m.away, hs, as_, partials, provisional)


def _ts(dt: Optional[datetime]) -> float:
    if dt is None:
        return float("inf")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


# --- evolución ----------------------------------------------------------------

def evolution(category: Category, ours_key: Optional[str]) -> dict:
    """Posición y puntos de cada equipo al final de cada jornada (solo resultados oficiales)."""
    teams = [s.team for s in category.standings]
    results = collect_results(category, lambda m: None, include_provisional=False)
    rounds = sorted({r.round_no for r in results})
    names = {r.round_no: r.round_name for r in results}
    rule = points_rule(category)
    series: Dict[str, dict] = {}
    for rn in rounds:
        table = build_table(teams, [r for r in results if r.round_no <= rn], ours_key, rule)
        for pos, row in enumerate(table, start=1):
            s = series.setdefault(norm(row.team), {"team": row.team, "is_ours": row.is_ours, "positions": [], "points": []})
            s["positions"].append(pos)
            s["points"].append(row.points)
    final = build_table(teams, results, ours_key, rule) if results else []
    official = {norm(s.team): s for s in category.standings}
    approximate = any(
        norm(r.team) in official and (official[norm(r.team)].points, official[norm(r.team)].played) != (r.points, r.played)
        for r in final
    )
    return {
        "rounds": [{"round_no": rn, "round_name": names[rn]} for rn in rounds],
        "teams": list(series.values()),
        "approximate": approximate,
    }


# --- Ancares --------------------------------------------------------------------

def ours_stats(category: Category, ours_key: str, provisional_for) -> Optional[dict]:
    results = [r for r in collect_results(category, provisional_for, True) if ours_key in (norm(r.home), norm(r.away))]
    standing = next((s for s in category.standings if norm(s.team) == ours_key), None)
    base = {
        "team": standing.team if standing else None,
        "position": standing.position if standing else None,
        "points": standing.points if standing else None,
        "teams": len(category.standings),
    }
    if not results:
        return {**base, "played": 0}

    won = lost = sets_for = sets_against = pts_for = pts_against = sets_played = 0
    streak, best_streak, run = [], 0, 0
    longest = clearest = None
    for r in results:
        own, opp = r.sets_of(ours_key)
        pf, pa = r.points_of(ours_key)
        won += own > opp
        lost += own < opp
        sets_for += own
        sets_against += opp
        pts_for += pf
        pts_against += pa
        sets_played += len(r.partials)
        outcome = "W" if own > opp else "L" if own < opp else "D"
        run = run + 1 if outcome == "W" else 0
        best_streak = max(best_streak, run)
        rival = r.rival_of(ours_key)
        streak.append({"round_name": r.round_name, "rival": rival, "result": outcome,
                       "score": f"{own}-{opp}", "provisional": r.provisional})

        home = norm(r.home) == ours_key
        for p in r.partials:
            h, a = p[0], p[1]
            o, x = (h, a) if home else (a, h)
            if longest is None or o + x > longest["total"]:
                longest = {"total": o + x, "score": f"{o}-{x}", "rival": rival, "round_name": r.round_name}
        if outcome == "W":
            margin = (own - opp, pf - pa)
            if clearest is None or margin > clearest["margin"]:
                clearest = {"margin": margin, "score": f"{own}-{opp}", "rival": rival, "round_name": r.round_name,
                            "partials": " · ".join(f"{(p[0] if home else p[1])}-{(p[1] if home else p[0])}" for p in r.partials)}

    for item in (longest, clearest):
        if item:
            item.pop("total", None)
            item.pop("margin", None)
    total_sets = sets_for + sets_against
    return {
        **base,
        "played": len(results),
        "won": won,
        "lost": lost,
        "sets_for": sets_for,
        "sets_against": sets_against,
        "points_for": pts_for,
        "points_against": pts_against,
        "sets_won_pct": round(100 * sets_for / total_sets) if total_sets else None,
        "avg_points_per_set": round(pts_for / sets_played, 1) if sets_played else None,
        "streak": streak[-5:],
        "best_streak": best_streak,
        "longest_set": longest,
        "clearest_win": clearest,
        "has_provisional": any(r.provisional for r in results),
    }


# --- clasificación provisional ----------------------------------------------------

def not_yet_counted(category: Category, pending: List[Result]) -> List[Result]:
    """Quita los provisionales que la tabla oficial ya cuenta.

    A veces la clasificación de la FVCL ya incluye un partido cuyo resultado aún
    no trae el calendario (o que no se ha podido leer). Se nota porque esos dos
    equipos tienen en la tabla más partidos jugados que resultados oficiales en el
    calendario: ese partido ya está contado y no se suma otra vez.
    """
    official = Counter()
    for m in category.matches:
        if m.home_sets is not None and not m.is_bye and m.away:
            official[norm(m.home)] += 1
            official[norm(m.away)] += 1
    extra = {norm(s.team): s.played - official[norm(s.team)] for s in category.standings}
    keep = []
    for r in pending:
        h, a = norm(r.home), norm(r.away)
        if extra.get(h, 0) > 0 and extra.get(a, 0) > 0:
            extra[h] -= 1
            extra[a] -= 1
            continue
        keep.append(r)
    return keep


def _official_rows(category: Category, ours_key: Optional[str]) -> Dict[str, Row]:
    return {
        norm(s.team): Row(
            team=s.team, played=s.played, won=s.won, lost=s.lost, points=s.points,
            sets_for=s.sets_for, sets_against=s.sets_against, points_for=s.points_for,
            points_against=s.points_against, is_ours=norm(s.team) == ours_key, official_position=s.position,
        )
        for s in category.standings
    }


def _apply_all(rows: Dict[str, Row], results: Iterable[Result], rule: PointsRule) -> None:
    for r in results:
        for name in (r.home, r.away):
            if norm(name) in rows:
                rows[norm(name)].apply(r, rule)


def _table_out(table: List[Row]) -> List[dict]:
    return [
        {
            "position": pos,
            "team": row.team,
            "points": row.points,
            "played": row.played,
            "won": row.won,
            "lost": row.lost,
            "sets_for": row.sets_for,
            "sets_against": row.sets_against,
            "is_ours": row.is_ours,
            "delta": (row.official_position - pos) if row.official_position else 0,
        }
        for pos, row in enumerate(table, start=1)
    ]


def missing_from_table(category: Category) -> List[Result]:
    """Resultados oficiales del calendario que la clasificación de la FVCL aún no cuenta.

    Pasa si la federación publica los resultados pero no actualiza su
    clasificación (en octubre de 2026 su web daba error en todas). Se nota
    porque un equipo tiene más resultados oficiales en el calendario que
    partidos jugados en la tabla; los que faltan son los más recientes.
    """
    if not category.standings:
        return []
    results = collect_results(category, lambda m: None, include_provisional=False)
    counts = Counter()
    for r in results:
        counts[norm(r.home)] += 1
        counts[norm(r.away)] += 1
    pending = {norm(s.team): counts[norm(s.team)] - s.played for s in category.standings}
    if not any(v > 0 for v in pending.values()):
        return []
    out = []
    for r in reversed(results):
        h, a = norm(r.home), norm(r.away)
        if pending.get(h, 0) > 0 and pending.get(a, 0) > 0:
            pending[h] -= 1
            pending[a] -= 1
            out.append(r)
    return list(reversed(out))


def updated_table(category: Category, ours_key: Optional[str]) -> Optional[List[dict]]:
    """Clasificación oficial + los resultados oficiales que la FVCL aún no ha sumado.

    Se parte de la tabla de la federación (así se respetan sus ajustes, como una
    sanción) y se suman con la puntuación de la normativa. Orden de la RFEVB:
    puntos, victorias, cociente de sets y de puntos; si todo empata, el oficial.
    """
    missing = missing_from_table(category)
    if not missing:
        return None
    rows = _official_rows(category, ours_key)
    _apply_all(rows, missing, points_rule(category))
    table = sorted(rows.values(), key=lambda row: (
        -row.points, -row.won, -_ratio(row.sets_for, row.sets_against),
        -_ratio(row.points_for, row.points_against), row.official_position or 999, norm(row.team),
    ))
    return _table_out(table)


def provisional_table(category: Category, ours_key: Optional[str], provisional_for) -> Optional[List[dict]]:
    """Tabla oficial (más lo que la FVCL aún no haya sumado) + resultados provisionales, reordenada."""
    pending = [r for r in collect_results(category, provisional_for, True) if r.provisional]
    pending = not_yet_counted(category, pending)
    if not pending:
        return None
    rule = points_rule(category)
    rows = _official_rows(category, ours_key)
    _apply_all(rows, missing_from_table(category), rule)
    _apply_all(rows, pending, rule)
    # A igualdad de puntos se respeta el orden oficial: así solo se mueve quien
    # suma puntos (y a quien adelanta), sin aplicar desempates que pueden no ser
    # exactamente los de la federación.
    table = sorted(rows.values(), key=lambda row: (-row.points, row.official_position or 999, norm(row.team)))
    return _table_out(table)


def ours_key_of(category: Category, is_ours) -> Optional[str]:
    standing: Optional[Standing] = next((s for s in category.standings if s.is_ours), None)
    if standing:
        return norm(standing.team)
    m = next((m for m in category.matches if m.is_ours and not m.is_bye), None)
    if not m:
        return None
    return norm(m.home if is_ours(m.home) else m.away)
