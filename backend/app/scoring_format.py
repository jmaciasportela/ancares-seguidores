"""Formatos de partido y validación de resultados provisionales.

Normativa FIVB/RFEVB: un set lo gana quien llega a los puntos del set con 2 de
diferencia (sin tope). Al mejor de N, el set decisivo se juega a `tiebreak`.
Con `mode="fixed"` se juegan siempre todos los sets (formatos de cantera).
La lógica del marcador vive en el frontend (src/lib/scoring.js); aquí solo se
valida que lo que se publica sea coherente.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError


class ScoreFormat(BaseModel):
    mode: Literal["best_of", "fixed"] = "best_of"
    sets: int = Field(default=5, ge=1, le=7)
    points: int = Field(default=25, ge=5, le=50)
    tiebreak: Optional[int] = Field(default=15, ge=5, le=50)


DEFAULT_FORMAT = ScoreFormat().model_dump()
MAX_SETS = 7
MAX_POINTS = 99


def format_of(raw: Optional[dict]) -> dict:
    """Formato guardado en la categoría, o el por defecto si falta o es inválido."""
    try:
        return ScoreFormat(**(raw or {})).model_dump()
    except (ValidationError, TypeError):
        return dict(DEFAULT_FORMAT)


class ResultError(ValueError):
    pass


def validate_partials(partials: List[List], home_sets: int, away_sets: int, finished_early: bool) -> List[list]:
    """Comprueba que los parciales sean coherentes y los devuelve normalizados.

    Cada set es [local, visitante, terminado]. Solo el último puede quedar sin
    terminar, y solo si el partido se dio por acabado antes de tiempo.
    """
    if not partials:
        raise ResultError("El resultado no tiene ningún set")
    if len(partials) > MAX_SETS:
        raise ResultError(f"Demasiados sets ({len(partials)})")
    clean: List[list] = []
    won_home = won_away = 0
    for i, item in enumerate(partials):
        if not isinstance(item, (list, tuple)) or len(item) not in (2, 3):
            raise ResultError(f"Set {i + 1} con formato incorrecto")
        h, a = item[0], item[1]
        done = bool(item[2]) if len(item) == 3 else True
        if not all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= MAX_POINTS for x in (h, a)):
            raise ResultError(f"Set {i + 1}: puntuación fuera de rango")
        if done:
            if abs(h - a) < 2 or max(h, a) < 5:
                raise ResultError(f"Set {i + 1} ({h}-{a}) no puede estar terminado")
            won_home += h > a
            won_away += a > h
        elif i != len(partials) - 1 or not finished_early:
            raise ResultError(f"El set {i + 1} está sin terminar")
        clean.append([h, a, done])
    if (won_home, won_away) != (home_sets, away_sets):
        raise ResultError(f"Los sets ({home_sets}-{away_sets}) no cuadran con los parciales ({won_home}-{won_away})")
    if all(h == 0 and a == 0 for h, a, _ in clean):
        raise ResultError("El marcador está a cero")
    return clean
