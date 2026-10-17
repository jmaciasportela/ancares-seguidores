import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..config import get_settings
from ..models import Category, Match, competition_order
from ..serializers import Ctx, category_detail, category_summary, iso
from ..services.logos import logo_map
from ..services.provisional import provisional_map
from ..auth import RateLimiter
from ..schemas import CheerIn, PingIn
from ..services import cheers, stats, usage
from ..services.provisional import match_key, prov_key
from ..services.importer import is_ours
from ..services.weather import forecast_for

router = APIRouter(prefix="/api", tags=["public"])
ping_limiter = RateLimiter(limit=120, window=3600)
cheer_limiter = RateLimiter(limit=240, window=60)


def cached_json(request: Request, payload) -> Response:
    """JSON con ETag: si el móvil ya tiene la versión, responde 304 sin cuerpo."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    etag = '"' + hashlib.sha1(body).hexdigest()[:20] + '"'
    # no-cache: el navegador revalida siempre (un 304 cuesta casi nada) y los
    # resultados provisionales recién publicados se ven al momento
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def make_ctx(session: Session) -> Ctx:
    return Ctx(logos=logo_map(session), provisional=provisional_map(session), cheers=cheers.totals_map(session))


def _active(session: Session):
    return session.scalars(
        select(Category)
        .where(Category.active.is_(True))
        .order_by(*competition_order())
        .options(selectinload(Category.standings), selectinload(Category.matches))
    ).all()


@router.get("/home")
def home(request: Request, session: Session = Depends(get_session)):
    cats = _active(session)
    updated = max((c.data_updated_at for c in cats if c.data_updated_at), default=None)
    checked = max((c.last_sync_at for c in cats if c.last_sync_at), default=None)
    ctx = make_ctx(session)
    return cached_json(request, {
        "categories": [category_summary(c, ctx) for c in cats],
        "updated_at": iso(updated),  # últimas novedades reales
        "checked_at": iso(checked),  # última comprobación
    })


@router.get("/categories")
def categories(request: Request, session: Session = Depends(get_session)):
    ctx = make_ctx(session)
    return cached_json(request, [category_summary(c, ctx) for c in _active(session)])


@router.get("/categories/{slug}")
def category(slug: str, request: Request, session: Session = Depends(get_session)):
    cat = session.scalars(
        select(Category)
        .where(Category.slug == slug, Category.active.is_(True))
        .options(selectinload(Category.standings), selectinload(Category.matches))
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return cached_json(request, category_detail(cat, make_ctx(session)))


@router.get("/categories/{slug}/stats")
def category_stats(slug: str, request: Request, session: Session = Depends(get_session)):
    cat = session.scalars(
        select(Category)
        .where(Category.slug == slug, Category.active.is_(True))
        .options(selectinload(Category.standings), selectinload(Category.matches))
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    ctx = make_ctx(session)
    key = stats.ours_key_of(cat, is_ours)
    evo = stats.evolution(cat, key)
    for t in evo["teams"]:
        t["logo"] = ctx.logo(t["team"])
    prov = stats.provisional_table(cat, key, ctx.provisional_for)
    if prov:
        for row in prov:
            row["logo"] = ctx.logo(row["team"])
    return cached_json(request, {
        **evo,
        "ours": stats.ours_stats(cat, key, ctx.provisional_for) if key else None,
        "provisional_table": prov,
    })


@router.get("/weather/{match_id}")
def weather(match_id: int, session: Session = Depends(get_session)):
    """Previsión del tiempo a la hora del partido (con caché: no hace falta pedirla a menudo)."""
    m = session.get(Match, match_id)
    if not m or m.is_bye:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    if not get_settings().weather_enabled:
        data = {"available": False, "reason": "disabled"}
    elif not m.starts_at:
        data = {"available": False, "reason": "no_date"}
    else:
        data = forecast_for(m.starts_at, m.venue, m.home)
    return Response(
        json.dumps(data, ensure_ascii=False),
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.post("/ping", status_code=204)
def ping(data: PingIn, request: Request, session: Session = Depends(get_session)):
    """Aviso anónimo de uso (ver services/usage.py). No guarda IPs ni datos personales."""
    ping_limiter.check(request)
    usage.record_ping(session, data.device, data.installed, data.platform, data.version)
    return Response(status_code=204)


@router.post("/cheers")
def cheer(data: CheerIn, request: Request, session: Session = Depends(get_session)):
    """Ánimos anónimos para un partido de Ancares (frases predefinidas, sin texto libre)."""
    cheer_limiter.check(request)
    cat = session.get(Category, data.category_id)
    key = prov_key(data.category_id, data.round_no, data.home, data.away)
    m = next((x for x in (cat.matches if cat else []) if match_key(x) == key), None)
    if not m:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    try:
        return cheers.add(session, m, data.kind, data.n, usage.device_key(data.device))
    except cheers.CheerError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
