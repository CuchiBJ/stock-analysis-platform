"""API endpoints for Setup Lifecycle Engine"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.deps import get_db
from app.models.stock import StockMetrics
from app.services.setup_lifecycle_engine import SetupLifecycleEngine, SetupState
from app.services.setup_invalidation_engine import SetupInvalidationEngine
from app.services.setup_priority_engine import SetupPriorityEngine
from app.services.weekly_structure_calculator import WeeklyStructureCalculator
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/setup-lifecycle", tags=["setup-lifecycle"])


@router.get("/current-state/{symbol}")
async def get_current_setup_state(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get current setup state for a symbol.
    
    Returns the current state in the setup lifecycle along with
    confidence score and narrative explanation.
    """
    try:
        # Get latest metrics for symbol
        from sqlalchemy import select, func
        subquery = select(
            StockMetrics.symbol,
            func.max(StockMetrics.date).label('max_date')
        ).group_by(StockMetrics.symbol).subquery()
        
        result = await db.execute(
            select(StockMetrics)
            .join(
                subquery,
                (StockMetrics.symbol == subquery.c.symbol) &
                (StockMetrics.date == subquery.c.max_date)
            )
            .where(StockMetrics.symbol == symbol.upper())
        )
        metrics = result.scalar_one_or_none()
        
        if not metrics:
            raise HTTPException(status_code=404, detail=f"No metrics found for {symbol}")
        
        # Initialize engines
        lifecycle_engine = SetupLifecycleEngine(db)
        weekly_calculator = WeeklyStructureCalculator()
        
        # Detect current state
        current_state = lifecycle_engine.detect_current_state(metrics)
        
        # Calculate continuation probability
        continuation_prob = lifecycle_engine.calculate_continuation_probability(metrics)
        
        # Calculate weekly structure score
        weekly_structure = weekly_calculator.calculate_weekly_structure_score(metrics)
        
        # Generate narrative
        narrative = lifecycle_engine.generate_narrative(metrics, current_state)
        
        return {
            "symbol": symbol.upper(),
            "current_state": current_state.value,
            "continuation_probability": continuation_prob,
            "weekly_structure_score": weekly_structure.total_score,
            "weekly_structure_breakdown": weekly_structure.get_breakdown(),
            "narrative": narrative,
            "metrics": {
                "pullback_quality_score": metrics.pullback_quality_score,
                "distance_to_ema21": metrics.distance_to_ema21,
                "distance_to_ema50": metrics.distance_to_ema50,
                "distance_to_high_52w": metrics.distance_to_high_52w,
                "weekly_trend_quality": metrics.weekly_trend_quality,
                "relative_strength_spy": metrics.relative_strength_spy,
                "current_price": metrics.current_price,
                "avg_volume_10d": metrics.avg_volume_10d
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting setup state for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active-setups")
async def get_active_setups(
    limit: int = 50,
    min_score: float = 55.0,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all active setups with their current states.
    
    Returns setups that pass invalidation and have pullback_quality_score >= min_score.
    """
    try:
        # Initialize engines
        invalidation_engine = SetupInvalidationEngine(db)
        priority_engine = SetupPriorityEngine()
        lifecycle_engine = SetupLifecycleEngine(db)
        weekly_calculator = WeeklyStructureCalculator()
        
        # Get all symbols with pullback quality score
        from sqlalchemy import select, func
        subquery = select(
            StockMetrics.symbol,
            func.max(StockMetrics.date).label('max_date')
        ).group_by(StockMetrics.symbol).subquery()
        
        result = await db.execute(
            select(StockMetrics)
            .join(
                subquery,
                (StockMetrics.symbol == subquery.c.symbol) &
                (StockMetrics.date == subquery.c.max_date)
            )
            .where(StockMetrics.pullback_quality_score >= min_score)
            .limit(limit * 2)  # Get more to account for invalidation
        )
        all_metrics = result.scalars().all()
        
        # Filter through invalidation
        valid_symbols = []
        for metrics in all_metrics:
            invalidation_result = invalidation_engine.check_setup_validity(metrics)
            if invalidation_result.is_valid:
                valid_symbols.append(metrics)
        
        # Calculate priority scores for valid setups
        setup_priorities = []
        for metrics in valid_symbols:
            current_state = lifecycle_engine.detect_current_state(metrics)
            priority = priority_engine.calculate_priority_score(metrics, current_state)
            setup_priorities.append(priority)
        
        # Rank and filter
        ranked_setups = priority_engine.rank_setups(setup_priorities, limit=limit)
        
        # Format response
        response = []
        for priority in ranked_setups:
            # Get metrics for this symbol
            metrics_result = await db.execute(
                select(StockMetrics)
                .join(
                    subquery,
                    (StockMetrics.symbol == subquery.c.symbol) &
                    (StockMetrics.date == subquery.c.max_date)
                )
                .where(StockMetrics.symbol == priority.symbol)
            )
            metrics = metrics_result.scalar_one_or_none()
            
            if metrics:
                weekly_structure = weekly_calculator.calculate_weekly_structure_score(metrics)
                continuation_prob = lifecycle_engine.calculate_continuation_probability(metrics)
                narrative = lifecycle_engine.generate_narrative(metrics, priority.current_state)
                
                response.append({
                    "symbol": priority.symbol,
                    "current_state": priority.current_state.value,
                    "priority_score": priority.priority_score,
                    "priority_breakdown": priority.get_breakdown(),
                    "continuation_probability": continuation_prob,
                    "weekly_structure_score": weekly_structure.total_score,
                    "narrative": narrative,
                    "metrics": {
                        "pullback_quality_score": metrics.pullback_quality_score,
                        "distance_to_ema21": metrics.distance_to_ema21,
                        "distance_to_ema50": metrics.distance_to_ema50,
                        "distance_to_high_52w": metrics.distance_to_high_52w,
                        "weekly_trend_quality": metrics.weekly_trend_quality,
                        "relative_strength_spy": metrics.relative_strength_spy,
                        "current_price": metrics.current_price,
                        "avg_volume_10d": metrics.avg_volume_10d
                    }
                })
        
        return {
            "total_analyzed": len(all_metrics),
            "total_passed_invalidation": len(valid_symbols),
            "total_ranked": len(response),
            "setups": response
        }
        
    except Exception as e:
        logger.error(f"Error getting active setups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invalidation-stats")
async def get_invalidation_stats(db: AsyncSession = Depends(get_db)):
    """
    Get statistics on setup invalidation effectiveness.
    """
    try:
        invalidation_engine = SetupInvalidationEngine(db)
        stats = await invalidation_engine.get_invalidation_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting invalidation stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/priority-summary")
async def get_priority_summary(
    limit: int = 50,
    min_score: float = 55.0,
    db: AsyncSession = Depends(get_db)
):
    """
    Get summary statistics for setup priority ranking.
    """
    try:
        invalidation_engine = SetupInvalidationEngine(db)
        priority_engine = SetupPriorityEngine()
        lifecycle_engine = SetupLifecycleEngine(db)
        
        # Get all symbols with pullback quality score
        from sqlalchemy import select, func
        subquery = select(
            StockMetrics.symbol,
            func.max(StockMetrics.date).label('max_date')
        ).group_by(StockMetrics.symbol).subquery()
        
        result = await db.execute(
            select(StockMetrics)
            .join(
                subquery,
                (StockMetrics.symbol == subquery.c.symbol) &
                (StockMetrics.date == subquery.c.max_date)
            )
            .where(StockMetrics.pullback_quality_score >= min_score)
            .limit(limit * 2)
        )
        all_metrics = result.scalars().all()
        
        # Filter through invalidation
        valid_symbols = []
        for metrics in all_metrics:
            invalidation_result = invalidation_engine.check_setup_validity(metrics)
            if invalidation_result.is_valid:
                valid_symbols.append(metrics)
        
        # Calculate priority scores
        setup_priorities = []
        for metrics in valid_symbols:
            current_state = lifecycle_engine.detect_current_state(metrics)
            priority = priority_engine.calculate_priority_score(metrics, current_state)
            setup_priorities.append(priority)
        
        # Rank
        ranked_setups = priority_engine.rank_setups(setup_priorities, limit=limit)
        
        # Get summary
        summary = priority_engine.get_priority_summary(ranked_setups)
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting priority summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
