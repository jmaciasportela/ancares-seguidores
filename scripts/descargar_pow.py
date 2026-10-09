#!/usr/bin/env python3
"""Cliente de diagnóstico de la PoW de FVCL. Python 3.9+, sin dependencias.

Una ejecución: GET inicial -> resolver un reto -> validar -> GET del fichero.
Las cookies solo viven en memoria. No hay reintentos ni ejecución periódica.
--sin-pow permite comprobar la respuesta sin resolver el reto.
Los eventos JSON por stdout permiten comparar pruebas y correlacionar horarios.
Salida: 0 descarga; 2 bloqueo/reto no compatible; 1 error local o de red.
No verifica internamente el contenido de un libro Excel: comprueba el tipo
anunciado y rechaza retos y páginas HTML que no sean exportaciones explícitas.
"""

import argparse
import hashlib
import http.cookiejar
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import (
    HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener,
)

DEFAULT_URL = "https://fvcl.es/es/tournament/1340427/calendar/3706760/all/export-xls"
MAX_BODY = 32 * 1024 * 1024


class Blocked(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    # Evita seguir redirecciones a login/otros destinos y ocultar el resultado.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def event(stage, **fields):
    print(json.dumps({
        "hora_utc": datetime.now(timezone.utc).isoformat(),
        "etapa": stage, **fields,
    }, ensure_ascii=False), flush=True)


def get(opener, url, stage, timeout):
    start = time.monotonic()
    req = Request(url, headers={
        "User-Agent": "FVCL-PoW-Diagnostic/1.0",
        "Accept": "*/*", "Accept-Encoding": "identity",
    })
    try:
        response = opener.open(req, timeout=timeout)
    except HTTPError as exc:
        response = exc  # Un 429 puede contener el reto esperado.
    with response:
        body = response.read(MAX_BODY + 1)
        status, headers = response.code, response.headers
    if len(body) > MAX_BODY:
        raise Blocked("Respuesta superior a 32 MiB; descarga detenida.")
    event(stage, http=status, segundos=round(time.monotonic() - start, 3),
          bytes=len(body), content_type=headers.get("Content-Type", ""),
          retry_after=headers.get("Retry-After"),
          cookies_emitidas=len(headers.get_all("Set-Cookie", [])))
    return status, headers, body


def parse_challenge(body):
    # Lee constantes; nunca evalúa JavaScript procedente de la página.
    text = body.decode("utf-8", errors="replace")
    values = {}
    for name in ("RETO", "FIRMA", "SEMILLA"):
        match = re.search(r"\b" + name + r"\s*=\s*(['\"])([^'\"\r\n]{1,1024})\1", text)
        if not match:
            return None
        values[name] = match.group(2)
    match = re.search(r"\bBITS\s*=\s*(\d+)\b", text)
    if not match:
        return None
    values["BITS"] = int(match.group(1))
    return values


def solve(seed, bits, seconds):
    if not 1 <= bits <= 24:
        raise Blocked("Dificultad fuera del intervalo de diagnóstico (1–24 bits).")
    # El JavaScript observado concatena semilla + nonce decimal, sin separador.
    if not seed.isascii():
        raise Blocked("Semilla no ASCII: revisar compatibilidad con el JavaScript.")
    prefix = seed.encode("ascii")
    target = 1 << (256 - bits)
    start = time.monotonic()
    nonce = 0
    while True:
        if nonce % 4096 == 0 and time.monotonic() - start >= seconds:
            raise Blocked("Agotado el tiempo máximo de cálculo PoW.")
        digest = hashlib.sha256(prefix + str(nonce).encode("ascii")).digest()
        if int.from_bytes(digest, "big") < target:
            elapsed = time.monotonic() - start
            event("pow_resuelta", bits=bits, intentos=nonce + 1,
                  segundos=round(elapsed, 3))
            return nonce
        nonce += 1


def save_download(response, output):
    status, headers, body = response
    if status != 200:
        raise Blocked(f"Descarga no entregada: HTTP {status}.")
    if parse_challenge(body):
        raise Blocked("El servidor sigue mostrando el reto; no se vuelve a intentar.")
    mime = headers.get_content_type().lower()
    disposition = headers.get("Content-Disposition", "").lower()
    excel_mimes = {
        "application/vnd.ms-excel", "application/msexcel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    excel_name = bool(re.search(r"\.xlsx?(?:[\"';\s]|$)", disposition))
    binary_excel = body.startswith((b"PK\x03\x04", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"))
    if not body or not (mime in excel_mimes or excel_name or
                       (mime == "application/octet-stream" and binary_excel)):
        raise Blocked(f"Respuesta no reconocida como Excel ({mime}); no se guarda.")
    with output.open("xb") as file:
        file.write(body)
    event("descarga_guardada", archivo=str(output.resolve()), bytes=len(body),
          sha256=hashlib.sha256(body).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=DEFAULT_URL, help="URL de producción o staging")
    parser.add_argument("-o", "--output", type=Path, default=Path("clasificacion.xls"))
    parser.add_argument("--sin-pow", action="store_true", help="Solo GET inicial")
    parser.add_argument("--timeout", type=float, default=30, help="Timeout de socket (s)")
    parser.add_argument("--max-pow-seconds", type=float, default=120, help="Presupuesto de cálculo (s)")
    args = parser.parse_args()
    parts = urlsplit(args.url)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
        parser.error("La URL debe ser HTTP(S), sin credenciales incrustadas.")
    if args.timeout <= 0 or args.max_pow_seconds <= 0:
        parser.error("Los tiempos deben ser positivos.")
    if args.output.exists():
        parser.error("El fichero de salida ya existe; elige otro nombre.")
    if any(key.startswith("_pow_") for key, _ in parse_qsl(parts.query)):
        parser.error("Usa la URL limpia, sin parámetros _pow_.")
    url = urlunsplit(parts._replace(fragment=""))
    jar = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar), NoRedirect())
    try:
        response = get(opener, url, "peticion_inicial", args.timeout)
        challenge = parse_challenge(response[2])
        if challenge is None or args.sin_pow:
            save_download(response, args.output)
            return 0
        if response[0] not in (200, 429):
            raise Blocked(f"Reto con estado inesperado: HTTP {response[0]}.")
        nonce = solve(challenge["SEMILLA"], challenge["BITS"], args.max_pow_seconds)
        query = parse_qsl(parts.query, keep_blank_values=True) + [
            ("_pow_r", challenge["RETO"]), ("_pow_f", challenge["FIRMA"]),
            ("_pow_n", str(nonce)),
        ]
        validation_url = urlunsplit(parts._replace(query=urlencode(query), fragment=""))
        validation = get(opener, validation_url, "validacion_pow", args.timeout)
        if validation[0] != 204:
            raise Blocked(f"Validación no aceptada: HTTP {validation[0]} (se esperaba 204).")
        event("sesion", cookies_en_memoria=len(jar))
        save_download(get(opener, url, "descarga", args.timeout), args.output)
        return 0
    except Blocked as exc:
        event("bloqueado", motivo=str(exc))
        return 2
    except (OSError, URLError, ValueError) as exc:
        # No imprime URL de validación, firmas ni cookies en los errores.
        event("error", tipo=type(exc).__name__, motivo="Error local o de conexión.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
