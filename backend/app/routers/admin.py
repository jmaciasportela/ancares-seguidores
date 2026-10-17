import re
from datetime import timezone
from pathlib import PurePath
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import (
    RateLimiter,
    check_password,
    clear_session,
    hash_code,
    is_admin,
    new_scorer_code,
    require_admin,
    set_session,
)
from ..db import get_session
from ..models import Category, Feedback, Match, ProvisionalResult, Scorer, Standing, SyncLog, Team, competition_order, utcnow
from ..parsers.common import ParseError, norm
from ..schemas import BulkIn, CategoryIn, FeedbackPatch, LoginIn, LogoSearchIn, LogoUrlIn, MatchIn, ParseIn, ScorerIn, SyncIn
from ..serializers import category_admin, iso, provisional_out
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
from ..services import tournament, usage
from ..services.provisional import match_key, provisional_map
from ..services.mailer import email_status, send_test_email
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
        .order_by(*competition_order())
        .options(selectinload(Category.standings), selectinload(Category.matches))
    ).all()
    # Último cambio real de cada categoría (las pasadas «Sin cambios» no cuentan)
    last_change = {}
    for log in session.scalars(select(SyncLog).where(SyncLog.status == "ok").order_by(SyncLog.id.desc())).all():
        last_change.setdefault(log.category_id, {"message": log.message, "at": iso(log.created_at), "kind": log.kind})
    out = []
    for c in cats:
        item = category_admin(c)
        item["last_change"] = last_change.get(c.id)
        item["fvcl_reports_changes"] = bool(c.http_validators)
        out.append(item)
    return out


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
        if cat.is_tournament:
            results.append({"filename": filename, "kind": kind, "status": "error", "category": cat.name,
                            "message": "Es un torneo: sus partidos se meten a mano, no con el Excel de la FVCL"})
            continue
        res = import_file(session, cat, data, source=source)
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
         "source": r.source, "status": r.status, "message": r.message, "details": r.details or []}
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


# --- anotadores ---------------------------------------------------------------

def _scorer_out(s: Scorer, code: Optional[str] = None) -> dict:
    out = {"id": s.id, "name": s.name, "active": s.active,
           "created_at": iso(s.created_at), "last_used_at": iso(s.last_used_at)}
    if code:
        out["code"] = code  # solo al crear o regenerar: no se guarda en claro
    return out


def _unique_code(session: Session) -> str:
    while True:
        code = new_scorer_code()
        if not session.scalars(select(Scorer).where(Scorer.code_hash == hash_code(code))).first():
            return code


def _get_scorer(session: Session, scorer_id: int) -> Scorer:
    scorer = session.get(Scorer, scorer_id)
    if not scorer:
        raise HTTPException(status_code=404, detail="Anotador no encontrado")
    return scorer


@protected.get("/scorers")
def list_scorers(session: Session = Depends(get_session)):
    return [_scorer_out(s) for s in session.scalars(select(Scorer).order_by(Scorer.name)).all()]


@protected.post("/scorers", status_code=201)
def create_scorer(data: ScorerIn, session: Session = Depends(get_session)):
    code = _unique_code(session)
    scorer = Scorer(name=data.name.strip(), code_hash=hash_code(code))
    session.add(scorer)
    session.commit()
    return _scorer_out(scorer, code)


@protected.post("/scorers/{scorer_id}/regenerate")
def regenerate_scorer(scorer_id: int, session: Session = Depends(get_session)):
    scorer = _get_scorer(session, scorer_id)
    code = _unique_code(session)
    scorer.code_hash = hash_code(code)
    scorer.active = True
    session.commit()
    return _scorer_out(scorer, code)


@protected.post("/scorers/{scorer_id}/revoke")
def revoke_scorer(scorer_id: int, session: Session = Depends(get_session)):
    scorer = _get_scorer(session, scorer_id)
    scorer.active = False
    session.commit()
    return _scorer_out(scorer)


@protected.post("/scorers/{scorer_id}/activate")
def activate_scorer(scorer_id: int, session: Session = Depends(get_session)):
    scorer = _get_scorer(session, scorer_id)
    scorer.active = True
    session.commit()
    return _scorer_out(scorer)


@protected.delete("/scorers/{scorer_id}")
def delete_scorer(scorer_id: int, session: Session = Depends(get_session)):
    session.delete(_get_scorer(session, scorer_id))
    session.commit()
    return {"ok": True}


# --- resultados provisionales -----------------------------------------------------

@protected.get("/provisional")
def list_provisional(session: Session = Depends(get_session)):
    cats = {c.id: c for c in session.scalars(select(Category)).all()}
    rows = session.scalars(select(ProvisionalResult).order_by(ProvisionalResult.updated_at.desc())).all()
    return [
        {"id": p.id, "category": cats[p.category_id].name if p.category_id in cats else None,
         "tournament": bool(p.category_id in cats and cats[p.category_id].is_tournament),
         "round_no": p.round_no, "home": p.home, "away": p.away, **provisional_out(p)}
        for p in rows
    ]


