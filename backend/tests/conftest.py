import os
import tempfile
from pathlib import Path

import pytest

# Configuración de pruebas antes de importar la app (el engine se crea al importar)
_tmp = tempfile.mkdtemp(prefix="ancares-test-")
os.environ.update(
    DB_PATH=str(Path(_tmp) / "test.db"),
    LOGOS_DIR=str(Path(_tmp) / "logos"),
    STATIC_DIR=str(Path(_tmp) / "no-frontend"),
    SYNC_ENABLED="false",
    ADMIN_PASSWORD="secreto",
    SECRET_KEY="test",
    SMTP_HOST="",
)

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
RANKING_XLS = SAMPLES / "Clasificación CRE Infantil Femenino Liga Oro.xls"
CALENDAR_XLS = SAMPLES / "Calendario CRE Infantil Femenino Liga Oro.xls"
# Descargados el 18/10/2026, con la jornada 1 ya jugada (resultados oficiales)
RANKING_J1_XLS = SAMPLES / "Clasificación CRE Infantil Femenino Liga Oro - jornada 1 jugada.xls"
CALENDAR_J1_XLS = SAMPLES / "Calendario CRE Infantil Femenino Liga Oro - jornada 1 jugada.xls"


@pytest.fixture(scope="session")
def ranking_bytes() -> bytes:
    return RANKING_XLS.read_bytes()


@pytest.fixture(scope="session")
def calendar_bytes() -> bytes:
    return CALENDAR_XLS.read_bytes()


def clear_ours_dates_except(away: str) -> None:
    """Las fechas reales del Excel de muestra caen en días concretos: para que los
    tests no dependan del día en que se ejecutan, el resto de partidos de Ancares
    se mueven a dentro de un mes (respetando su orden)."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Match

    with SessionLocal() as s:
        base = datetime.now(timezone.utc) + timedelta(days=30)
        for m in s.scalars(select(Match).where(Match.is_ours.is_(True), Match.starts_at.is_not(None))):
            if m.away != away:
                m.starts_at = base + timedelta(days=m.round_no, minutes=m.order)
        s.commit()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.db import Base, engine
    from app.main import app
    from app.routers import admin, feedback, live, public, scoring

    Base.metadata.drop_all(engine)
    # Los límites por IP son globales: cada test empieza de cero
    for limiter in (admin.login_limiter, feedback.limiter, scoring.join_limiter, public.ping_limiter, public.cheer_limiter,
                    live.push_limiter):
        limiter.hits.clear()
    with TestClient(app) as c:
        yield c
