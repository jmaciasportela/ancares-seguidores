"""Utilidades comunes para leer los .xls que exporta la FVCL (plataforma Clupik).

Los ficheros son BIFF8 generados con PHPExcel y su contenedor OLE viene
"corrupto" a ojos de xlrd, por eso se abren con ``ignore_workbook_corruption``.
"""
import html
import re
import unicodedata
from typing import Any, List, Optional

import xlrd

OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class ParseError(Exception):
    pass


def looks_like_xls(data: bytes) -> bool:
    return data[:8] == OLE_SIGNATURE


def clean(value: Any) -> Any:
    """Normaliza el valor de una celda: texto sin entidades HTML ni espacios sobrantes."""
    if isinstance(value, str):
        return re.sub(r"\s+", " ", html.unescape(value)).strip()
    return value


def read_rows(data: bytes) -> List[List[Any]]:
    if not looks_like_xls(data):
        raise ParseError("El fichero no es un Excel .xls válido (¿página de bloqueo de la federación?)")
    try:
        book = xlrd.open_workbook(
            file_contents=data, ignore_workbook_corruption=True, logfile=_NullLog()
        )
    except Exception as exc:  # xlrd lanza varias excepciones propias
        raise ParseError(f"No se pudo abrir el Excel: {exc}") from exc
    sheet = book.sheet_by_index(0)
    return [[clean(v) for v in sheet.row_values(r)] for r in range(sheet.nrows)]


def norm(text: Optional[str]) -> str:
    """Minúsculas, sin tildes y con espacios simples, para comparar nombres."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def detect_kind(rows: List[List[Any]]) -> str:
    """Devuelve 'ranking' o 'calendar' según la fila de cabecera."""
    if not rows:
        raise ParseError("El Excel está vacío")
    header = {norm(h) for h in rows[0]}
    if "posicion" in header and "nombre" in header:
        return "ranking"
    if "equipo" in header and "jornada" in header:
        return "calendar"
    raise ParseError("No reconozco el Excel: no parece ni una clasificación ni un calendario")


class _NullLog:
    """xlrd escribe trazas de depuración al ignorar la corrupción; las descartamos."""

    def write(self, *_args, **_kwargs):
        pass
