from dataclasses import dataclass, field
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .models import Category, LiveScore, Match, ProvisionalResult, Standing
from .parsers.common import norm
from .scoring_format import format_of
from .services.cheers import summary as cheer_summary
from .services.stats import missing_from_table, points_system, updated_table
from .services.live import live_id, summary as live_summary
from .services.provisional import Key, match_key

Logos = Dict[str, str]  # nombre normalizado -> URL del logo


@dataclass
class Ctx:
    """Datos auxiliares para serializar: logos, resultados provisionales, ánimos y directos."""

    logos: Logos = field(default_factory=dict)
    provisional: Dict[Key, ProvisionalResult] = field(default_factory=dict)
    cheers: Dict[Key, Dict[str, int]] = field(default_factory=dict)
    live: Dict[Key, LiveScore] = field(default_factory=dict)
    _rounds: Dict[int, Dict[int, datetime]] = field(default_factory=dict)

    def rounds_for(self, category: Category) -> Dict[int, datetime]:
        """Fecha típica de cada jornada de la categoría (se calcula una vez por petición)."""
        if self is EMPTY:  # el contexto vacío es compartido: sin memoria
            return round_dates(category.matches)
        if category.id not in self._rounds:
            self._rounds[category.id] = round_dates(category.matches)
        return self._rounds[category.id]

    def logo(self, name: Optional[str]) -> Optional[str]:
        return self.logos.get(norm(name)) if name else None

    def provisional_for(self, m: Match) -> Optional[ProvisionalResult]:
        # El oficial manda: con resultado de la FVCL, el provisional se ignora
        if m.home_sets is not None or m.is_bye:
            return None
        return self.provisional.get(match_key(m))


EMPTY = Ctx()


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite devuelve datetimes sin zona: se guardan en UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def standing_out(s: Standing, ctx: Ctx = EMPTY) -> dict:
    return {
        "position": s.position,
        "team": s.team,
        "logo": ctx.logo(s.team),
        "points": s.points,
        "played": s.played,
        "won": s.won,
        "lost": s.lost,
        "sets_for": s.sets_for,
        "sets_against": s.sets_against,
        "points_for": s.points_for,
        "points_against": s.points_against,
        "promotion": s.promotion,
        "is_ours": s.is_ours,
    }


def provisional_out(p: ProvisionalResult) -> dict:
    return {
        "home_sets": p.home_sets,
        "away_sets": p.away_sets,
        "partials": p.partials or [],
        "finished_early": p.finished_early,
        "by": p.published_by,
        "updated_at": iso(p.updated_at),
    }


def match_out(m: Match, ctx: Ctx = EMPTY) -> dict:
    prov = ctx.provisional_for(m)
    ours = m.is_ours and not m.is_bye
    league = ours and m.category is not None and not m.category.is_tournament
    rounds = ctx.rounds_for(m.category) if league else {}
    twin = swapped_with(m, m.category.matches, rounds) if league else None
    key = match_key(m)
    return {
        "id": m.id,
        "category_id": m.category_id,
        "round_no": m.round_no,
        "round_name": m.round_name,
        "home": m.home,
        "away": m.away,
        "home_logo": ctx.logo(m.home),
        "away_logo": ctx.logo(m.away),
        "is_bye": m.is_bye,
        "starts_at": iso(m.starts_at),
        "venue": m.venue,
        "home_sets": m.home_sets,
        "away_sets": m.away_sets,
        "partials": m.partials or [],
        "played": m.home_sets is not None,
        "is_ours": m.is_ours,
        "provisional": provisional_out(prov) if prov else None,
        "tournament": bool(m.category and m.category.is_tournament),
        "cheers": cheer_summary(ctx.cheers.get(key, {}), m) if ours else None,
        # Marcador en directo: id para el visor y resumen si alguien lo está retransmitiendo
        "live_id": live_id(m) if ours else None,
        "live": live_summary(ctx.live.get(key)) if ours and m.home_sets is None else None,
        "schedule_override": bool(m.schedule_override),  # horario cambiado a mano por el club
        # «adelantada»/«aplazada» si no se juega con el resto de su jornada (ligas)
        "round_shift": ("aplazada" if twin else round_shift(m, rounds)) if league else None,
        # Cambio de orden de vueltas: «Jornada 11» si este partido pasa al hueco de esa jornada
        "swap_round": twin.round_name if twin else None,
    }


SHIFT = timedelta(days=5)  # margen para decir que un partido no se juega con el resto de su jornada


