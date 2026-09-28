"""Public account flows and the authenticated session boundary."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    AuthenticatedSession,
    get_current_active_user,
    get_current_session,
    parse_session_cookie,
    require_authenticated_mutation,
    require_trusted_origin,
)
from app.core.config import settings
from app.core.deps import get_db
from app.models.user import User, normalize_email
from app.schemas.auth import (
    AuthMessage,
    CurrentUser,
    EmailRequest,
    LoginRequest,
    PasswordResetRequest,
    RegistrationRequest,
    SessionResponse,
    TokenRequest,
)
from app.services.auth_rate_limiter import (
    AuthRateLimitAction,
    AuthRateLimitExceeded,
    AuthRateLimiter,
    AuthRateLimiterUnavailable,
    auth_rate_limiter,
)
from app.services.auth_service import (
    SESSION_ABSOLUTE_LIFETIME,
    authenticate_user,
    create_session,
    issue_password_reset_token,
    issue_session_csrf,
    register_user,
    resend_verification_token,
    reset_password,
    revoke_current_session,
    verify_email_token,
)
from app.services.mailer import (
    Mailer,
    build_password_reset_url,
    build_verification_url,
    create_mailer,
)
from app.services.security_events import record_security_event


router = APIRouter(prefix="/auth")

GENERIC_ACCOUNT_MESSAGE = "If the account is eligible, an email has been sent."
GENERIC_LOGIN_ERROR = "Invalid email or password."
INVALID_TOKEN_ERROR = "The token is invalid or expired."


def get_auth_rate_limiter() -> AuthRateLimiter:
    return auth_rate_limiter


def get_mailer() -> Mailer:
    return create_mailer(settings)


def _request_source(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


async def _enforce_rate_limit(
    limiter: AuthRateLimiter,
    action: AuthRateLimitAction,
    request: Request,
    email: str,
) -> None:
    try:
        await limiter.enforce(action, source=_request_source(request), email=email)
    except AuthRateLimitExceeded as exc:
        record_security_event(
            "auth_rate_limit", "blocked", reason="limit_exceeded"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts.",
            headers={"Retry-After": str(max(1, exc.decision.retry_after_seconds))},
        ) from exc
    except AuthRateLimiterUnavailable as exc:
        record_security_event(
            "auth_rate_limit", "unavailable", reason="backend_unavailable"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable.",
        ) from exc


def _current_user(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.profile.display_name,
    )


@router.post(
    "/register",
    response_model=AuthMessage,
    status_code=status.HTTP_202_ACCEPTED,
)
async def register(
    payload: RegistrationRequest,
    request: Request,
    _origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> AuthMessage:
    await _enforce_rate_limit(
        limiter, AuthRateLimitAction.REGISTRATION, request, payload.email
    )
    try:
        issued = await register_user(
            db,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        duplicate = await db.scalar(
            select(User.id).where(User.email == normalize_email(payload.email))
        )
        if duplicate is None:
            raise
        issued = None

    if issued is not None:
        await mailer.send_verification_email(
            recipient=issued.user.email,
            verification_url=build_verification_url(issued.token),
        )
    return AuthMessage(message=GENERIC_ACCOUNT_MESSAGE)


@router.post("/verify-email", response_model=AuthMessage)
async def verify_email(
    payload: TokenRequest,
    _origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthMessage:
    user = await verify_email_token(db, payload.token)
    if user is None:
        await db.rollback()
        record_security_event(
            "auth_login", "failure", reason="invalid_credentials"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_TOKEN_ERROR)
    await db.commit()
    record_security_event("auth_login", "success")
    return AuthMessage(message="Email verified. You can now sign in.")


@router.post(
    "/resend-verification",
    response_model=AuthMessage,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resend_verification(
    payload: EmailRequest,
    request: Request,
    _origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> AuthMessage:
    await _enforce_rate_limit(
        limiter, AuthRateLimitAction.VERIFICATION_RESEND, request, payload.email
    )
    issued = await resend_verification_token(db, payload.email)
    await db.commit()
    if issued is not None:
        await mailer.send_verification_email(
            recipient=issued.user.email,
            verification_url=build_verification_url(issued.token),
        )
    return AuthMessage(message=GENERIC_ACCOUNT_MESSAGE)


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    _origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
) -> SessionResponse:
    await _enforce_rate_limit(limiter, AuthRateLimitAction.LOGIN, request, payload.email)
    user = await authenticate_user(db, email=payload.email, password=payload.password)
    if user is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_LOGIN_ERROR,
            headers={"WWW-Authenticate": "Session"},
        )

    created = await create_session(db, user.id)
    await db.commit()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=created.session_token,
        max_age=int(SESSION_ABSOLUTE_LIFETIME.total_seconds()),
        expires=created.expires_at,
        path=SESSION_COOKIE_PATH,
        secure=SESSION_COOKIE_SECURE,
        httponly=SESSION_COOKIE_HTTPONLY,
        samesite=SESSION_COOKIE_SAMESITE,
    )
    return SessionResponse(
        user=_current_user(user),
        csrf_token=created.csrf_token,
        expires_at=created.expires_at,
    )


@router.get("/session", response_model=SessionResponse)
async def current_session(
    principal: Annotated[AuthenticatedSession, Depends(get_current_session)],
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    csrf_token = await issue_session_csrf(db, principal.session)
    await db.commit()
    return SessionResponse(
        user=_current_user(user),
        csrf_token=csrf_token,
        expires_at=principal.session.expires_at,
    )


@router.post("/logout", response_model=AuthMessage)
async def logout(
    request: Request,
    response: Response,
    _user: Annotated[User, Depends(require_authenticated_mutation)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthMessage:
    raw_token = parse_session_cookie(request)
    await revoke_current_session(db, raw_token)
    await db.commit()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path=SESSION_COOKIE_PATH,
        secure=SESSION_COOKIE_SECURE,
        httponly=SESSION_COOKIE_HTTPONLY,
        samesite=SESSION_COOKIE_SAMESITE,
    )
    return AuthMessage(message="Signed out.")


@router.post(
    "/forgot-password",
    response_model=AuthMessage,
    status_code=status.HTTP_202_ACCEPTED,
)
async def forgot_password(
    payload: EmailRequest,
    request: Request,
    _origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limiter: Annotated[AuthRateLimiter, Depends(get_auth_rate_limiter)],
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> AuthMessage:
    await _enforce_rate_limit(limiter, AuthRateLimitAction.RECOVERY, request, payload.email)
    issued = await issue_password_reset_token(db, payload.email)
    await db.commit()
    if issued is not None:
        await mailer.send_password_reset_email(
            recipient=issued.user.email,
            reset_url=build_password_reset_url(issued.token),
        )
    return AuthMessage(message=GENERIC_ACCOUNT_MESSAGE)


@router.post("/reset-password", response_model=AuthMessage)
async def complete_password_reset(
    payload: PasswordResetRequest,
    _origin: Annotated[None, Depends(require_trusted_origin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthMessage:
    user = await reset_password(
        db,
        raw_token=payload.token,
        new_password=payload.new_password,
    )
    if user is None:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_TOKEN_ERROR)
    await db.commit()
    return AuthMessage(message="Password updated. Sign in with your new password.")
