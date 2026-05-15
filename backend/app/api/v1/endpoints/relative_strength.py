from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.services.rs_service import RelativeStrengthService

router = APIRouter()


@router.get("/ranking")
async def get_rs_ranking(
    benchmark: str = Query("SPY", regex="^(SPY|QQQ)$"),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get stocks ranked by relative strength vs benchmark"""
    service = RelativeStrengthService(db)
    results = await service.get_rs_ranking(benchmark, limit)
    
    return {
        "results": results,
        "benchmark": benchmark,
        "total": len(results)
    }


@router.get("/leaders")
async def get_rs_leaders(
    benchmark: str = Query("SPY", regex="^(SPY|QQQ)$"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get stocks outperforming benchmark"""
    service = RelativeStrengthService(db)
    results = await service.get_leaders_vs_benchmark(benchmark, limit)
    
    return {
        "results": results,
        "benchmark": benchmark,
        "total": len(results)
    }


@router.get("/momentum")
async def get_rs_momentum(
    benchmark: str = Query("SPY", regex="^(SPY|QQQ)$"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get stocks with improving relative strength"""
    service = RelativeStrengthService(db)
    results = await service.get_rs_momentum_leaders(benchmark, limit)
    
    return {
        "results": results,
        "benchmark": benchmark,
        "total": len(results)
    }


@router.get("/sector/{sector}")
async def get_sector_rs(
    sector: str,
    benchmark: str = Query("SPY", regex="^(SPY|QQQ)$"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get top RS leaders within a sector"""
    service = RelativeStrengthService(db)
    results = await service.get_sector_rs_leaders(sector, benchmark, limit)
    
    return {
        "results": results,
        "sector": sector,
        "benchmark": benchmark,
        "total": len(results)
    }
