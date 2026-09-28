"""FastAPI authentication, account-state, CSRF, and Origin dependencies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated, Iterable, Mapping, Optional
from urllib.parse import urlsplit

from fastapi import (
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.models.user import AuthSession, User, UserState
from app.services.auth_service import lookup_session, token_matches


# The __Host- prefix instructs supporting browsers that the cookie must be
# Secure, Path=/, and have no Domain attribute.  Endpoint code in task 3.5 will
# use these constants when setting and clearing it.
SESSION_COOKIE_NAME = "__Host-session"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "lax"
CSRF_HEADER_NAME = "X-CSRF-Token"

_OPAQUE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
_UNSAFE_HTTP_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class AuthenticatedSession:
    """The database-backed identity resolved from one request cookie."""

    session: AuthSession
    user: User


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Session"},
    )


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _session_token_from_cookies(cookies: Mapping[str, str]) -> str | None:
    raw_token = cookies.get(SESSION_COOKIE_NAME)
    if raw_token is None or _OPAQUE_TOKEN_PATTERN.fullmatch(raw_token) is None:
        return None
    return raw_token


def parse_session_cookie(request: Request) -> str:
    """Return a syntactically valid opaque cookie or fail without fallbacks."""

    raw_token = _session_token_from_cookies(request.cookies)
    if raw_token is None:
        raise _unauthenticated()
    return raw_token


async def get_current_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthenticatedSession:
    """Resolve the request's server-side session from the secure cookie only."""

    raw_token = parse_session_cookie(request)
    session = await lookup_session(db, raw_token)
    if session is None or session.user is None:
        raise _unauthenticated()
    return AuthenticatedSession(session=session, user=session.user)


async def get_current_user(
    principal: Annotated[AuthenticatedSession, Depends(get_current_session)],
) -> User:
    """Require a valid session and return its user; never return anonymous."""

    return principal.user


async def get_current_active_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require a valid session belonging to an active, verified account."""

    if user.state != UserState.ACTIVE.value or user.email_verified_at is None:
        raise _forbidden("Account is not active")
    return user


# Alternative descriptive name for router-level dependencies.
require_active_user = get_current_active_user


async def require_csrf_token(
    principal: Annotated[AuthenticatedSession, Depends(get_current_session)],
    csrf_token: Annotated[Optional[str], Header(alias=CSRF_HEADER_NAME)] = None,
) -> None:
    """Validate the double-submit proof against the current session's digest."""

    if (
        csrf_token is None
        or _OPAQUE_TOKEN_PATTERN.fullmatch(csrf_token) is None
        or not token_matches(csrf_token, principal.session.csrf_token_digest)
    ):
        raise _forbidden("CSRF validation failed")


async def require_authenticated_mutation(
    user: Annotated[User, Depends(get_current_active_user)],
    _csrf: Annotated[None, Depends(require_csrf_token)],
) -> User:
    """Combined dependency for a state-changing authenticated endpoint."""

    return user


async def require_protected_request(
    request: Request,
    principal: Annotated[AuthenticatedSession, Depends(get_current_session)],
    user: Annotated[User, Depends(get_current_active_user)],
    csrf_token: Annotated[Optional[str], Header(alias=CSRF_HEADER_NAME)] = None,
) -> User:
    """Protect product routes and require CSRF only for unsafe HTTP methods.

    This dependency is installed once at the protected-router boundary.  It
    intentionally returns the active user even though router-level callers do
    not consume it; endpoint dependencies that need the identity reuse the
    same cached session resolution.
    """

    if request.method.upper() in _UNSAFE_HTTP_METHODS:
        await require_csrf_token(principal, csrf_token)
    return user


async def get_current_websocket_user(
    websocket: WebSocket,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Authenticate an active WebSocket caller before the connection is accepted."""

    raw_token = _session_token_from_cookies(websocket.cookies)
    if raw_token is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    session = await lookup_session(db, raw_token)
    user = session.user if session is not None else None
    if (
        user is None
        or user.state != UserState.ACTIVE.value
        or user.email_verified_at is None
    ):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return user


def configured_trusted_origins() -> frozenset[str]:
    """Return exact configured HTTPS origins suitable for credentialed CORS."""

    origins: set[str] = set()
    for configured in settings.cors_origins.split(","):
        origin = configured.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        try:
            hostname = parsed.hostname
            parsed.port  # Validate a configured numeric port when present.
        except ValueError:
            continue
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or "*" in parsed.netloc
            or origin != f"https://{parsed.netloc}"
        ):
            continue
        origins.add(origin)
    return frozenset(origins)


def is_trusted_origin(origin: str | None, trusted_origins: Iterable[str]) -> bool:
    """Check exact Origin membership; absent/null origins fail closed."""

    if not origin or origin == "null":
        return False
    return origin in frozenset(trusted_origins)


async def require_trusted_origin(
    origin: Annotated[Optional[str], Header(alias="Origin")] = None,
) -> None:
    """Reject unauthenticated authentication mutations from other origins."""

    if not is_trusted_origin(origin, configured_trusted_origins()):
        raise _forbidden("Origin not allowed")
