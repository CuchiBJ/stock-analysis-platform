from fastapi import APIRouter, Depends
from app.core.auth import require_protected_request
from app.api.v1.endpoints import (
    auth,
    calibration,
    chat,
    data,
    health,
    journal,
    market_context,
    metrics,
    profile,
    queue,
    realtime,
    sectors,
    security_operations,
    stocks,
    transitions,
    websocket,
)

api_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_protected_request)])

api_router.include_router(auth.router, tags=["auth"])
# Explicitly public operational endpoints; these expose no account or journal
# data and remain available to container/load-balancer probes.
api_router.include_router(health.router, tags=["health"])

protected_router.include_router(profile.router, tags=["profile"])
protected_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
protected_router.include_router(sectors.router, prefix="/sectors", tags=["sectors"])
protected_router.include_router(data.router, prefix="/data", tags=["data"])
protected_router.include_router(market_context.router, tags=["market-context"])
# WebSockets have an explicit handshake dependency because HTTP Request
# dependencies cannot run on an ASGI WebSocket scope.
api_router.include_router(websocket.router, tags=["websocket"])
protected_router.include_router(
    transitions.router, prefix="/transitions", tags=["transitions"]
)
protected_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
protected_router.include_router(realtime.router, prefix="/realtime", tags=["realtime"])
protected_router.include_router(queue.router, prefix="/queue", tags=["queue"])
protected_router.include_router(calibration.router, tags=["calibration"])
protected_router.include_router(journal.router, tags=["journal"])
protected_router.include_router(chat.router, prefix="/chat", tags=["chat"])
protected_router.include_router(
    security_operations.router, tags=["security-operations"]
)

api_router.include_router(protected_router)
