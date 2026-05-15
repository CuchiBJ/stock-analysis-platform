from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.services.breadth_service import BreadthService

router = APIRouter()
breadth_service = BreadthService()


@router.get("/")
async def get_breadth(db: AsyncSession = Depends(get_db)):
    """Get market breadth metrics"""
    try:
        breadth_data = await breadth_service.calculate_breadth(db)
        return breadth_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
