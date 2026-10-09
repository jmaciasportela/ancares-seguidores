import logging
import random
import time
from datetime import date
from typing import List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import Category, SyncLog, utcnow
from .fetcher import fetch_xls, make_client
from .importer import import_file
from .mailer import send_admin_email

log = logging.getLogger(__name__)
_last_blocked_email: Optional[date] = None


def sync_categories(category_ids: Optional[List[int]] = None, source: str = "auto", pause: bool = False) -> List[dict]:
    """Descarga e importa clasificación y calendario de cada categoría activa."""
    report = []
    # Un cliente por sincronización: la cookie de la PoW sirve para todos los ficheros
    with SessionLocal() as session, make_client() as client:
        query = select(Category).where(Category.active.is_(True)).order_by(Category.sort_order)
        if category_ids:
            query = select(Category).where(Category.id.in_(category_ids))
        categories = session.scalars(query).all()

        for i, cat in enumerate(categories):
            if pause and i:
                time.sleep(random.uniform(3, 12))  # no acribillar a la federación
            failure = None
            # Primero la clasificación: sus nombres sirven para separar el calendario
            for kind, url in (("ranking", cat.ranking_url), ("calendar", cat.calendar_url)):
                if not url:
                    continue
                fetched = fetch_xls(url, client=client)
                if fetched.ok:
                    res = import_file(session, cat, fetched.data, source=source)
                    report.append({"category": cat.name, "kind": kind, "status": res.status, "message": res.message, "url": url})
                    if res.status == "error":
                        failure = ("error", res.message)
                else:
                    status = "blocked" if fetched.blocked else "error"
                    failure = (status, fetched.message)
                    session.add(SyncLog(category_id=cat.id, kind=kind, source=source, status=status, message=fetched.message))
                    report.append({"category": cat.name, "kind": kind, "status": status, "message": fetched.message, "url": url})
            if failure:
                cat.sync_status, cat.last_error = failure
                cat.last_sync_at = utcnow()
                session.commit()
    return report


def daily_job() -> None:
    global _last_blocked_email
    log.info("Sincronización diaria iniciada")
    report = sync_categories(source="auto", pause=True)
    failed = [r for r in report if r["status"] in ("blocked", "error")]
    if failed and _last_blocked_email != date.today():
        settings = get_settings()
        lines = [
            "No se han podido descargar automáticamente estos ficheros de la FVCL.",
            "Ábrelos desde el móvil y compártelos con la app (o súbelos en el panel de admin):",
            "",
        ]
        for r in failed:
            lines.append(f"• {r['category']} ({'clasificación' if r['kind'] == 'ranking' else 'calendario'}): {r.get('url', '')}")
            lines.append(f"  Motivo: {r['message']}")
        lines += ["", f"Panel de admin: {settings.public_url}/#/admin"]
        send_admin_email("Hay ficheros pendientes de subir", "\n".join(lines))
        _last_blocked_email = date.today()
    log.info("Sincronización diaria terminada: %s", report)


def start_scheduler() -> Optional[BackgroundScheduler]:
    settings = get_settings()
    if not settings.sync_enabled:
        return None
    scheduler = BackgroundScheduler(timezone=settings.timezone)
    scheduler.add_job(
        daily_job,
        CronTrigger.from_crontab(settings.sync_cron, timezone=settings.timezone),
        id="daily_sync",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler
