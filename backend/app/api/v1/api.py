from fastapi import APIRouter
from app.api.v1.endpoints import stocks, sectors, data, websocket, transitions, metrics, realtime, queue, market_context, calibration, health, journal, chat

api_router = APIRouter()

api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(sectors.router, prefix="/sectors", tags=["sectors"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(market_context.router, tags=["market-context"])
api_router.include_router(websocket.router, tags=["websocket"])
api_router.include_router(transitions.router, prefix="/transitions", tags=["transitions"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["realtime"])
api_router.include_router(queue.router, prefix="/queue", tags=["queue"])
api_router.include_router(calibration.router, tags=["calibration"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(journal.router, tags=["journal"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
