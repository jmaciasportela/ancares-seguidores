from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from ..auth import RateLimiter
from ..db import get_session
from ..models import Feedback
from ..schemas import FeedbackIn
from ..services.mailer import send_admin_email

router = APIRouter(prefix="/api", tags=["feedback"])
limiter = RateLimiter(limit=5, window=3600)

KIND_LABEL = {"error": "Error", "mejora": "Mejora", "otro": "Comentario"}


@router.post("/feedback", status_code=201)
def create_feedback(
    data: FeedbackIn, request: Request, background: BackgroundTasks, session: Session = Depends(get_session)
):
    if data.website:  # bot: se responde OK pero no se guarda
        return {"ok": True}
    limiter.check(request)
    fb = Feedback(
        name=(data.name or "").strip() or None,
        contact=(data.contact or "").strip() or None,
        kind=data.kind,
        message=data.message.strip(),
    )
    session.add(fb)
    session.commit()
    body = (
        f"Tipo: {KIND_LABEL[fb.kind]}\n"
        f"Nombre: {fb.name or '-'}\n"
        f"Contacto: {fb.contact or '-'}\n\n"
        f"{fb.message}\n"
    )
    background.add_task(send_admin_email, f"Nuevo feedback ({KIND_LABEL[fb.kind]})", body)
    return {"ok": True}
