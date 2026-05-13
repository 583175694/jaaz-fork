import hmac
import os
import time
from hashlib import sha256
from typing import Callable

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


SESSION_COOKIE_NAME = "ai_studio_session"
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", "604800"))


def is_auth_required() -> bool:
    return bool(os.getenv("APP_PASSWORD", "").strip())


def use_secure_cookie() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _session_secret() -> str:
    configured = os.getenv("SESSION_SECRET", "").strip()
    if configured:
        return configured
    return os.getenv("APP_PASSWORD", "")


def verify_password(password: str) -> bool:
    expected = os.getenv("APP_PASSWORD", "")
    if not expected:
        return True
    return hmac.compare_digest(password or "", expected)


def create_session_token(now: int | None = None) -> str:
    issued_at = int(now or time.time())
    payload = str(issued_at)
    signature = hmac.new(
        _session_secret().encode("utf-8"),
        payload.encode("utf-8"),
        sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def validate_session_token(token: str | None) -> bool:
    if not is_auth_required():
        return True
    if not token or "." not in token:
        return False

    issued_at_text, signature = token.split(".", 1)
    try:
        issued_at = int(issued_at_text)
    except ValueError:
        return False

    if issued_at + SESSION_MAX_AGE_SECONDS < int(time.time()):
        return False

    expected = hmac.new(
        _session_secret().encode("utf-8"),
        issued_at_text.encode("utf-8"),
        sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def request_is_authenticated(request: Request) -> bool:
    return validate_session_token(request.cookies.get(SESSION_COOKIE_NAME))


def set_session_cookie(response: Response) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=use_secure_cookie(),
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME)


def _is_public_path(path: str) -> bool:
    if path == "/api/health":
        return True
    if not path.startswith("/api/"):
        return True
    if path.startswith("/api/auth/"):
        return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        if not is_auth_required() or _is_public_path(request.url.path):
            return await call_next(request)

        if request_is_authenticated(request):
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            return JSONResponse(
                {"detail": "Authentication required"},
                status_code=401,
            )

        raise HTTPException(status_code=401, detail="Authentication required")