def round_dates(matches: List[Match]) -> Dict[int, datetime]:
    """Fecha típica (mediana) de cada jornada, con los partidos de todos los equipos que ya tienen fecha."""
    by_round: Dict[int, List[datetime]] = {}
    for m in matches:
        if not m.is_bye and m.away and m.starts_at:
            by_round.setdefault(m.round_no, []).append(_aware(m.starts_at))
    return {r: sorted(ds)[len(ds) // 2] for r, ds in by_round.items()}


def swapped_with(m: Match, matches: List[Match], rounds: Dict[int, datetime]) -> Optional[Match]:
    """Partido de vuelta que se juega en la fecha de esta jornada (la FVCL cambió el orden de las vueltas).

    Ejemplo: el Ancares – AULE de la jornada 11 se juega en la fecha de la
    jornada 2, y el AULE – Ancares de la jornada 2 queda sin fecha: pasa al
    hueco de la jornada 11.
    """
    typical = rounds.get(m.round_no)
    if m.starts_at or m.is_bye or not m.away or typical is None:
        return None
    for o in matches:
        if (o is not m and not o.is_bye and o.away and o.starts_at and o.round_no in rounds
                and norm(o.home) == norm(m.away) and norm(o.away) == norm(m.home)
                and abs(_aware(o.starts_at) - typical) <= SHIFT):
            return o
    return None


def expected_at(m: Match, matches: List[Match], rounds: Dict[int, datetime]) -> Optional[datetime]:
    """Cuándo se espera un partido: su fecha o, si aún no tiene, la de su jornada (o la de la vuelta si se cambiaron)."""
    if m.starts_at:
        return _aware(m.starts_at)
    twin = swapped_with(m, matches, rounds)
    return rounds[twin.round_no] if twin else rounds.get(m.round_no)


def round_shift(m: Match, rounds: Dict[int, datetime], now: Optional[datetime] = None,
                matches: Optional[List[Match]] = None) -> Optional[str]:
    """«adelantada» o «aplazada» si el partido no se juega cuando el resto de su jornada.

    Pasa, por ejemplo, cuando la federación cambia el orden de las vueltas: el
    Ancares – AULE de la jornada 11 se juega en octubre (adelantada) y el AULE –
    Ancares de la jornada 2 pasa al hueco de la 11 (aplazada).
    """
    typical = rounds.get(m.round_no)
    if m.is_bye or not m.away or typical is None:
        return None
    if not m.starts_at and matches is not None and swapped_with(m, matches, rounds):
        return "aplazada"
    if m.starts_at:
        when = _aware(m.starts_at)
        if when < typical - SHIFT:
            return "adelantada"
        if when > typical + SHIFT:
            return "aplazada"
        return None
    if m.home_sets is None and typical < (now or datetime.now(timezone.utc)) - timedelta(days=1):
        return "aplazada"  # el resto de la jornada ya se jugó y este sigue sin fecha
    return None


def upcoming(matches: List[Match], ctx: Ctx = EMPTY, limit: int = 2, now: Optional[datetime] = None) -> List[Match]:
    """Próximos partidos de Ancares sin jugar (incluye el que se está jugando ahora).

    Van por fecha. Los que aún no tienen (la federación no la ha fijado) se
    colocan en la fecha típica de su jornada (la del resto de partidos) o, si la
    FVCL cambió el orden de las vueltas, en la de la jornada de la vuelta; si esa
    fecha ya pasó, están aplazados sin fecha y no se proponen. Si toda la jornada
    está sin fecha, se colocan por número de jornada entre los demás. Un partido
    con resultado (oficial o provisional) o cuya fecha ya pasó se da por jugado.
    Lo que se está retransmitiendo en directo va siempre primero, aunque el
    Excel diga otro día.
    """
    now = now or datetime.now(timezone.utc)
    recent = now - timedelta(hours=3)
    ours = [m for m in matches if m.is_ours and not m.is_bye]
    rounds = round_dates(matches)

    def on_air(m: Match) -> bool:
        s = live_summary(ctx.live.get(match_key(m)), now) if m.home_sets is None and not ctx.provisional_for(m) else None
        return bool(s and s["on"])

    def played(m: Match) -> bool:
        return m.home_sets is not None or ctx.provisional_for(m) is not None or bool(m.starts_at and _aware(m.starts_at) < recent)

    live_now = [m for m in ours if on_air(m)]
    ours = [m for m in ours if m not in live_now]
    played_round = max((m.round_no for m in ours if played(m)), default=0)
    timed: List[tuple] = []  # (fecha o fecha prevista, partido)
    unknown: List[Match] = []  # sin fecha y sin pista de cuándo
    for m in ours:
        if played(m):
            continue
        if m.starts_at:
            timed.append((_aware(m.starts_at), m))
        elif m.round_no in rounds:
            # Sin fecha: cuando el resto de su jornada o, si se cambió el orden de las
            # vueltas, en el hueco de la vuelta. Si esa fecha ya pasó, aplazado sin fecha.
            when = expected_at(m, matches, rounds)
            if when >= now - timedelta(days=1):
                timed.append((when, m))
        elif m.round_no > played_round:
            unknown.append(m)
    timed.sort(key=lambda t: (t[0], t[1].round_no, t[1].order))
    unknown.sort(key=lambda m: (m.round_no, m.order))
    out: List[Match] = list(live_now)
    for _, d in timed:
        while unknown and unknown[0].round_no < d.round_no:
            out.append(unknown.pop(0))
        out.append(d)
    return (out + unknown)[:limit]


def next_match(matches: List[Match], ctx: Ctx = EMPTY, now: Optional[datetime] = None) -> Optional[Match]:
    nxt = upcoming(matches, ctx, 1, now)
    return nxt[0] if nxt else None


def last_result(matches: List[Match], ctx: Ctx = EMPTY) -> Optional[Match]:
    """Último partido de Ancares con resultado, oficial o provisional."""
    played = [m for m in matches if m.is_ours and (m.home_sets is not None or ctx.provisional_for(m))]
    if not played:
        return None
    return max(played, key=lambda m: (m.round_no, _aware(m.starts_at) or datetime.min.replace(tzinfo=timezone.utc), m.order))


def _updated(c: Category) -> Optional[List[dict]]:
    """Clasificación con los resultados oficiales que la FVCL aún no ha sumado (o None si está al día)."""
    if c.is_tournament:
        return None
    ours = next((norm(s.team) for s in c.standings if s.is_ours), None)
    return updated_table(c, ours)


def category_summary(c: Category, ctx: Ctx = EMPTY) -> dict:
    ours = next((s for s in c.standings if s.is_ours), None)
    updated = _updated(c)
    if updated and ours:  # la posición de Ancares, con los resultados que la FVCL aún no ha sumado
        row = next((r for r in updated if r["is_ours"]), None)
        if row:
            ours = SimpleNamespace(team=ours.team, position=row["position"], points=row["points"])
    coming = upcoming(c.matches, ctx, 2)
    nm = coming[0] if coming else None
    am = coming[1] if len(coming) > 1 else None
    lr = last_result(c.matches, ctx)
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "teams": len(c.standings),
        "our_team": ours.team if ours else None,
        "our_position": ours.position if ours else None,
        "our_points": ours.points if ours else None,
        "next_match": match_out(nm, ctx) if nm else None,
        "after_match": match_out(am, ctx) if am else None,
        "last_result": match_out(lr, ctx) if lr else None,
        "score_format": format_of(c.score_format),
        "kind": c.kind or "league",
        "points_system": points_system(c),  # la puntuación que se aplica y de dónde sale
        "updated_at": iso(c.data_updated_at),  # último cambio real en los datos
        "checked_at": iso(c.last_sync_at),  # última comprobación con la FVCL
    }


def category_detail(c: Category, ctx: Ctx = EMPTY) -> dict:
    data = category_summary(c, ctx)
    data["standings"] = [standing_out(s, ctx) for s in c.standings]
    updated = _updated(c)
    if updated:
        for row in updated:
            row["logo"] = ctx.logo(row["team"])
        missing = missing_from_table(c)
        data["standings_updated"] = updated
        data["standings_missing"] = {
            "results": len(missing),
            "rounds": list(dict.fromkeys(r.round_name for r in missing)),
        }
    else:
        data["standings_updated"] = None
        data["standings_missing"] = None
    data["matches"] = [match_out(m, ctx) for m in c.matches]
    if c.is_tournament:
        from .services.tournament import group_tables

        data["groups"] = group_tables(c, ctx.provisional_for, ctx.logo)
    return data


def category_admin(c: Category) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "fvcl_name": c.fvcl_name,
        "ranking_url": c.ranking_url,
        "calendar_url": c.calendar_url,
        "sort_order": c.sort_order,
        "active": c.active,
        "score_format": format_of(c.score_format),
        "kind": c.kind or "league",
        "points_system": c.points_system or "auto",
        "points_applied": points_system(c),
        "sync_status": c.sync_status,
        "last_error": c.last_error,
        "last_sync_at": iso(c.last_sync_at),
        "updated_at": iso(c.data_updated_at),
        "teams": len(c.standings),
        "matches": len(c.matches),
    }