@protected.post("/provisional/{provisional_id}/confirm")
def confirm_provisional(provisional_id: int, session: Session = Depends(get_session)):
    """Torneos: el admin da por bueno el resultado provisional."""
    prov = session.get(ProvisionalResult, provisional_id)
    if not prov:
        raise HTTPException(status_code=404, detail="Resultado no encontrado")
    try:
        match = tournament.confirm_provisional(session, prov)
    except tournament.TournamentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return {"ok": True, "match_id": match.id}


@protected.delete("/provisional/{provisional_id}")
def delete_provisional(provisional_id: int, session: Session = Depends(get_session)):
    prov = session.get(ProvisionalResult, provisional_id)
    if prov:
        session.delete(prov)
        session.commit()
    return {"ok": True}


# --- email ----------------------------------------------------------------------

@protected.get("/email")
def email_info():
    return email_status()


@protected.post("/email/test")
def email_test():
    ok, error = send_test_email()
    return {"ok": ok, "error": error, **email_status()}


# --- uso de la app ------------------------------------------------------------

@protected.get("/usage")
def usage_summary(session: Session = Depends(get_session)):
    return usage.summary(session)


# --- torneos: partidos a mano -----------------------------------------------------

def _tournament(session: Session, category_id: int) -> Category:
    cat = _get_category(session, category_id)
    if not cat.is_tournament:
        raise HTTPException(status_code=422, detail="Los partidos de liga vienen del Excel de la federación")
    return cat


def _admin_match(m: Match, prov: Optional[ProvisionalResult]) -> dict:
    local = m.starts_at.replace(tzinfo=m.starts_at.tzinfo or timezone.utc).astimezone(tournament.TZ) if m.starts_at else None
    return {
        "id": m.id, "phase": m.round_name, "round_no": m.round_no, "home": m.home, "away": m.away,
        "date": local.date().isoformat() if local else None, "time": local.strftime("%H:%M") if local else None,
        "venue": m.venue, "home_sets": m.home_sets, "away_sets": m.away_sets, "partials": m.partials or [],
        "result": m.raw_result or (f"{m.home_sets}-{m.away_sets}" if m.home_sets is not None else None),
        "is_ours": m.is_ours, "provisional": {"id": prov.id, **provisional_out(prov)} if prov else None,
    }


def _matches_out(session: Session, cat: Category) -> list:
    provs = provisional_map(session)
    session.refresh(cat)
    return [_admin_match(m, provs.get(match_key(m))) for m in sorted(cat.matches, key=lambda m: m.order)]


def _save(session: Session, cat: Category, data: dict, match: Optional[Match] = None) -> Match:
    try:
        m = tournament.save_match(session, cat, data, match)
    except (tournament.TournamentError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    cat.data_updated_at = utcnow()
    return m


@protected.get("/categories/{category_id}/matches")
def list_tournament_matches(category_id: int, session: Session = Depends(get_session)):
    return _matches_out(session, _tournament(session, category_id))


@protected.post("/categories/{category_id}/matches", status_code=201)
def create_tournament_match(category_id: int, data: MatchIn, session: Session = Depends(get_session)):
    cat = _tournament(session, category_id)
    m = _save(session, cat, data.model_dump())
    session.commit()
    return {"id": m.id}


@protected.put("/matches/{match_id}")
def update_tournament_match(match_id: int, data: MatchIn, session: Session = Depends(get_session)):
    m = session.get(Match, match_id)
    if not m:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    cat = _tournament(session, m.category_id)
    _save(session, cat, data.model_dump(), m)
    session.commit()
    return {"id": m.id}


@protected.delete("/matches/{match_id}")
def delete_tournament_match(match_id: int, session: Session = Depends(get_session)):
    m = session.get(Match, match_id)
    if not m:
        return {"ok": True}
    cat = _tournament(session, m.category_id)
    prov = provisional_map(session).get(match_key(m))
    if prov:
        session.delete(prov)
    session.delete(m)
    session.flush()
    tournament.renumber(session, cat)
    cat.data_updated_at = utcnow()
    session.commit()
    return {"ok": True}


@protected.post("/categories/{category_id}/matches/parse")
def parse_tournament_matches(category_id: int, data: ParseIn, session: Session = Depends(get_session)):
    """Vista previa de una lista pegada (no guarda nada)."""
    _tournament(session, category_id)
    return {"rows": [r.as_dict() for r in tournament.parse_lines(data.text)]}


@protected.post("/categories/{category_id}/matches/bulk", status_code=201)
def bulk_tournament_matches(category_id: int, data: BulkIn, session: Session = Depends(get_session)):
    cat = _tournament(session, category_id)
    for item in data.matches:
        _save(session, cat, item.model_dump())
    session.commit()
    return {"created": len(data.matches)}
