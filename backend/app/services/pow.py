"""Prueba de trabajo (PoW) que fvcl.es exige antes de servir los Excel.

La página de reto define RETO, FIRMA, SEMILLA y BITS. Hay que encontrar un
nonce tal que sha256(SEMILLA + str(nonce)) tenga BITS ceros iniciales, validarlo
con ?_pow_r=RETO&_pow_f=FIRMA&_pow_n=NONCE (responde 204 y deja una cookie) y
volver a pedir el fichero. Basado en scripts/descargar_pow.py.

Nunca se ejecuta JavaScript de la página: solo se leen esas constantes.
"""
import hashlib
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_BITS = 24


class PowError(Exception):
    pass


@dataclass
class Challenge:
    reto: str
    firma: str
    semilla: str
    bits: int


def parse_challenge(body: bytes) -> Optional[Challenge]:
    text = body.decode("utf-8", errors="replace")
    values = {}
    for name in ("RETO", "FIRMA", "SEMILLA"):
        m = re.search(r"\b" + name + r"\s*=\s*(['\"])([^'\"\r\n]{1,1024})\1", text)
        if not m:
            return None
        values[name] = m.group(2)
    m = re.search(r"\bBITS\s*=\s*(\d+)\b", text)
    if not m:
        return None
    return Challenge(values["RETO"], values["FIRMA"], values["SEMILLA"], int(m.group(1)))


def solve(challenge: Challenge, max_seconds: float) -> int:
    """Busca el nonce: semilla + nonce decimal, sin separador (como el JS de la página)."""
    if not 1 <= challenge.bits <= MAX_BITS:
        raise PowError(f"Dificultad fuera de rango ({challenge.bits} bits)")
    if not challenge.semilla.isascii():
        raise PowError("Semilla no ASCII")
    prefix = challenge.semilla.encode("ascii")
    target = 1 << (256 - challenge.bits)
    start = time.monotonic()
    nonce = 0
    while True:
        if nonce % 4096 == 0 and time.monotonic() - start >= max_seconds:
            raise PowError("Agotado el tiempo de cálculo de la PoW")
        if int.from_bytes(hashlib.sha256(prefix + str(nonce).encode("ascii")).digest(), "big") < target:
            return nonce
        nonce += 1


def validation_url(url: str, challenge: Challenge, nonce: int) -> str:
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True) + [
        ("_pow_r", challenge.reto),
        ("_pow_f", challenge.firma),
        ("_pow_n", str(nonce)),
    ]
    return urlunsplit(parts._replace(query=urlencode(query), fragment=""))
