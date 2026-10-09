from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .models import Category, Match, Standing


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


def standing_out(s: Standing) -> dict:
    return {
        "position": s.position,
        "team": s.team,
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


def match_out(m: Match) -> dict:
    return {
        "id": m.id,
        "round_no": m.round_no,
        "round_name": m.round_name,
        "home": m.home,
        "away": m.away,
        "is_bye": m.is_bye,
        "starts_at": iso(m.starts_at),
        "venue": m.venue,
        "home_sets": m.home_sets,
        "away_sets": m.away_sets,
        "partials": m.partials or [],
        "played": m.home_sets is not None,
        "is_ours": m.is_ours,
    }


def next_match(matches: List[Match], now: Optional[datetime] = None) -> Optional[Match]:
    """Próximo partido de Ancares sin jugar (incluye el que se está jugando ahora)."""
    now = now or datetime.now(timezone.utc)
    pending = [m for m in matches if m.is_ours and not m.is_bye and m.home_sets is None]
    dated = [m for m in pending if m.starts_at and _aware(m.starts_at) >= now - timedelta(hours=3)]
    if dated:
        return min(dated, key=lambda m: _aware(m.starts_at))
    # Sin fecha: el de la jornada más baja posterior al último jugado
    last = last_result(matches)
    after = [m for m in pending if not m.starts_at and (last is None or m.round_no > last.round_no)]
    return min(after, key=lambda m: (m.round_no, m.order)) if after else None


def last_result(matches: List[Match]) -> Optional[Match]:
    played = [m for m in matches if m.is_ours and m.home_sets is not None]
    if not played:
        return None
    return max(played, key=lambda m: (m.round_no, _aware(m.starts_at) or datetime.min.replace(tzinfo=timezone.utc), m.order))


def category_summary(c: Category) -> dict:
    ours = next((s for s in c.standings if s.is_ours), None)
    nm, lr = next_match(c.matches), last_result(c.matches)
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "teams": len(c.standings),
        "our_team": ours.team if ours else None,
        "our_position": ours.position if ours else None,
        "our_points": ours.points if ours else None,
        "next_match": match_out(nm) if nm else None,
        "last_result": match_out(lr) if lr else None,
        "updated_at": iso(c.data_updated_at),
    }


def category_detail(c: Category) -> dict:
    data = category_summary(c)
    data["standings"] = [standing_out(s) for s in c.standings]
    data["matches"] = [match_out(m) for m in c.matches]
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
        "sync_status": c.sync_status,
        "last_error": c.last_error,
        "last_sync_at": iso(c.last_sync_at),
        "updated_at": iso(c.data_updated_at),
        "teams": len(c.standings),
        "matches": len(c.matches),
    }
