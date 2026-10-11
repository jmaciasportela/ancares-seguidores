from typing import List, Optional, Union

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
