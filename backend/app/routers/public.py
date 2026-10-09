import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..models import Category
from ..serializers import category_detail, category_summary, iso
from ..services.logos import logo_map

router = APIRouter(prefix="/api", tags=["public"])


def cached_json(request: Request, payload) -> Response:
    """JSON con ETag: si el móvil ya tiene la versión, responde 304 sin cuerpo."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    etag = '"' + hashlib.sha1(body).hexdigest()[:20] + '"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=60, stale-while-revalidate=600"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def _active(session: Session):
    return session.scalars(
        select(Category)
        .where(Category.active.is_(True))
        .order_by(Category.sort_order, Category.name)
        .options(selectinload(Category.standings), selectinload(Category.matches))
    ).all()


@router.get("/home")
def home(request: Request, session: Session = Depends(get_session)):
    cats = _active(session)
    updated = max((c.data_updated_at for c in cats if c.data_updated_at), default=None)
    logos = logo_map(session)
    return cached_json(request, {"categories": [category_summary(c, logos) for c in cats], "updated_at": iso(updated)})


@router.get("/categories")
def categories(request: Request, session: Session = Depends(get_session)):
    logos = logo_map(session)
    return cached_json(request, [category_summary(c, logos) for c in _active(session)])


@router.get("/categories/{slug}")
def category(slug: str, request: Request, session: Session = Depends(get_session)):
    cat = session.scalars(
        select(Category)
        .where(Category.slug == slug, Category.active.is_(True))
        .options(selectinload(Category.standings), selectinload(Category.matches))
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return cached_json(request, category_detail(cat, logo_map(session)))
