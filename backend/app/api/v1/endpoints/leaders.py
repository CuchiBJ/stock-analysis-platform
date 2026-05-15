from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.deps import get_db
from app.schemas.leader import LeaderData
from app.services.leader_service import LeaderService

router = APIRouter()


@router.get("/", response_model=List[LeaderData])
async def get_leaders(
    limit: int = Query(50, ge=1, le=100),
    sort: str = Query("score", description="Sort by: score, gain, rvol"),
    db: AsyncSession = Depends(get_db)
):
    """Get top leaders by score"""
    try:
        leader_service = LeaderService(db)
        leaders = await leader_service.get_leaders(limit, sort)
        return leaders
    except Exception as e:
        import traceback
        print(f"Error in get_leaders: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
