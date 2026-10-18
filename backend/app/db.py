from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


settings = get_settings()
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
engine = _make_engine(f"sqlite:///{settings.db_path}")
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# Columnas añadidas a tablas que ya existían en versiones anteriores.
# create_all crea las tablas nuevas, pero no añade columnas a las existentes.
ADDED_COLUMNS = {
    "categories": {
        "score_format": "TEXT",
        "kind": "VARCHAR(20) DEFAULT 'league'",
        "http_validators": "TEXT",
        "points_system": "VARCHAR(10) DEFAULT 'auto'",
    },
    "sync_logs": {"details": "TEXT"},
}


def _add_missing_columns() -> None:
    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            for name, ddl in columns.items():
                if existing and name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    from . import models  # noqa: F401  registra los modelos

    Base.metadata.create_all(engine)
    _add_missing_columns()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
