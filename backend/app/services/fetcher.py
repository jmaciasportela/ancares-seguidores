"""Descarga educada de los Excel de la FVCL.

fvcl.es protege sus descargas con un reto anti-bots. No intentamos saltarlo:
hacemos una única petición identificada y, si no recibimos un .xls, se avisa al
admin para que suba el fichero manualmente.
"""
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import get_settings
from ..parsers.common import looks_like_xls


@dataclass
class FetchResult:
    ok: bool
    data: Optional[bytes] = None
    blocked: bool = False
    message: str = ""


def fetch_xls(url: str, timeout: float = 30.0) -> FetchResult:
    settings = get_settings()
    headers = {"User-Agent": settings.user_agent, "Accept": "application/vnd.ms-excel,*/*"}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
    except httpx.HTTPError as exc:
        return FetchResult(ok=False, message=f"Error de red: {exc}")

    if resp.status_code == 200 and looks_like_xls(resp.content):
        return FetchResult(ok=True, data=resp.content)

    content_type = resp.headers.get("content-type", "")
    blocked = resp.status_code in (403, 429, 503) or "text/html" in content_type
    reason = "protección anti-bots de la federación" if blocked else "respuesta inesperada"
    return FetchResult(
        ok=False,
        blocked=blocked,
        message=f"HTTP {resp.status_code} ({content_type or 'sin tipo'}): {reason}",
    )
