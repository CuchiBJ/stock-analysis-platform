from app.api.v1.endpoints.transitions import router


def test_forming_route_replaces_actionable_contract():
    paths = {route.path for route in router.routes}
    assert "/forming" in paths
    assert "/forming/all" in paths
    assert "/actionable" not in paths


def test_forming_limit_is_capped_by_route_contract():
    route = next(route for route in router.routes if route.path == "/forming")
    limit = next(field for field in route.dependant.query_params if field.name == "limit")
    metadata = repr(limit.field_info.metadata)
    assert "ge=1" in metadata
    assert "le=6" in metadata
