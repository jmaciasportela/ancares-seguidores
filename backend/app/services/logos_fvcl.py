"""Búsqueda automática de escudos en la página de clasificación de fvcl.es.

No dependemos de la maquetación exacta de Clupik: para cada <img> se reúne el
texto que la identifica (alt, title, title/aria-label del enlace que la contiene
y el texto que aparece justo después) y se compara con los equipos conocidos.
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import timedelta
from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Category, Team, utcnow
from ..parsers.common import norm
from .fetcher import fetch_html
from .logos import LogoError, download_image, ensure_teams, image_size, save_logo

log = logging.getLogger(__name__)
RECHECK_AFTER = timedelta(days=7)
FOLLOWING_TEXT = 160  # caracteres de texto tras la imagen que se tienen en cuenta


@dataclass
class _Img:
    src: str
    labels: List[str] = field(default_factory=list)
    after: str = ""


def largest_in_srcset(srcset: Optional[str]) -> Optional[str]:
    """'a.png 1x, b.png 2x' / 'a.png 60w, b.png 240w' -> la candidata más grande."""
    best, best_size = None, -1.0
    for part in (srcset or "").split(","):
        bits = part.strip().split()
        if not bits or bits[0].startswith("data:"):
            continue
        m = re.fullmatch(r"(\d+(?:\.\d+)?)([wx])", bits[1]) if len(bits) > 1 else None
        size = float(m.group(1)) * (1 if m and m.group(2) == "w" else 100) if m else 100
        if size > best_size:
            best, best_size = bits[0], size
    return best


SIZE_IN_PATH = re.compile(r"(?<![\d])(\d{2,3})x(\d{2,3})(?![\d])")
SIZE_PARAMS = ("w", "width", "h", "height", "size", "s")


def bigger_variants(url: str) -> List[str]:
    """Versiones más grandes de una miniatura, de mayor a menor (sin la original).

    Cubre los patrones habituales de CDN: tamaño en la ruta ("logo.60x60.png",
    "/60x60/logo.png") o en la query (?w=60, ?width=60, ?size=small).
    """
    parts = urlsplit(url)
    variants: List[str] = []
    for size in (512, 256):
        path = parts.path
        if SIZE_IN_PATH.search(path):
            path = SIZE_IN_PATH.sub(f"{size}x{size}", path)
        query = parse_qsl(parts.query, keep_blank_values=True)
        query = [(k, str(size) if k.lower() in SIZE_PARAMS and v.isdigit() else ("large" if k.lower() == "size" else v)) for k, v in query]
        candidate = urlunsplit(parts._replace(path=path, query=urlencode(query)))
        if candidate != url and candidate not in variants:
            variants.append(candidate)
    return variants


class _ImgCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images: List[_Img] = []
        self.links: List[List[str]] = []  # pila de etiquetas de los <a> abiertos
        self.skip = 0  # dentro de <script>/<style>

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "a":
            self.links.append([v for v in (a.get("title"), a.get("aria-label")) if v])
        elif tag == "img":
            src = largest_in_srcset(a.get("data-srcset") or a.get("srcset")) or a.get("data-src") or a.get("src")
            if src and not src.startswith("data:"):
                labels = [v for v in (a.get("alt"), a.get("title")) if v]
                for link in self.links:
                    labels += link
                self.images.append(_Img(src=src, labels=labels))

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        elif tag == "a" and self.links:
            self.links.pop()

    def handle_data(self, data):
        if self.skip or not self.images:
            return
        last = self.images[-1]
        if len(last.after) < FOLLOWING_TEXT:
            last.after = (last.after + " " + data)[:FOLLOWING_TEXT]


def find_logos(html: str, base_url: str, teams: Iterable[str]) -> Dict[str, str]:
    """{nombre de equipo: URL absoluta de su escudo} para los que se encuentren."""
    parser = _ImgCollector()
    parser.feed(html)
    by_key = {norm(t): t for t in teams if t}
    found: Dict[str, str] = {}

    keys_longest_first = sorted(by_key, key=len, reverse=True)

    def match_label(text: str) -> Optional[str]:
        """alt/title: el nombre completo o contenido como palabras ("Escudo de X")."""
        n = norm(text)
        for key in keys_longest_first:
            if n == key or re.search(r"(^|\W)" + re.escape(key) + r"($|\W)", n):
                return by_key[key]
        return None

    def match_following(text: str) -> Optional[str]:
        """Texto tras la imagen: debe empezar por el nombre ("Maristas Burgos A 12 5 ...")."""
        n = norm(text)
        for key in keys_longest_first:
            if n == key or n.startswith(key + " "):
                return by_key[key]
        return None

    for img in parser.images:
        if re.search(r"\.svg(\?|$)", img.src, re.I):
            continue  # Pillow no lee SVG
        team = next((t for t in map(match_label, img.labels) if t), None) or match_following(img.after)
        if team and team not in found:
            found[team] = urljoin(base_url, img.src)
    return found


def ranking_page_url(ranking_url: str) -> str:
    """.../ranking/3706763/export-xls -> .../ranking/3706763"""
    return re.sub(r"/export-xls/?$", "", ranking_url.split("?")[0])


def search_category_logos(
    session: Session, category: Category, client: Optional[httpx.Client] = None, force: bool = False
) -> dict:
    """Busca escudos para los equipos de la categoría que no tienen logo.

    Nunca sustituye un logo puesto a mano. Sin `force`, cada equipo se reintenta
    como mucho una vez por semana para no pedir la página a diario.
    """
    names = [s.team for s in category.standings]
    ensure_teams(session, names)
    teams = session.scalars(select(Team).where(Team.key.in_([norm(n) for n in names]))).all()
    now = utcnow()

    def due(t: Team) -> bool:
        checked = t.logo_checked_at
        if checked is not None and checked.tzinfo is None:
            checked = checked.replace(tzinfo=now.tzinfo)
        return force or checked is None or now - checked > RECHECK_AFTER

    # Con `force` (botón del admin) también se rehacen los logos que vinieron de
    # la FVCL; los subidos a mano no se tocan nunca.
    pending = [t for t in teams if (not t.logo_file or (force and t.logo_source == "fvcl")) and due(t)]
    report = {"category": category.name, "checked": len(pending), "found": [], "missing": [], "error": None}
    if not pending or not category.ranking_url:
        session.commit()
        return report

    page = fetch_html(ranking_page_url(category.ranking_url), client)
    for t in pending:
        t.logo_checked_at = now
    if not page.ok:
        report["error"] = page.message
        session.commit()
        return report

    urls = find_logos(page.data.decode("utf-8", errors="replace"), ranking_page_url(category.ranking_url), [t.name for t in pending])
    for t in pending:
        url = urls.get(t.name)
        if not url:
            report["missing"].append(t.name)
            continue
        try:
            url, image = best_image(url, client)
            save_logo(t, image, source="fvcl")
            log.info("Logo de %s desde %s (%s px)", t.name, url, image_size(image))
            report["found"].append(t.name)
        except LogoError as exc:
            log.info("Logo de %s no válido (%s): %s", t.name, url, exc)
            report["missing"].append(t.name)
    session.commit()
    return report


def best_image(url: str, client: Optional[httpx.Client]) -> Tuple[str, bytes]:
    """Descarga la miniatura y, si existe, una versión más grande de la misma imagen."""
    original = download_image(url, client)
    base = max(image_size(original) or (0, 0))
    for candidate in bigger_variants(url):
        try:
            data = download_image(candidate, client)
        except LogoError:
            continue
        size = image_size(data)
        if size and max(size) > base:
            return candidate, data
    return url, original
