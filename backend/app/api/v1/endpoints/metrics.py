from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.data.scheduler import DataScheduler
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/update")
async def update_metrics(limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Manually trigger metrics calculation"""
    scheduler = DataScheduler(lambda: db)
    count = await scheduler.trigger_metrics_update(limit=limit)
    return {"message": f"Metrics calculated for {count} symbols"}
