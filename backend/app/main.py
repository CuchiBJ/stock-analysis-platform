# Pin the process timezone to UTC before anything else. asyncpg binds a naive
# datetime to a TIMESTAMPTZ column using the OS-local zone, so on a non-UTC host
# every naive datetime.utcnow() write is shifted by the local offset. Forcing the
# process zone to UTC makes "naive == UTC" true, matching how the codebase uses
# utcnow() everywhere.
import os as _os_boot, time as _time_boot
_os_boot.environ["TZ"] = "UTC"
_time_boot.tzset()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.deps import AsyncSessionLocal
from app.api.v1.api import api_router
from app.services.realtime_price_service import get_realtime_price_service
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application started")

    # Cleanup scheduler_errors older than 7 days — operational table, not historical
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import delete
        from app.models.stock import SchedulerError
        async with AsyncSessionLocal() as session:
            cutoff = datetime.utcnow() - timedelta(days=7)
            await session.execute(delete(SchedulerError).where(SchedulerError.occurred_at < cutoff))
            await session.commit()
    except Exception as e:
        logger.warning(f"scheduler_errors cleanup skipped: {e}")

    yield

    # Shutdown
    logger.info("Application shutdown")


app = FastAPI(
    title="Stock Analysis Platform",
    description="Momentum and sector rotation analysis platform",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configuration — restrict to configured origins
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Stock Analysis Platform API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
