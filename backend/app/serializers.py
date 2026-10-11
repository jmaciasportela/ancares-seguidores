from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from .models import Category, Match, ProvisionalResult, Standing
from .parsers.common import norm
from .scoring_format import format_of
from .services.provisional import Key, match_key

Logos = Dict[str, str]  # nombre normalizado -> URL del logo


@dataclass
class Ctx:
    """Datos auxiliares para serializar: logos y resultados provisionales."""

    logos: Logos = field(default_factory=dict)
    provisional: Dict[Key, ProvisionalResult] = field(default_factory=dict)

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
    }


def next_match(matches: List[Match], ctx: Ctx = EMPTY, now: Optional[datetime] = None) -> Optional[Match]:
    """Próximo partido de Ancares sin jugar (incluye el que se está jugando ahora).

    Un partido con resultado provisional ya se ha jugado: no es el próximo.
    """
    now = now or datetime.now(timezone.utc)
    pending = [m for m in matches if m.is_ours and not m.is_bye and m.home_sets is None and not ctx.provisional_for(m)]
    dated = [m for m in pending if m.starts_at and _aware(m.starts_at) >= now - timedelta(hours=3)]
    if dated:
        return min(dated, key=lambda m: _aware(m.starts_at))
    # Sin fecha: el de la jornada más baja posterior al último jugado
    last = last_result(matches, ctx)
    after = [m for m in pending if not m.starts_at and (last is None or m.round_no > last.round_no)]
    return min(after, key=lambda m: (m.round_no, m.order)) if after else None


def last_result(matches: List[Match], ctx: Ctx = EMPTY) -> Optional[Match]:
    """Último partido de Ancares con resultado, oficial o provisional."""
    played = [m for m in matches if m.is_ours and (m.home_sets is not None or ctx.provisional_for(m))]
    if not played:
        return None
    return max(played, key=lambda m: (m.round_no, _aware(m.starts_at) or datetime.min.replace(tzinfo=timezone.utc), m.order))


def category_summary(c: Category, ctx: Ctx = EMPTY) -> dict:
    ours = next((s for s in c.standings if s.is_ours), None)
    nm, lr = next_match(c.matches, ctx), last_result(c.matches, ctx)
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "teams": len(c.standings),
        "our_team": ours.team if ours else None,
        "our_position": ours.position if ours else None,
        "our_points": ours.points if ours else None,
        "next_match": match_out(nm, ctx) if nm else None,
        "last_result": match_out(lr, ctx) if lr else None,
        "score_format": format_of(c.score_format),
        "updated_at": iso(c.data_updated_at),
    }


def category_detail(c: Category, ctx: Ctx = EMPTY) -> dict:
    data = category_summary(c, ctx)
    data["standings"] = [standing_out(s, ctx) for s in c.standings]
    data["matches"] = [match_out(m, ctx) for m in c.matches]
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
        "sync_status": c.sync_status,
        "last_error": c.last_error,
        "last_sync_at": iso(c.last_sync_at),
        "updated_at": iso(c.data_updated_at),
        "teams": len(c.standings),
        "matches": len(c.matches),
    }
