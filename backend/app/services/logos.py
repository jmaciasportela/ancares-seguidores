"""Logos de equipos: normalización de imágenes, descarga segura y registro de equipos."""
import hashlib
import io
import ipaddress
import socket
from typing import Dict, Iterable, Optional
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Standing, Team, utcnow
from ..parsers.common import norm

MAX_IMAGE_BYTES = 5 * 1024 * 1024
LOGO_SIZE = 160
MAX_REDIRECTS = 3


class LogoError(Exception):
    pass


# --- equipos ----------------------------------------------------------------

def ensure_teams(session: Session, names: Iterable[str]) -> None:
    """Da de alta los equipos que aún no existen (clave = nombre normalizado)."""
    wanted = {norm(n): n for n in names if n}
    if not wanted:
        return
    existing = set(session.scalars(select(Team.key).where(Team.key.in_(list(wanted)))).all())
    for key, name in wanted.items():
        if key not in existing:
            session.add(Team(name=name, key=key))
    session.flush()


def sync_teams_from_standings(session: Session) -> None:
    ensure_teams(session, session.scalars(select(Standing.team).distinct()).all())
    session.commit()


def logo_url(team: Team) -> Optional[str]:
    return f"/logos/{team.logo_file}" if team.logo_file else None


def logo_map(session: Session) -> Dict[str, str]:
    """{nombre normalizado: url del logo} para los equipos que tienen logo."""
    return {t.key: logo_url(t) for t in session.scalars(select(Team).where(Team.logo_file.is_not(None))).all()}


# --- imágenes ---------------------------------------------------------------

def normalize_image(data: bytes) -> bytes:
    """Cualquier PNG/JPG/WebP/GIF -> WebP cuadrado de 160 px con fondo transparente."""
    if len(data) > MAX_IMAGE_BYTES:
        raise LogoError("La imagen pesa más de 5 MB")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise LogoError("No es una imagen válida (usa PNG, JPG o WebP)") from exc
    img = img.convert("RGBA")
    bbox = img.getbbox()  # recorta márgenes transparentes
    if bbox:
        img = img.crop(bbox)
    img.thumbnail((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    canvas = Image.new("RGBA", (LOGO_SIZE, LOGO_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((LOGO_SIZE - img.width) // 2, (LOGO_SIZE - img.height) // 2))
    out = io.BytesIO()
    canvas.save(out, "WEBP", quality=85, method=6)
    return out.getvalue()


def save_logo(team: Team, data: bytes, source: str) -> None:
    webp = normalize_image(data)
    logos_dir = get_settings().logos_dir
    logos_dir.mkdir(parents=True, exist_ok=True)
    # El hash en el nombre permite cachear el fichero para siempre
    filename = f"{team.id}-{hashlib.sha256(webp).hexdigest()[:10]}.webp"
    (logos_dir / filename).write_bytes(webp)
    remove_logo_file(team)
    team.logo_file = filename
    team.logo_source = source
    team.logo_updated_at = utcnow()


def remove_logo_file(team: Team) -> None:
    if team.logo_file:
        old = get_settings().logos_dir / team.logo_file
        if old.exists():
            old.unlink()
    team.logo_file = None
    team.logo_source = None


# --- descarga segura ----------------------------------------------------------

def check_public_url(url: str) -> None:
    """Solo http(s) hacia IPs públicas: evita que se use para llegar a la red interna."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise LogoError("La URL debe ser http(s) y sin credenciales")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise LogoError("No se encuentra el servidor de la imagen") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise LogoError("La URL apunta a una dirección no pública")


def download_image(url: str, client: Optional[httpx.Client] = None) -> bytes:
    own = client is None
    client = client or httpx.Client(timeout=20, headers={"User-Agent": get_settings().user_agent})
    try:
        for _ in range(MAX_REDIRECTS + 1):
            check_public_url(url)
            with client.stream("GET", url, follow_redirects=False) as resp:
                if resp.is_redirect:
                    url = urljoin(url, resp.headers.get("location", ""))
                    continue
                if resp.status_code != 200:
                    raise LogoError(f"La imagen no se pudo descargar (HTTP {resp.status_code})")
                data = b""
                for chunk in resp.iter_bytes():
                    data += chunk
                    if len(data) > MAX_IMAGE_BYTES:
                        raise LogoError("La imagen pesa más de 5 MB")
                return data
        raise LogoError("Demasiadas redirecciones")
    except httpx.HTTPError as exc:
        raise LogoError(f"Error de red al descargar la imagen ({type(exc).__name__})") from exc
    finally:
        if own:
            client.close()
