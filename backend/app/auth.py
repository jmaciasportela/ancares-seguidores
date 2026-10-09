import hmac
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import get_settings

COOKIE = "ancares_admin"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="admin-session")


def check_password(password: str) -> bool:
    return hmac.compare_digest(password.encode(), get_settings().admin_password.encode())


def set_session(response: Response) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE,
        _serializer().dumps({"admin": True}),
        max_age=s.session_max_age,
        httponly=True,
        secure=s.cookie_secure,
        samesite="strict",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE)


def is_admin(request: Request) -> bool:
    token = request.cookies.get(COOKIE)
    if not token:
        return False
    try:
        data = _serializer().loads(token, max_age=get_settings().session_max_age)
    except (BadSignature, SignatureExpired):
        return False
    return bool(data.get("admin"))


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Necesitas iniciar sesión")


class RateLimiter:
    """Límite en memoria por IP. Suficiente para una app de un solo proceso."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, request: Request) -> None:
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "?"
        )
        now = time.monotonic()
        q = self.hits[ip]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(status_code=429, detail="Demasiadas peticiones, prueba más tarde")
        q.append(now)
