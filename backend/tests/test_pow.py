import hashlib

import httpx
import pytest

from app.config import get_settings
from app.services import fetcher
from app.services.pow import Challenge, PowError, parse_challenge, solve, validation_url

SEED = "a7fcbce54f8ac467"
BITS = 12
PAGE = (
    "<html><script>var RETO = '1791533437-%d-%s', FIRMA = 'fc264aa6', SEMILLA = '%s', BITS = %d;</script></html>"
    % (BITS, SEED, SEED, BITS)
).encode()


def test_parse_challenge_real_format():
    ch = parse_challenge(PAGE)
    assert ch == Challenge(f"1791533437-{BITS}-{SEED}", "fc264aa6", SEED, BITS)
    assert parse_challenge(b"<html>otra cosa</html>") is None


def test_solve_finds_valid_nonce():
    nonce = solve(Challenge("r", "f", SEED, BITS), max_seconds=10)
    digest = hashlib.sha256(f"{SEED}{nonce}".encode()).digest()
    assert int.from_bytes(digest, "big") >> (256 - BITS) == 0


def test_solve_rejects_absurd_difficulty():
    with pytest.raises(PowError):
        solve(Challenge("r", "f", SEED, 40), max_seconds=1)


def test_validation_url_keeps_query():
    url = validation_url("https://fvcl.es/x?a=1#frag", Challenge("R", "F", SEED, BITS), 42)
    assert url == "https://fvcl.es/x?a=1&_pow_r=R&_pow_f=F&_pow_n=42"


class FakeFvcl:
    """Servidor que exige la PoW: valida el nonce, da una cookie y solo entonces sirve el .xls."""

    def __init__(self, xls: bytes, accept: bool = True):
        self.xls, self.accept = xls, accept
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        params = dict(request.url.params)
        if "_pow_n" in params:
            digest = hashlib.sha256(f"{SEED}{params['_pow_n']}".encode()).digest()
            valid = int.from_bytes(digest, "big") >> (256 - BITS) == 0 and params["_pow_f"] == "fc264aa6"
            if valid and self.accept:
                return httpx.Response(204, headers={"set-cookie": "pow_ok=1; Path=/"})
            return httpx.Response(403)
        if "pow_ok=1" in request.headers.get("cookie", ""):
            return httpx.Response(200, headers={"content-type": "application/vnd.ms-excel"}, content=self.xls)
        return httpx.Response(429, headers={"content-type": "text/html"}, content=PAGE)


@pytest.fixture()
def fake_client(monkeypatch):
    def install(server):
        real = httpx.Client
        monkeypatch.setattr(fetcher.httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(server), **kw))

    return install


def test_fetch_solves_pow_and_reuses_cookie(fake_client, ranking_bytes):
    server = FakeFvcl(ranking_bytes)
    fake_client(server)
    with fetcher.make_client() as client:
        first = fetcher.fetch_xls("https://fvcl.es/ranking/export-xls", client=client)
        second = fetcher.fetch_xls("https://fvcl.es/calendar/export-xls", client=client)
    assert first.ok and first.data == ranking_bytes
    assert second.ok
    # reto + validación + descarga, y el segundo fichero va directo con la cookie
    assert len(server.requests) == 4
    assert all(r.headers["user-agent"].startswith("AncaresSeguidores/") for r in server.requests)


def test_fetch_reports_rejected_pow(fake_client, ranking_bytes):
    fake_client(FakeFvcl(ranking_bytes, accept=False))
    res = fetcher.fetch_xls("https://fvcl.es/x")
    assert not res.ok and res.blocked and "no aceptó" in res.message


def test_fetch_with_pow_disabled(fake_client, monkeypatch, ranking_bytes):
    server = FakeFvcl(ranking_bytes)
    fake_client(server)
    monkeypatch.setattr(get_settings(), "pow_enabled", False)
    res = fetcher.fetch_xls("https://fvcl.es/x")
    assert not res.ok and res.blocked and "desactivada" in res.message
    assert len(server.requests) == 1
