from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.deps import get_db
from app.services.index_service import IndexService

router = APIRouter()
index_service = IndexService()


@router.get("/")
async def get_indices(db: AsyncSession = Depends(get_db)):
    """Get all major indices (SPY, QQQ, IWM, DIA) with current data"""
    try:
        indices_data = await index_service.get_all_indices(db)
        return indices_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}")
async def get_index(symbol: str, db: AsyncSession = Depends(get_db)):
    """Get specific index by symbol"""
    try:
        index_data = await index_service._get_index_data(db, symbol)
        if not index_data:
            raise HTTPException(status_code=404, detail=f"Index {symbol} not found")
        return index_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
