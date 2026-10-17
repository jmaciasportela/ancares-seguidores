from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .models import Category, LiveScore, Match, ProvisionalResult, Standing
from .parsers.common import norm
from .scoring_format import format_of
from .services.cheers import summary as cheer_summary
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
    }


def upcoming(matches: List[Match], ctx: Ctx = EMPTY, limit: int = 2, now: Optional[datetime] = None) -> List[Match]:
    """Próximos partidos de Ancares sin jugar (incluye el que se está jugando ahora).

    Los que tienen fecha van por orden de fecha. Los que aún no la tienen (la
    federación no la ha fijado) se colocan por jornada entre ellos: uno sin fecha
    de la jornada 2 va antes que otro con fecha de la jornada 11. Un partido con
    resultado (oficial o provisional) o cuya fecha ya pasó se da por jugado, y los
    sin fecha de jornadas ya superadas se descartan. Lo que se está retransmitiendo
    en directo va siempre primero, aunque el Excel diga otro día.
    """
    now = now or datetime.now(timezone.utc)
    recent = now - timedelta(hours=3)
    ours = [m for m in matches if m.is_ours and not m.is_bye]

    def on_air(m: Match) -> bool:
        s = live_summary(ctx.live.get(match_key(m)), now) if m.home_sets is None and not ctx.provisional_for(m) else None
        return bool(s and s["on"])

    def played(m: Match) -> bool:
        return m.home_sets is not None or ctx.provisional_for(m) is not None or bool(m.starts_at and _aware(m.starts_at) < recent)

    live_now = [m for m in ours if on_air(m)]
    ours = [m for m in ours if m not in live_now]
    played_round = max((m.round_no for m in ours if played(m)), default=0)
    pending = [m for m in ours if not played(m)]
    dated = sorted((m for m in pending if m.starts_at), key=lambda m: _aware(m.starts_at))
    undated = sorted((m for m in pending if not m.starts_at and m.round_no > played_round), key=lambda m: (m.round_no, m.order))
    out: List[Match] = list(live_now)
    for d in dated:
        while undated and undated[0].round_no < d.round_no:
            out.append(undated.pop(0))
        out.append(d)
    return (out + undated)[:limit]


def next_match(matches: List[Match], ctx: Ctx = EMPTY, now: Optional[datetime] = None) -> Optional[Match]:
    nxt = upcoming(matches, ctx, 1, now)
    return nxt[0] if nxt else None


def last_result(matches: List[Match], ctx: Ctx = EMPTY) -> Optional[Match]:
    """Último partido de Ancares con resultado, oficial o provisional."""
    played = [m for m in matches if m.is_ours and (m.home_sets is not None or ctx.provisional_for(m))]
    if not played:
        return None
    return max(played, key=lambda m: (m.round_no, _aware(m.starts_at) or datetime.min.replace(tzinfo=timezone.utc), m.order))


def category_summary(c: Category, ctx: Ctx = EMPTY) -> dict:
    ours = next((s for s in c.standings if s.is_ours), None)
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
        "updated_at": iso(c.data_updated_at),  # último cambio real en los datos
        "checked_at": iso(c.last_sync_at),  # última comprobación con la FVCL
    }


def category_detail(c: Category, ctx: Ctx = EMPTY) -> dict:
    data = category_summary(c, ctx)
    data["standings"] = [standing_out(s, ctx) for s in c.standings]
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
        "sync_status": c.sync_status,
        "last_error": c.last_error,
        "last_sync_at": iso(c.last_sync_at),
        "updated_at": iso(c.data_updated_at),
        "teams": len(c.standings),
        "matches": len(c.matches),
    }
