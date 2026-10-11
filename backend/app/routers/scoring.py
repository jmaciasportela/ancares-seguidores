"""Marcador: códigos de anotador, partidos para anotar y resultados provisionales."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import RateLimiter, clear_scorer_session, hash_code, is_admin, scorer_id_from, set_scorer_session
from ..db import get_session
from ..models import Category, ProvisionalResult, Scorer, utcnow
from ..parsers.common import norm
from ..schemas import ProvisionalIn, ScorerJoinIn
from ..scoring_format import ResultError, format_of, validate_partials
from ..serializers import Ctx, _aware, match_out, provisional_out
from ..services.logos import logo_map
from ..services.provisional import prov_key, provisional_map

router = APIRouter(prefix="/api", tags=["scoring"])
join_limiter = RateLimiter(limit=10, window=900)
WINDOW = timedelta(days=2)


@dataclass
class Publisher:
    scorer: Optional[Scorer]
    name: str


def current_scorer(request: Request, session: Session) -> Optional[Scorer]:
    sid = scorer_id_from(request)
    scorer = session.get(Scorer, sid) if sid else None
    return scorer if scorer and scorer.active else None


def require_publisher(request: Request, session: Session = Depends(get_session)) -> Publisher:
    """Puede publicar el admin o un anotador activo (revocarlo lo corta al instante)."""
    if is_admin(request):
        return Publisher(None, "Admin")
    scorer = current_scorer(request, session)
    if not scorer:
        raise HTTPException(status_code=401, detail="Necesitas un código de anotador para publicar resultados")
    return Publisher(scorer, scorer.name)


# --- código de anotador -------------------------------------------------------

@router.post("/scorer/join")
def join(data: ScorerJoinIn, request: Request, response: Response, session: Session = Depends(get_session)):
    join_limiter.check(request)
    scorer = session.scalars(select(Scorer).where(Scorer.code_hash == hash_code(data.code))).first()
    if not scorer or not scorer.active:
        raise HTTPException(status_code=401, detail="Código no válido")
    scorer.last_used_at = utcnow()
    session.commit()
    set_scorer_session(response, scorer.id)
    return {"scorer": True, "name": scorer.name}


@router.get("/scorer/me")
def me(request: Request, session: Session = Depends(get_session)):
    scorer = current_scorer(request, session)
    admin = is_admin(request)
    return {
        "scorer": bool(scorer),
        "name": scorer.name if scorer else ("Admin" if admin else None),
        "admin": admin,
        "can_publish": bool(scorer) or admin,
    }


@router.post("/scorer/logout")
def logout(response: Response):
    clear_scorer_session(response)
    return {"ok": True}


# --- partidos para anotar -----------------------------------------------------

@router.get("/scoring/matches")
def scoring_matches(session: Session = Depends(get_session)):
    """Partidos de Ancares sin resultado oficial en ±2 días, del más cercano a ahora al más lejano."""
    now = datetime.now(timezone.utc)
    cats = session.scalars(
        select(Category).where(Category.active.is_(True)).options(selectinload(Category.matches))
    ).all()
    ctx = Ctx(logos=logo_map(session), provisional=provisional_map(session))
    items = []
    for cat in cats:
        for m in cat.matches:
            if not m.is_ours or m.is_bye or m.home_sets is not None or not m.away or not m.starts_at:
                continue
            delta = _aware(m.starts_at) - now
            if abs(delta) > WINDOW:
                continue
            item = match_out(m, ctx)
            item.update(
                category=cat.name,
                category_slug=cat.slug,
                score_format=format_of(cat.score_format),
                minutes_from_now=round(delta.total_seconds() / 60),
            )
            items.append(item)
    items.sort(key=lambda i: abs(i["minutes_from_now"]))
    return items


# --- publicar ---------------------------------------------------------------

@router.post("/scoring/results")
def publish(data: ProvisionalIn, who: Publisher = Depends(require_publisher), session: Session = Depends(get_session)):
    cat = session.get(Category, data.category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    key = prov_key(cat.id, data.round_no, data.home, data.away)
    match = next((m for m in cat.matches if (m.category_id, m.round_no, norm(m.home), norm(m.away)) == key), None)
    if not match or match.is_bye:
        raise HTTPException(status_code=404, detail="No encuentro ese partido en el calendario")
    if not match.is_ours:
        raise HTTPException(status_code=422, detail="Solo se pueden publicar partidos de Ancares")
    if match.home_sets is not None:
        raise HTTPException(status_code=409, detail="La federación ya ha publicado el resultado oficial de este partido")
    try:
        partials = validate_partials(
            [list(p) for p in data.partials], data.home_sets, data.away_sets, data.finished_early
        )
    except ResultError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    prov = session.scalars(
        select(ProvisionalResult).where(
            ProvisionalResult.category_id == key[0],
            ProvisionalResult.round_no == key[1],
            ProvisionalResult.home_key == key[2],
            ProvisionalResult.away_key == key[3],
        )
    ).first()
    if not prov:
        prov = ProvisionalResult(
            category_id=cat.id, round_no=match.round_no, home=match.home, away=match.away,
            home_key=key[2], away_key=key[3],
        )
        session.add(prov)
    prov.home_sets, prov.away_sets = data.home_sets, data.away_sets
    prov.partials = partials
    prov.finished_early = data.finished_early
    prov.scorer_id = who.scorer.id if who.scorer else None
    prov.published_by = who.name
    prov.updated_at = utcnow()
    if who.scorer:
        who.scorer.last_used_at = utcnow()
    session.commit()
    return {"ok": True, "provisional": provisional_out(prov), "category_slug": cat.slug}
