"""Parser del calendario de la FVCL.

Particularidades del Excel:
- La columna "Equipo" trae local y visitante pegados con un espacio
  ("CDF Voleibol Ancares UVa VCV Castilla"); se separan usando los nombres
  de la clasificación de la misma categoría.
- Los descansos vienen como "descansa X" o "X descansa".
- "Fecha" = "Sáb, 17/10/2026 17:00 GMT+2 Pabellón", solo el pabellón o vacía.
- "Resultado" repite la fecha mientras el partido no se juega. El formato del
  resultado jugado aún no se ha visto: se acepta "3 - 1" y se guarda el texto
  original para poder ajustarlo.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .common import ParseError, norm, to_int

DATE_RE = re.compile(
    r"^(?:[^\W\d_]+\.?,?\s*)?"  # día de la semana opcional ("Sáb,")
    r"(\d{1,2})/(\d{1,2})/(\d{4})"
    r"(?:\s+(\d{1,2}):(\d{2}))?"
    r"(?:\s+GMT\s*([+-])(\d{1,2})(?::?(\d{2}))?)?"
    r"\s*(.*)$"
)
SETS_RE = re.compile(r"^\s*(\d)\s*[-–:]\s*(\d)\s*$")
PARTIAL_RE = re.compile(r"(\d{1,2})\s*[-–:]\s*(\d{1,2})")
BYE_WORD = "descansa"
LOCAL_TZ = ZoneInfo("Europe/Madrid")


@dataclass
class MatchRow:
    order: int
    round_no: int
    round_name: str
    raw_teams: str
    home: Optional[str] = None
    away: Optional[str] = None
    is_bye: bool = False
    starts_at: Optional[datetime] = None
    venue: Optional[str] = None
    home_sets: Optional[int] = None
    away_sets: Optional[int] = None
    partials: List[List[int]] = field(default_factory=list)
    raw_result: Optional[str] = None


def parse_when(text: str) -> Tuple[Optional[datetime], Optional[str]]:
    """'Sáb, 17/10/2026 17:00 GMT+2 Fuente la Mora' -> (datetime con zona, 'Fuente la Mora').

    Clupik escribe el desfase vigente el día de la exportación (GMT+2 en verano)
    también para partidos de invierno, así que el "GMT+X" no es fiable: la hora
    de reloj se interpreta siempre en Europe/Madrid.
    """
    text = (text or "").strip()
    if not text:
        return None, None
    m = DATE_RE.match(text)
    if not m:
        return None, text  # solo pabellón
    day, month, year, hh, mm, _sign, _tz_h, _tz_m, venue = m.groups()
    try:
        when = datetime(int(year), int(month), int(day), int(hh or 0), int(mm or 0), tzinfo=LOCAL_TZ)
    except ValueError:
        return None, text
    return when, (venue.strip() or None)


def parse_score(result: str, partials_text: str) -> Tuple[Optional[int], Optional[int], List[List[int]]]:
    partials: List[List[int]] = []
    if partials_text and not set(partials_text) <= set("-–— "):
        partials = [[int(a), int(b)] for a, b in PARTIAL_RE.findall(partials_text)]

    home_sets = away_sets = None
    m = SETS_RE.match(result or "")
    if m:
        home_sets, away_sets = int(m.group(1)), int(m.group(2))
    elif partials:
        home_sets = sum(1 for a, b in partials if a > b)
        away_sets = sum(1 for a, b in partials if b > a)
    return home_sets, away_sets, partials


def split_teams(raw: str, known: Iterable[str]) -> Tuple[Optional[str], Optional[str], bool]:
    """Separa "Local Visitante" usando los equipos conocidos. Devuelve (home, away, is_bye)."""
    raw = (raw or "").strip()
    n = norm(raw)
    if n.startswith(BYE_WORD + " ") or n == BYE_WORD:
        return raw[len(BYE_WORD):].strip() or None, None, True
    if n.endswith(" " + BYE_WORD):
        return raw[: -len(BYE_WORD)].strip(), None, True

    teams = sorted({t for t in known if t}, key=len, reverse=True)
    by_norm = {norm(t): t for t in teams}

    # 1) prefijo conocido + resto conocido
    for t in teams:
        nt = norm(t)
        if n.startswith(nt + " "):
            rest = n[len(nt) + 1:]
            if rest in by_norm:
                return t, by_norm[rest], False
    # 2) prefijo conocido (rival que no está en la clasificación)
    for t in teams:
        nt = norm(t)
        if n.startswith(nt + " "):
            return t, raw[len(t) + 1:].strip(), False
    # 3) sufijo conocido
    for t in teams:
        nt = norm(t)
        if n.endswith(" " + nt):
            return raw[: len(raw) - len(t) - 1].strip(), t, False
    # Sin forma de separar: se deja el texto entero como local
    return raw, None, False


def _col(header: List[str], *candidates: str) -> Optional[int]:
    normalized = [norm(h) for h in header]
    for cand in candidates:
        if cand in normalized:
            return normalized.index(cand)
    return None


def parse_calendar(rows: List[List[Any]], known_teams: Iterable[str]) -> List[MatchRow]:
    if not rows:
        raise ParseError("Calendario vacío")
    header = [str(h) for h in rows[0]]
    c_round_no = _col(header, "nº jornada", "n jornada", "no jornada")
    c_round = _col(header, "jornada")
    c_teams = _col(header, "equipo", "equipos")
    c_date = _col(header, "fecha")
    c_partials = _col(header, "parciales")
    c_result = _col(header, "resultado")
    if c_teams is None or (c_round is None and c_round_no is None):
        raise ParseError("El calendario no tiene las columnas 'Jornada' y 'Equipo'")

    known = list(known_teams)

    def cell(row: List[Any], idx: Optional[int]) -> Any:
        return row[idx] if idx is not None and idx < len(row) else ""

    matches: List[MatchRow] = []
    for order, row in enumerate(rows[1:], start=1):
        raw_teams = str(cell(row, c_teams) or "").strip()
        if not raw_teams:
            continue
        round_name = str(cell(row, c_round) or "").strip()
        round_no = to_int(cell(row, c_round_no)) or to_int(re.sub(r"\D", "", round_name))
        home, away, is_bye = split_teams(raw_teams, known)

        date_text = str(cell(row, c_date) or "")
        result_text = str(cell(row, c_result) or "").strip()
        starts_at, venue = parse_when(date_text)

        # Mientras no se juega, "Resultado" repite la fecha: no es un resultado
        if result_text == date_text.strip() or DATE_RE.match(result_text):
            score_text = ""
        else:
            score_text = result_text
        home_sets, away_sets, partials = parse_score(score_text, str(cell(row, c_partials) or ""))

        matches.append(
            MatchRow(
                order=order,
                round_no=round_no,
                round_name=round_name or f"Jornada {round_no}",
                raw_teams=raw_teams,
                home=home,
                away=away,
                is_bye=is_bye,
                starts_at=starts_at,
                venue=venue,
                home_sets=home_sets,
                away_sets=away_sets,
                partials=partials,
                raw_result=score_text or None,
            )
        )
    if not matches:
        raise ParseError("El calendario no tiene partidos")
    return matches
