from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.deps import get_db
from app.schemas.leader import ScoredStock

router = APIRouter()


@router.get("/top", response_model=List[ScoredStock])
async def get_top_scored(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get top scored stocks"""
    # TODO: Implement scoring system
    return []
