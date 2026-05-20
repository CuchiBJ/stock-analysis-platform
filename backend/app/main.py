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
    
    # DatabasePollingDataSource disabled due to connection pool issues
    # Frontend uses REST API polling directly to backend endpoints
    # Backend endpoints query database with proper connection management
    
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
