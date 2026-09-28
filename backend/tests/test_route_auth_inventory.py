"""Fail closed when a new API route is registered without auth policy."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi.routing import APIRoute, APIWebSocketRoute

from app.main import app


PUBLIC_HTTP_ROUTES = {
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/verify-email"),
    ("POST", "/api/v1/auth/resend-verification"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/forgot-password"),
    ("POST", "/api/v1/auth/reset-password"),
    ("GET", "/api/v1/health/data-freshness"),
}

ACTIVE_USER_DEPENDENCIES = {
    "get_current_active_user",
    "require_active_user",
    "require_authenticated_mutation",
    "require_product_route_access",
    "require_protected_request",
}
CSRF_DEPENDENCIES = {
    "require_authenticated_mutation",
    "require_csrf_token",
    "require_product_route_access",
    "require_protected_request",
}
WEBSOCKET_DEPENDENCIES = {
    "get_current_websocket_user",
    "require_websocket_user",
    "authenticate_websocket",
}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _dependency_names(dependant) -> set[str]:
    names: set[str] = set()

    def visit(node) -> None:
        for dependency in getattr(node, "dependencies", ()):
            names.add(getattr(dependency.call, "__name__", repr(dependency.call)))
            visit(dependency)

    visit(dependant)
    return names


def _api_http_routes() -> Iterable[APIRoute]:
    return (
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1/")
    )


def test_public_route_allowlist_is_exact_and_all_product_routes_require_active_user():
    observed_public = set()
    missing_auth = []
    for route in _api_http_routes():
        dependencies = _dependency_names(route.dependant)
        for method in route.methods:
            identity = (method, route.path)
            if identity in PUBLIC_HTTP_ROUTES:
                observed_public.add(identity)
                continue
            if not dependencies.intersection(ACTIVE_USER_DEPENDENCIES):
                missing_auth.append(identity)

    assert observed_public == PUBLIC_HTTP_ROUTES
    assert missing_auth == []


def test_every_authenticated_product_mutation_has_csrf_protection():
    missing_csrf = []
    for route in _api_http_routes():
        dependencies = _dependency_names(route.dependant)
        for method in route.methods:
            identity = (method, route.path)
            if method in SAFE_METHODS or identity in PUBLIC_HTTP_ROUTES:
                continue
            if not dependencies.intersection(CSRF_DEPENDENCIES):
                missing_csrf.append(identity)

    assert missing_csrf == []


def test_websocket_routes_declare_handshake_authentication():
    websocket_routes = [
        route for route in app.routes if isinstance(route, APIWebSocketRoute)
    ]
    assert websocket_routes
    missing_auth = [
        route.path
        for route in websocket_routes
        if not _dependency_names(route.dependant).intersection(
            WEBSOCKET_DEPENDENCIES
        )
    ]
    assert missing_auth == []
