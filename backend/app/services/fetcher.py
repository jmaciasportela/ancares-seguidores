"""Descarga de los Excel de la FVCL.

fvcl.es protege sus descargas con una prueba de trabajo (ver pow.py). La
resolvemos como haría un navegador, pero sin hacernos pasar por uno: User-Agent
propio, un único intento por fichero y sin reintentos. Si aun así no llega un
.xls, se avisa al admin para que lo suba manualmente.
"""
import logging
from dataclasses import dataclass
from typing import Callable, Optional

import httpx

from ..config import get_settings
from ..parsers.common import looks_like_xls
from .pow import PowError, parse_challenge, solve, validation_url

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    ok: bool
    data: Optional[bytes] = None
    blocked: bool = False
    message: str = ""


def make_client(timeout: float = 30.0) -> httpx.Client:
    """Cliente con cookies en memoria: compartirlo en una sincronización evita
    resolver la PoW para cada fichero."""
    settings = get_settings()
    headers = {"User-Agent": settings.user_agent, "Accept": "*/*"}
    # Sin seguir redirecciones, para no confundir un login u otra página con el fichero
    return httpx.Client(timeout=timeout, follow_redirects=False, headers=headers)


def _blocked(resp: httpx.Response, reason: str) -> FetchResult:
    content_type = resp.headers.get("content-type", "sin tipo")
    return FetchResult(ok=False, blocked=True, message=f"HTTP {resp.status_code} ({content_type}): {reason}")


def fetch_xls(url: str, client: Optional[httpx.Client] = None) -> FetchResult:
    return fetch(url, client, accept=lambda r: looks_like_xls(r.content), what="un Excel")


def fetch_html(url: str, client: Optional[httpx.Client] = None) -> FetchResult:
    """Página HTML de fvcl.es (p. ej. la clasificación, para buscar escudos)."""
    return fetch(url, client, accept=lambda r: "text/html" in r.headers.get("content-type", ""), what="una página HTML")


def fetch(url: str, client: Optional[httpx.Client], accept: Callable[[httpx.Response], bool], what: str) -> FetchResult:
    own_client = client is None
    client = client or make_client()
    try:
        return _fetch(client, url, accept, what)
    except httpx.HTTPError as exc:
        return FetchResult(ok=False, message=f"Error de red: {type(exc).__name__}")
    finally:
        if own_client:
            client.close()


def _fetch(client: httpx.Client, url: str, accept: Callable[[httpx.Response], bool], what: str) -> FetchResult:
    settings = get_settings()

    def good(r: httpx.Response) -> bool:
        # La página del reto también es HTML: nunca cuenta como respuesta válida
        return r.status_code == 200 and accept(r) and parse_challenge(r.content) is None

    resp = client.get(url)
    if good(resp):
        return FetchResult(ok=True, data=resp.content)

    challenge = parse_challenge(resp.content) if resp.status_code in (200, 429) else None
    if challenge is None:
        blocked = resp.status_code in (403, 429, 503) or "text/html" in resp.headers.get("content-type", "")
        reason = "protección anti-bots de la federación" if blocked else "respuesta inesperada"
        return FetchResult(ok=False, blocked=blocked, message=f"HTTP {resp.status_code} ({resp.headers.get('content-type', 'sin tipo')}): {reason}")
    if not settings.pow_enabled:
        return _blocked(resp, "prueba de trabajo de la federación (resolución desactivada)")

    try:
        nonce = solve(challenge, settings.pow_max_seconds)
    except PowError as exc:
        return _blocked(resp, str(exc))
    log.info("PoW resuelta (%s bits)", challenge.bits)

    check = client.get(validation_url(url, challenge, nonce))
    if check.status_code != 204:
        return _blocked(check, "la federación no aceptó la prueba de trabajo")

    resp = client.get(url)
    if good(resp):
        return FetchResult(ok=True, data=resp.content)
    if parse_challenge(resp.content):
        return _blocked(resp, "la federación sigue mostrando el reto tras validarlo")
    return _blocked(resp, f"la respuesta no es {what}")
