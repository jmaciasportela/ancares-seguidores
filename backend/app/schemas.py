from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from .scoring_format import ScoreFormat


class LoginIn(BaseModel):
    password: str


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    fvcl_name: Optional[str] = Field(default=None, max_length=200)
    ranking_url: Optional[str] = Field(default=None, max_length=500)
    calendar_url: Optional[str] = Field(default=None, max_length=500)
    sort_order: int = 0
    active: bool = True
    score_format: Optional[ScoreFormat] = None
    kind: Literal["league", "tournament"] = "league"

    @field_validator("ranking_url", "calendar_url")
    @classmethod
    def _url(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip()
        if not v:
            return None
        if not v.startswith(("http://", "https://")):
            raise ValueError("Debe ser una URL http(s)")
        return v

    @field_validator("fvcl_name", "name")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return (v or "").strip() or None


class FeedbackIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    contact: Optional[str] = Field(default=None, max_length=200)
    kind: str = Field(default="otro", pattern="^(error|mejora|otro)$")
    message: str = Field(min_length=3, max_length=4000)
    website: Optional[str] = None  # honeypot: los humanos lo dejan vacío


class FeedbackPatch(BaseModel):
    read: bool


class SyncIn(BaseModel):
    category_id: Optional[int] = None


class LogoUrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=1000)


class LogoSearchIn(BaseModel):
    category_id: Optional[int] = None
    force: bool = True  # desde el panel, ignora la espera semanal


class ScorerJoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)


class ScorerIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ProvisionalIn(BaseModel):
    category_id: int
    round_no: int
    home: str = Field(max_length=200)
    away: str = Field(max_length=200)
    home_sets: int = Field(ge=0, le=7)
    away_sets: int = Field(ge=0, le=7)
    partials: List[List[Union[int, bool]]] = Field(max_length=7)
    finished_early: bool = False


class PingIn(BaseModel):
    device: str = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    installed: bool = False
    platform: str = Field(default="otro", max_length=20)
    version: Optional[str] = Field(default=None, max_length=20)


class MatchIn(BaseModel):
    """Partido de torneo (a mano)."""

    phase: Optional[str] = Field(default=None, max_length=80)
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    home: str = Field(min_length=1, max_length=200)
    away: str = Field(min_length=1, max_length=200)
    venue: Optional[str] = Field(default=None, max_length=200)
    result: Optional[str] = Field(default=None, max_length=80)

    @field_validator("date", "time", "phase", "venue", "result", mode="before")
    @classmethod
    def _empty(cls, v):
        return v.strip() or None if isinstance(v, str) else v


class ParseIn(BaseModel):
    text: str = Field(max_length=20000)


class BulkIn(BaseModel):
    matches: List[MatchIn] = Field(max_length=300)
