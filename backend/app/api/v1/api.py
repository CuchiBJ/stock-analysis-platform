from fastapi import APIRouter
from app.api.v1.endpoints import stocks, scanners, sectors, watchlists, data, relative_strength, indices, breadth, leaders, themes, calendar, scoring, capital_flow, pullbacks, quality_swing_scanner

api_router = APIRouter()

api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(scanners.router, prefix="/scanners", tags=["scanners"])
api_router.include_router(sectors.router, prefix="/sectors", tags=["sectors"])
api_router.include_router(watchlists.router, prefix="/watchlists", tags=["watchlists"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(relative_strength.router, prefix="/relative-strength", tags=["relative-strength"])
api_router.include_router(indices.router, prefix="/indices", tags=["indices"])
api_router.include_router(breadth.router, prefix="/breadth", tags=["breadth"])
api_router.include_router(leaders.router, prefix="/leaders", tags=["leaders"])
api_router.include_router(themes.router, prefix="/themes", tags=["themes"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
api_router.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
api_router.include_router(capital_flow.router, prefix="/capital-flow", tags=["capital-flow"])
api_router.include_router(pullbacks.router, prefix="/pullbacks", tags=["pullbacks"])
api_router.include_router(quality_swing_scanner.router, prefix="/quality-swing-scanner", tags=["quality-swing-scanner"])
