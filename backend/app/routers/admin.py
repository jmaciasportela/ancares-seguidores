import re
from pathlib import PurePath
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import RateLimiter, check_password, clear_session, is_admin, require_admin, set_session
from ..db import get_session
from ..models import Category, Feedback, Standing, SyncLog, Team, utcnow
from ..parsers.common import ParseError, norm
from ..schemas import CategoryIn, FeedbackPatch, LoginIn, LogoSearchIn, LogoUrlIn, SyncIn
from ..serializers import category_admin, iso
from ..services.fetcher import make_client
from ..services.importer import import_file, is_ours, sniff_kind
from ..services.logos import (
    MAX_IMAGE_BYTES,
    LogoError,
    download_image,
    logo_url,
    remove_logo_file,
    save_logo,
    sync_teams_from_standings,
)
from ..services.logos_fvcl import search_category_logos
from ..services.sync import sync_categories

router = APIRouter(prefix="/api/admin", tags=["admin"])
protected = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
login_limiter = RateLimiter(limit=10, window=900)
MAX_UPLOAD = 5 * 1024 * 1024


# --- sesión -----------------------------------------------------------------

@router.post("/login")
def login(data: LoginIn, request: Request, response: Response):
    login_limiter.check(request)
    if not check_password(data.password):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    set_session(response)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    return {"authenticated": is_admin(request)}


# --- categorías -------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-") or "categoria"


def _unique_slug(session: Session, name: str, exclude_id: Optional[int] = None) -> str:
    base, n = slugify(name), 1
    slug = base
    while True:
        existing = session.scalars(select(Category).where(Category.slug == slug)).first()
        if not existing or existing.id == exclude_id:
            return slug
        n += 1
        slug = f"{base}-{n}"


def _get_category(session: Session, category_id: int) -> Category:
    cat = session.get(Category, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    return cat


@protected.get("/categories")
def list_categories(session: Session = Depends(get_session)):
    cats = session.scalars(
        select(Category)
        .order_by(Category.sort_order, Category.name)
        .options(selectinload(Category.standings), selectinload(Category.matches))
    ).all()
    return [category_admin(c) for c in cats]


@protected.post("/categories", status_code=201)
def create_category(data: CategoryIn, session: Session = Depends(get_session)):
    cat = Category(**data.model_dump(), slug=_unique_slug(session, data.name))
    session.add(cat)
    session.commit()
    return category_admin(cat)


@protected.put("/categories/{category_id}")
def update_category(category_id: int, data: CategoryIn, session: Session = Depends(get_session)):
    cat = _get_category(session, category_id)
    if data.name != cat.name:
        cat.slug = _unique_slug(session, data.name, exclude_id=cat.id)
    for key, value in data.model_dump().items():
        setattr(cat, key, value)
    # URLs nuevas: forzar reimportación aunque el fichero coincida
    cat.ranking_hash = cat.calendar_hash = None
    session.commit()
    return category_admin(cat)


@protected.delete("/categories/{category_id}")
def delete_category(category_id: int, session: Session = Depends(get_session)):
    session.delete(_get_category(session, category_id))
    session.commit()
    return {"ok": True}


# --- subida manual / compartida ---------------------------------------------

async def _read_files(files: List[UploadFile]):
    out = []
    for f in files:
        data = await f.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(status_code=413, detail=f"{f.filename}: fichero demasiado grande")
        try:
            kind = sniff_kind(data)
        except ParseError as exc:
            raise HTTPException(status_code=422, detail=f"{f.filename}: {exc}") from exc
        out.append((f.filename or "", kind, data))
    # La clasificación primero: aporta los nombres para separar el calendario
    out.sort(key=lambda t: 0 if t[1] == "ranking" else 1)
    return out


def match_category_by_filename(session: Session, filename: str) -> Optional[Category]:
    """'Calendario CRE Infantil Femenino Liga Oro.xls' -> categoría con ese fvcl_name."""
    stem = norm(PurePath(filename).stem)
    stem = re.sub(r"^(calendario|clasificacion)\s+", "", stem)
    stem = re.sub(r"\s*\(\d+\)$", "", stem)  # "(1)" que añaden los navegadores
    cats = session.scalars(select(Category)).all()
    for c in cats:
        if c.fvcl_name and norm(c.fvcl_name) == stem:
            return c
    for c in cats:
        if c.fvcl_name and norm(c.fvcl_name) in stem:
            return c
    return None


@protected.post("/upload")
async def upload(
    files: List[UploadFile] = File(...),
    category_id: Optional[int] = Form(default=None),
    source: str = Form(default="manual"),
    session: Session = Depends(get_session),
):
    """Sube uno o varios Excel. Sin category_id se intenta deducir por el nombre del fichero."""
    parsed = await _read_files(files)
    source = source if source in ("manual", "share") else "manual"
    results = []
    for filename, kind, data in parsed:
        cat = _get_category(session, category_id) if category_id else match_category_by_filename(session, filename)
        if not cat:
            results.append({"filename": filename, "kind": kind, "status": "needs_category",
                            "message": "No sé a qué categoría pertenece; elígela"})
            continue
        res = import_file(session, cat, data, source=source, force=True)
        results.append({"filename": filename, "kind": kind, "status": res.status, "message": res.message,
                        "category": cat.name, "category_id": cat.id})
    return {"results": results}


# --- sincronización ---------------------------------------------------------

@protected.post("/sync")
def sync(data: SyncIn):
    ids = [data.category_id] if data.category_id else None
    return {"report": sync_categories(ids, source="auto")}


@protected.get("/logs")
def logs(limit: int = 50, session: Session = Depends(get_session)):
    rows = session.scalars(select(SyncLog).order_by(SyncLog.id.desc()).limit(min(limit, 200))).all()
    names = {c.id: c.name for c in session.scalars(select(Category)).all()}
    return [
        {"id": r.id, "created_at": iso(r.created_at), "category": names.get(r.category_id), "kind": r.kind,
         "source": r.source, "status": r.status, "message": r.message}
        for r in rows
    ]


# --- feedback ---------------------------------------------------------------

def _feedback_out(f: Feedback) -> dict:
    return {"id": f.id, "created_at": iso(f.created_at), "name": f.name, "contact": f.contact,
            "kind": f.kind, "message": f.message, "read": f.read}


@protected.get("/feedback")
def list_feedback(session: Session = Depends(get_session)):
    return [_feedback_out(f) for f in session.scalars(select(Feedback).order_by(Feedback.id.desc())).all()]


@protected.patch("/feedback/{feedback_id}")
def patch_feedback(feedback_id: int, data: FeedbackPatch, session: Session = Depends(get_session)):
    fb = session.get(Feedback, feedback_id)
    if not fb:
        raise HTTPException(status_code=404, detail="No encontrado")
    fb.read = data.read
    session.commit()
    return _feedback_out(fb)


@protected.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: int, session: Session = Depends(get_session)):
    fb = session.get(Feedback, feedback_id)
    if fb:
        session.delete(fb)
        session.commit()
    return {"ok": True}


