"""Pullbacks API endpoints for quality swing setups"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.deps import get_db
from app.services.pullback_service import PullbackService

router = APIRouter()


@router.get("/quality/")
async def get_quality_pullbacks(
    limit: int = Query(50, ge=1, le=100),
    min_score: float = Query(60, ge=0, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get quality pullbacks - strong leaders above EMA21
    
    Criteria:
    - Pullback quality score >= min_score
    - Price above EMA21 (optimal pullback zone)
    - Near ATH (within 20%)
    - Strong weekly structure
    - Volume contraction
    - Weekly uptrend intact
    """
    service = PullbackService(db)
    return await service.get_quality_pullbacks(
        limit=limit,
        min_score=min_score
    )


@router.get("/leaders-under-pressure/")
async def get_leaders_under_pressure(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get leaders under pressure - structurally strong stocks correcting orderly
    
    These are stocks that:
    - Have strong weekly structure
    - Are pulling back but maintaining structure
    - Approaching entry zones (EMA9/21)
    - Maintaining relative strength
    """
    service = PullbackService(db)
    return await service.get_leaders_under_pressure(limit=limit)


@router.get("/early-reclaims/")
async def get_early_reclaims(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get early reclaims - stocks that briefly lost EMA9/21 but are reclaiming quickly
    
    These show:
    - Brief loss of EMA9/21
    - Quick recovery
    - Buying volume entering
    - RS maintained
    """
    service = PullbackService(db)
    return await service.get_early_reclaims(limit=limit)


@router.get("/controlled/")
async def get_controlled_pullbacks(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Get controlled pullbacks - differentiate healthy pullbacks from distribution
    
    HEALTHY pullbacks show:
    - Volume decreasing
    - Small candles
    - Respecting EMA9/21
    - Strong RS
    - Orderly consolidation
    
    UNHEALTHY (distribution) shows:
    - Aggressive selling
    - Breakdown
    - RS deteriorating
    - Selling volume
    """
    service = PullbackService(db)
    return await service.get_controlled_pullbacks(limit=limit)
