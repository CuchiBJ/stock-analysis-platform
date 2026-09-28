"""Focused contracts for HTTP, WebSocket, CORS, and health-route protection."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.websockets import WebSocketDisconnect

import app.core.auth as auth_dependencies
from app.api.v1.api import api_router
from app.api.v1.endpoints import websocket as websocket_endpoint_module
from app.core.auth import (
    AuthenticatedSession,
    configured_trusted_origins,
    get_current_websocket_user,
    require_protected_request,
)
from app.models.user import AuthSession, User, UserState
from app.services.auth_service import digest_token


NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _active_principal(*, csrf_token: str = "C" * 43) -> AuthenticatedSession:
    user = User(
        id=uuid4(),
        email="route-security@example.com",
        password_hash="not-a-real-hash",
        state=UserState.ACTIVE.value,
        email_verified_at=NOW,
    )
    session = AuthSession(
        user_id=user.id,
        token_digest=digest_token("S" * 43),
        csrf_token_digest=digest_token(csrf_token),
        expires_at=NOW + timedelta(days=1),
    )
    session.user = user
    return AuthenticatedSession(session=session, user=user)


def _request(method: str) -> Request:
    return Request({"type": "http", "method": method, "path": "/", "headers": []})


def _direct_dependency_names(route: APIRoute | APIWebSocketRoute) -> set[str]:
    return {
        getattr(dependency.call, "__name__", "")
        for dependency in route.dependant.dependencies
    }


def test_product_http_routes_use_the_central_protected_dependency():
    product_routes = [
        route
        for route in api_router.routes
        if isinstance(route, APIRoute)
        and not route.path.startswith("/auth/")
        and not route.path.startswith("/health/")
    ]

    assert product_routes
    assert all(
        "require_protected_request" in _direct_dependency_names(route)
        for route in product_routes
    )


def test_auth_and_health_are_explicit_public_router_exemptions():
    public_routes = [
        route
        for route in api_router.routes
        if isinstance(route, APIRoute)
        and (
            route.path.startswith("/auth/")
            or route.path.startswith("/health/")
        )
    ]

    assert public_routes
    assert all(
        "require_protected_request" not in _direct_dependency_names(route)
        for route in public_routes
    )


def test_protected_request_requires_csrf_only_for_unsafe_methods():
    principal = _active_principal()

    assert (
        asyncio.run(
            require_protected_request(
                _request("GET"), principal, principal.user, csrf_token=None
            )
        )
        is principal.user
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            require_protected_request(
                _request("POST"), principal, principal.user, csrf_token=None
            )
        )
    assert raised.value.status_code == 403

    assert (
        asyncio.run(
            require_protected_request(
                _request("DELETE"), principal, principal.user, csrf_token="C" * 43
            )
        )
        is principal.user
    )


def test_websocket_route_declares_handshake_authentication_dependency():
    websocket_routes = [
        route for route in api_router.routes if isinstance(route, APIWebSocketRoute)
    ]

    assert [route.path for route in websocket_routes] == ["/ws"]
    assert _direct_dependency_names(websocket_routes[0]) == {
        "get_current_websocket_user"
    }


def test_anonymous_websocket_is_rejected_before_manager_connect(monkeypatch):
    connected = False

    async def record_connect(*_args, **_kwargs):
        nonlocal connected
        connected = True

    monkeypatch.setattr(
        websocket_endpoint_module.websocket_manager, "connect", record_connect
    )
    test_app = FastAPI()
    test_app.include_router(websocket_endpoint_module.router)

    with TestClient(test_app) as client:
        with pytest.raises(WebSocketDisconnect) as raised:
            with client.websocket_connect("/ws?client_id=anonymous"):
                pass

    assert raised.value.code == 1008
    assert connected is False


def test_websocket_dependency_accepts_only_active_verified_sessions(monkeypatch):
    principal = _active_principal()

    class _WebSocket:
        cookies = {"__Host-session": "S" * 43}

    async def active_session(_db, _token):
        return principal.session

    monkeypatch.setattr(auth_dependencies, "lookup_session", active_session)
    assert (
        asyncio.run(get_current_websocket_user(_WebSocket(), object()))
        is principal.user
    )


def test_credentialed_origins_are_exact_https_origins(monkeypatch):
    monkeypatch.setattr(
        auth_dependencies.settings,
        "cors_origins",
        ",".join(
            [
                "https://app.example",
                "https://admin.example:8443/",
                "http://app.example",
                "https://*.example",
                "https://app.example/path",
                "https://user:secret@app.example",
            ]
        ),
    )

    assert configured_trusted_origins() == frozenset(
        {"https://app.example", "https://admin.example:8443"}
    )