# --- equipos y logos --------------------------------------------------------

def _get_team(session: Session, team_id: int) -> Team:
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return team


def _team_out(team: Team, categories: List[str]) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "logo": logo_url(team),
        "logo_source": team.logo_source,
        "logo_checked_at": iso(team.logo_checked_at),
        "categories": categories,
        "is_ours": is_ours(team.name),
    }


@protected.get("/teams")
def list_teams(session: Session = Depends(get_session)):
    sync_teams_from_standings(session)
    cats_by_team = {}
    for team_name, cat_name in session.execute(
        select(Standing.team, Category.name).join(Category, Standing.category_id == Category.id)
    ).all():
        cats_by_team.setdefault(norm(team_name), set()).add(cat_name)
    # Solo equipos presentes en alguna clasificación actual
    teams = [t for t in session.scalars(select(Team).order_by(Team.name)).all() if t.key in cats_by_team]
    return [_team_out(t, sorted(cats_by_team[t.key])) for t in teams]


def _store_logo(session: Session, team: Team, data: bytes) -> dict:
    try:
        save_logo(team, data, source="manual")
    except LogoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return {"id": team.id, "logo": logo_url(team), "logo_source": team.logo_source}


@protected.post("/teams/{team_id}/logo")
async def upload_logo(team_id: int, file: UploadFile = File(...), session: Session = Depends(get_session)):
    data = await file.read(MAX_IMAGE_BYTES + 1)
    return _store_logo(session, _get_team(session, team_id), data)


@protected.post("/teams/{team_id}/logo-url")
def logo_from_url(team_id: int, data: LogoUrlIn, session: Session = Depends(get_session)):
    team = _get_team(session, team_id)
    try:
        image = download_image(data.url.strip())
    except LogoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _store_logo(session, team, image)


@protected.delete("/teams/{team_id}/logo")
def delete_logo(team_id: int, session: Session = Depends(get_session)):
    team = _get_team(session, team_id)
    remove_logo_file(team)
    team.logo_checked_at = utcnow()  # que la búsqueda automática no lo vuelva a poner enseguida
    session.commit()
    return {"ok": True}


@protected.post("/teams/search-fvcl")
def search_fvcl_logos(data: LogoSearchIn, session: Session = Depends(get_session)):
    query = select(Category).where(Category.active.is_(True), Category.ranking_url.is_not(None))
    if data.category_id:
        query = select(Category).where(Category.id == data.category_id)
    reports = []
    with make_client() as client:
        for cat in session.scalars(query).all():
            reports.append(search_category_logos(session, cat, client, force=data.force))
    return {"reports": reports}
