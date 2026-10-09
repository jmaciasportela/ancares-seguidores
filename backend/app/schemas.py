from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LoginIn(BaseModel):
    password: str


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    fvcl_name: Optional[str] = Field(default=None, max_length=200)
    ranking_url: Optional[str] = Field(default=None, max_length=500)
    calendar_url: Optional[str] = Field(default=None, max_length=500)
    sort_order: int = 0
    active: bool = True

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
