from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .common import ParseError, norm, to_int

# cabecera normalizada -> atributo
COLUMNS = {
    "posicion": "position",
    "nombre": "team",
    "puntos": "points",
    "partidos jugados": "played",
    "partidos ganados": "won",
    "partidos perdidos": "lost",
    "a favor": "sets_for",
    "en contra": "sets_against",
    "puntos a favor": "points_for",
    "parciales en contra": "points_against",
    "ascenso / descenso": "promotion",
}


@dataclass
class StandingRow:
    position: int
    team: str
    points: int = 0
    played: int = 0
    won: int = 0
    lost: int = 0
    sets_for: int = 0
    sets_against: int = 0
    points_for: int = 0
    points_against: int = 0
    promotion: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


def parse_ranking(rows: List[List[Any]]) -> List[StandingRow]:
    if not rows:
        raise ParseError("Clasificación vacía")
    header = rows[0]
    index = {}
    for i, h in enumerate(header):
        attr = COLUMNS.get(norm(h))
        if attr and attr not in index:
            index[attr] = i
    if "team" not in index or "position" not in index:
        raise ParseError("La clasificación no tiene las columnas 'Posición' y 'Nombre'")

    result: List[StandingRow] = []
    for raw in rows[1:]:
        team = str(raw[index["team"]] or "").strip()
        if not team:
            continue
        values = {
            attr: (raw[i] if attr in ("team", "promotion") else to_int(raw[i]))
            for attr, i in index.items()
            if i < len(raw)
        }
        values["promotion"] = str(values.get("promotion") or "").strip() or None
        values["team"] = team
        values["extra"] = {str(h): raw[i] for i, h in enumerate(header) if h and i < len(raw)}
        result.append(StandingRow(**values))

    if not result:
        raise ParseError("La clasificación no tiene equipos")
    result.sort(key=lambda s: s.position)
    return result
