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


@pytest.fixture(scope="session")
def ranking_bytes() -> bytes:
    return RANKING_XLS.read_bytes()


@pytest.fixture(scope="session")
def calendar_bytes() -> bytes:
    return CALENDAR_XLS.read_bytes()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.db import Base, engine
    from app.main import app

    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c
