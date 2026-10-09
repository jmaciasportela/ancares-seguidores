from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # Nombre de la competición tal y como aparece en los ficheros de la FVCL
    # (p. ej. "CRE Infantil Femenino Liga Oro"); sirve para asociar subidas.
    fvcl_name: Mapped[Optional[str]] = mapped_column(String(200))
    ranking_url: Mapped[Optional[str]] = mapped_column(String(500))
    calendar_url: Mapped[Optional[str]] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    data_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[str] = mapped_column(String(20), default="pending")
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    ranking_hash: Mapped[Optional[str]] = mapped_column(String(64))
    calendar_hash: Mapped[Optional[str]] = mapped_column(String(64))

    standings: Mapped[List["Standing"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="Standing.position"
    )
    matches: Mapped[List["Match"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="Match.order"
    )


class Standing(Base):
    __tablename__ = "standings"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    team: Mapped[str] = mapped_column(String(200))
    points: Mapped[int] = mapped_column(Integer, default=0)
    played: Mapped[int] = mapped_column(Integer, default=0)
    won: Mapped[int] = mapped_column(Integer, default=0)
    lost: Mapped[int] = mapped_column(Integer, default=0)
    sets_for: Mapped[int] = mapped_column(Integer, default=0)
    sets_against: Mapped[int] = mapped_column(Integer, default=0)
    points_for: Mapped[int] = mapped_column(Integer, default=0)
    points_against: Mapped[int] = mapped_column(Integer, default=0)
    promotion: Mapped[Optional[str]] = mapped_column(String(50))
    is_ours: Mapped[bool] = mapped_column(Boolean, default=False)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    category: Mapped[Category] = relationship(back_populates="standings")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    round_no: Mapped[int] = mapped_column(Integer)
    round_name: Mapped[str] = mapped_column(String(80))
    home: Mapped[Optional[str]] = mapped_column(String(200))
    away: Mapped[Optional[str]] = mapped_column(String(200))
    is_bye: Mapped[bool] = mapped_column(Boolean, default=False)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    venue: Mapped[Optional[str]] = mapped_column(String(200))
    home_sets: Mapped[Optional[int]] = mapped_column(Integer)
    away_sets: Mapped[Optional[int]] = mapped_column(Integer)
    partials: Mapped[list] = mapped_column(JSON, default=list)
    raw_teams: Mapped[str] = mapped_column(String(400))
    raw_result: Mapped[Optional[str]] = mapped_column(String(400))
    is_ours: Mapped[bool] = mapped_column(Boolean, default=False)

    category: Mapped[Category] = relationship(back_populates="matches")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    contact: Mapped[Optional[str]] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="otro")
    message: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(20))  # ranking | calendar
    source: Mapped[str] = mapped_column(String(20))  # auto | manual | share
    status: Mapped[str] = mapped_column(String(20))  # ok | unchanged | blocked | error
    message: Mapped[Optional[str]] = mapped_column(Text)


class Team(Base):
    """Equipo visto en alguna clasificación; guarda su logo (si lo hay)."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200), unique=True, index=True)  # nombre normalizado
    logo_file: Mapped[Optional[str]] = mapped_column(String(120))
    logo_source: Mapped[Optional[str]] = mapped_column(String(20))  # manual | fvcl
    logo_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    logo_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # última búsqueda en FVCL
