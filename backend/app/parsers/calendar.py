"""Parser del calendario de la FVCL.

Particularidades del Excel:
- La columna "Equipo" trae local y visitante pegados con un espacio
  ("CDF Voleibol Ancares UVa VCV Castilla"); se separan usando los nombres
  de la clasificación de la misma categoría.
- Los descansos vienen como "descansa X" o "X descansa".
- "Fecha" = "Sáb, 17/10/2026 17:00 GMT+2 Pabellón", solo el pabellón o vacía.
- "Resultado" repite la fecha, también cuando el partido ya se ha jugado.
- El resultado viene en "Parciales", todo seguido y sin separadores (visto en
  octubre de 2026): "131425112525181225&dash;&dash;" = sets 1-3 y parciales
  14-25, 11-25, 25-18, 12-25. Ver `parse_packed`. Si algún día llega con
  separadores ("3 - 1", "25-20 22-25"), también se entiende.
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
PACKED_RE = re.compile(r"^\s*(\d+)")
SET_TARGETS = (11, 15, 21, 25)  # puntos de set habituales (25, desempate a 15 y formatos de cantera)
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


def _finished_set(h: int, a: int) -> bool:
    """¿Puede ser un set terminado? Llega a los puntos del set con 2 de diferencia, o se alarga de 2 en 2."""
    w, lo = max(h, a), min(h, a)
    return w - lo >= 2 and (w in SET_TARGETS or (w > SET_TARGETS[0] and w - lo == 2))


def parse_packed(text: str) -> Optional[Tuple[int, int, List[List[int]]]]:
    """Parciales de Clupik sin separadores.

    «131425112525181225&dash;&dash;» = sets del local (1), del visitante (3) y los
    puntos de cada set seguidos (14-25, 11-25, 25-18, 12-25). Los sets que no se
    jugaron salen como «0» «0» o «&dash;». Como no hay separadores, se busca la
    única forma de partirlo en sets válidos que cuadre con los sets ganados; si
    no hay ninguna (acta incompleta) o hay varias, no se da por bueno.
    """
    m = PACKED_RE.match(text or "")
    digits = m.group(1) if m else ""
    if len(digits) < 4:
        return None
    hs, as_ = int(digits[0]), int(digits[1])
    rest = digits[2:]
    found: List[List[List[int]]] = []

    def walk(i: int, sets: List[List[int]]) -> None:
        if len(found) > 1:
            return
        if i == len(rest):
            played = [s for s in sets if s != [0, 0]]
            # Los sets sin jugar (0-0) solo pueden ir al final
            if played and sets[: len(played)] == played:
                won = (sum(h > a for h, a in played), sum(a > h for h, a in played))
                if won == (hs, as_):
                    found.append(played)
            return
        if len(sets) >= 7:
            return
        for lh in (1, 2):
            for la in (1, 2):
                j = i + lh + la
                if j > len(rest):
                    continue
                h_txt, a_txt = rest[i : i + lh], rest[i + lh : j]
                if (lh == 2 and h_txt[0] == "0") or (la == 2 and a_txt[0] == "0"):
                    continue  # sin ceros a la izquierda
                h, a = int(h_txt), int(a_txt)
                if (h, a) != (0, 0) and not _finished_set(h, a):
                    continue
                walk(j, sets + [[h, a]])

    walk(0, [])
    return (hs, as_, found[0]) if len(found) == 1 else None


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
    elif partials_text:
        packed = parse_packed(partials_text)
        if packed:
            home_sets, away_sets, partials = packed
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
        partials_text = str(cell(row, c_partials) or "")
        home_sets, away_sets, partials = parse_score(score_text, partials_text)
        # Para revisar el formato: el texto del que sale el resultado (o el que no se ha entendido)
        packed = partials_text.strip() if PACKED_RE.match(partials_text) else ""

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
                raw_result=score_text or packed or None,
            )
        )
    if not matches:
        raise ParseError("El calendario no tiene partidos")
    return matches
