"""Quality Swing Setups Scanner API endpoints"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.deps import get_db
from app.services.quality_swing_scanner_service import QualitySwingScannerService

router = APIRouter()


@router.get("/")
async def get_quality_swing_setups(
    limit: int = Query(50, ge=1, le=100),
    min_score: float = Query(60, ge=0, le=100),
    max_distance_ema9: float = Query(5, ge=0, le=20),
    max_distance_ema21: float = Query(8, ge=0, le=25),
    max_distance_ath: float = Query(-15, ge=-50, le=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Get quality swing setups - stocks meeting institutional swing trading criteria
    
    Criteria:
    - Weekly uptrend intact (weekly_trend_quality >= 0.6)
    - Near ATH (within 15%)
    - Strong RS (rs_spy > 50)
    - Within X% of EMA9/21
    - Volume contraction (volume_contraction > 0.1)
    - Strong weekly structure (weekly_tightness > 0.3)
    - Pullback quality score >= min_score
    - Setup quality in ['excellent', 'good', 'fair']
    - Liquidity (avg_volume_10d >= 700k)
    """
    service = QualitySwingScannerService(db)
    return await service.get_quality_swing_setups(
        limit=limit,
        min_score=min_score,
        max_distance_ema9=max_distance_ema9,
        max_distance_ema21=max_distance_ema21,
        max_distance_ath=max_distance_ath
    )
