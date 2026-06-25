from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.core.deps import get_db
from app.services.sector_service import SectorService
from app.services.universe_filters import QUALITY_FILTERS
from app.models.stock import Stock, StockMetrics
from app.schemas.sector import Sector as SectorSchema

router = APIRouter()


@router.get("/performance")
async def get_sector_performance(
    timeframe: str = Query("daily", description="Timeframe: daily, weekly, monthly"),
    db: AsyncSession = Depends(get_db)
):
    """Calculate sector performance from stock data with enhanced metrics"""
    try:
        sector_service = SectorService(db)
        sector_performance = await sector_service.calculate_sector_performance()
        return sector_performance
    except Exception as e:
        import traceback
        print(f"Error in get_sector_performance: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rotation")
async def get_sector_rotation(
    lookback: int = Query(5, ge=2, le=20, description="Trading sessions to look back"),
    db: AsyncSession = Depends(get_db)
):
    """Sector rotation by momentum — which market_groups are gaining/losing leadership."""
    try:
        sector_service = SectorService(db)
        return await sector_service.calculate_sector_rotation(lookback)
    except Exception as e:
        import traceback
        print(f"Error in get_sector_rotation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/group-stocks")
async def get_group_stocks(
    group: str = Query(..., description="market_group name, e.g. 'Mining & Metals'"),
    limit: int = Query(60, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Constituent stocks of a market_group, ranked by score + structure."""
    try:
        sector_service = SectorService(db)
        return await sector_service.get_group_constituents(group, limit)
    except Exception as e:
        import traceback
        print(f"Error in get_group_stocks: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaders")
async def get_sector_leaders(
    sector: str = Query(..., description="Sector name"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get top leaders in a specific sector"""
    try:
        sector_service = SectorService(db)
        leaders = await sector_service.get_sector_leaders(sector, limit)
        return leaders
    except Exception as e:
        import traceback
        print(f"Error in get_sector_leaders: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/breadth")
async def get_market_breadth(db: AsyncSession = Depends(get_db)):
    """Calculate market breadth metrics over institutional-quality universe."""
    result = await db.execute(
        select(StockMetrics).join(Stock, Stock.symbol == StockMetrics.symbol)
        .where(Stock.is_active == True, *QUALITY_FILTERS)
    )
    metrics = result.scalars().all()
    
    if not metrics:
        return {
            "above_ema20": 0,
            "above_ema50": 0,
            "new_highs": 0,
            "new_lows": 0,
            "advancers": 0,
            "decliners": 0
        }
    
    total = len(metrics)
    above_ema20 = sum(1 for m in metrics if m.distance_to_ema20 > 0)
    above_ema50 = sum(1 for m in metrics if m.distance_to_ema50 > 0)
    
    # Near 52-week high (within 5%)
    new_highs = sum(1 for m in metrics if m.distance_to_high_52w is not None and m.distance_to_high_52w >= 0 and m.distance_to_high_52w < 5)
    
    # Near 52-week low (simplified as far from high)
    new_lows = sum(1 for m in metrics if m.distance_to_high_52w is not None and m.distance_to_high_52w < -20)
    
    # Advancers/decliners (using distance to EMA20)
    advancers = sum(1 for m in metrics if m.distance_to_ema20 > 0)
    decliners = sum(1 for m in metrics if m.distance_to_ema20 < 0)
    
    return {
        "above_ema20": round((above_ema20 / total) * 100, 1) if total > 0 else 0,
        "above_ema50": round((above_ema50 / total) * 100, 1) if total > 0 else 0,
        "new_highs": new_highs,
        "new_lows": new_lows,
        "advancers": advancers,
        "decliners": decliners
    }
