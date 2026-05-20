"""API endpoints for Leader Health Calculator"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.core.cache import cache_manager
from app.services.leader_health_calculator import LeaderHealthCalculator
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leader-health", tags=["leader-health"])

_CACHE_KEY = "leader_health_current"
_CACHE_TTL = 120  # 2 minutes


@router.get("/current")
async def get_current_leader_health(db: AsyncSession = Depends(get_db)):
    """Get current leader health analysis (cached 2 min)."""
    cached = cache_manager.get(_CACHE_KEY)
    if cached is not None:
        return cached

    try:
        health_calculator = LeaderHealthCalculator(db)
        health_metrics = await health_calculator.calculate_leader_health()

        result = {
            "leaders_above_ema21": health_metrics.leaders_above_ema21,
            "failed_breakouts": health_metrics.failed_breakouts,
            "distribution_count": health_metrics.distribution_count,
            "pullback_quality_index": health_metrics.pullback_quality_index,
            "breakdown_count": health_metrics.breakdown_count,
            "reclaim_quality": health_metrics.reclaim_quality,
            "continuation_quality": health_metrics.continuation_quality,
            "rs_deterioration": health_metrics.rs_deterioration,
            "overall_health_score": health_metrics.overall_health_score,
            "summary": health_metrics.get_summary()
        }

        cache_manager.set(_CACHE_KEY, result, _CACHE_TTL)
        return result

    except Exception as e:
        logger.error(f"Error getting current leader health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_leader_health_history(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical leader health data.
    
    Returns leader health history for the specified number of days.
    Note: This requires historical data tracking to be implemented.
    """
    try:
        # For now, return current health as placeholder
        # Full implementation would require historical tracking
        health_calculator = LeaderHealthCalculator(db)
        health_metrics = await health_calculator.calculate_leader_health()
        
        return {
            "message": "Historical tracking not yet implemented",
            "current_health_score": health_metrics.overall_health_score,
            "days_requested": days
        }
        
    except Exception as e:
        logger.error(f"Error getting leader health history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis")
async def get_leader_health_analysis(db: AsyncSession = Depends(get_db)):
    """
    Get detailed leader health analysis with recommendations.
    
    Returns leader health analysis with trading recommendations based on
    current leadership conditions.
    """
    try:
        health_calculator = LeaderHealthCalculator(db)
        health_metrics = await health_calculator.calculate_leader_health()
        
        # Generate recommendations based on health score
        recommendations = _generate_health_recommendations(health_metrics)
        
        return {
            "health_metrics": {
                "leaders_above_ema21": health_metrics.leaders_above_ema21,
                "failed_breakouts": health_metrics.failed_breakouts,
                "distribution_count": health_metrics.distribution_count,
                "pullback_quality_index": health_metrics.pullback_quality_index,
                "breakdown_count": health_metrics.breakdown_count,
                "reclaim_quality": health_metrics.reclaim_quality,
                "continuation_quality": health_metrics.continuation_quality,
                "rs_deterioration": health_metrics.rs_deterioration,
                "overall_health_score": health_metrics.overall_health_score
            },
            "recommendations": recommendations,
            "summary": health_metrics.get_summary()
        }
        
    except Exception as e:
        logger.error(f"Error getting leader health analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generate_health_recommendations(health_metrics) -> dict:
    """
    Generate trading recommendations based on leader health.
    """
    health_score = health_metrics.overall_health_score
    
    recommendations = {
        "setup_focus": "",
        "position_sizing": "",
        "risk_management": "",
        "leadership_quality": ""
    }
    
    if health_score >= 0.8:
        recommendations["setup_focus"] = "Excellent leadership health. Focus on continuation setups and trigger_ready states. High confidence in institutional sponsorship."
        recommendations["position_sizing"] = "Normal to larger position sizes. Leadership is strong and supportive."
        recommendations["risk_management"] = "Standard stop losses. Leaders are likely to find support."
        recommendations["leadership_quality"] = "Very healthy leadership. Institutions are supporting quality names."
    elif health_score >= 0.6:
        recommendations["setup_focus"] = "Good leadership health. Focus on quality pullbacks and continuation setups. Moderate confidence."
        recommendations["position_sizing"] = "Normal position sizes. Leadership is generally supportive."
        recommendations["risk_management"] = "Standard stop losses. Monitor for signs of deterioration."
        recommendations["leadership_quality"] = "Healthy leadership. Most leaders are maintaining structure."
    elif health_score >= 0.4:
        recommendations["setup_focus"] = "Mixed leadership health. Be selective. Focus only on highest quality setups with strong individual metrics."
        recommendations["position_sizing"] = "Reduced position sizes. Leadership is showing signs of stress."
        recommendations["risk_management"] = "Tighter stop losses. Quick exits on signs of distribution."
        recommendations["leadership_quality"] = "Deteriorating leadership. Some leaders are breaking down."
    else:
        recommendations["setup_focus"] = "Poor leadership health. Avoid new entries. Focus on managing existing positions or stay in cash."
        recommendations["position_sizing"] = "Very small position sizes or stay in cash."
        recommendations["risk_management"] = "Very tight risk management. Avoid chasing failing leaders."
        recommendations["leadership_quality"] = "Unhealthy leadership. Distribution is widespread."
    
    return recommendations
