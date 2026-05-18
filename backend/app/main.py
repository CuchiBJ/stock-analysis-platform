from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.deps import AsyncSessionLocal
from app.api.v1.api import api_router
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application started")
    
    yield
    
    # Shutdown
    logger.info("Application shutdown")


app = FastAPI(
    title="Stock Analysis Platform",
    description="Momentum and sector rotation analysis platform",
    version="0.1.0",
    lifespan=lifespan
)

# CORS configuration
origins = settings.cors_origins.split(",") if settings.cors_origins else ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
