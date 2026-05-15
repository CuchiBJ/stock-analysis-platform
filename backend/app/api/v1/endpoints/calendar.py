from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.deps import get_db
from app.schemas.calendar import Event

router = APIRouter()


@router.get("/", response_model=List[Event])
async def get_calendar(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get upcoming calendar events"""
    # TODO: Implement calendar fetching
    return []
