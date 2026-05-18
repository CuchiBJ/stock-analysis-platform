"""API endpoints for Market Regime Engine"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.services.market_regime_engine import MarketRegimeEngine
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market-regime", tags=["market-regime"])


@router.get("/current")
async def get_current_market_regime(db: AsyncSession = Depends(get_db)):
    """
    Get current market regime analysis.
    
    Returns comprehensive analysis including regime state, breadth quality,
    leadership health, speculative appetite, and confidence.
    """
    try:
        regime_engine = MarketRegimeEngine(db)
        analysis = await regime_engine.detect_regime()
        
        return {
            "regime": analysis.regime.value,
            "breadth_quality": analysis.breadth_quality,
            "leadership_health": analysis.leadership_health,
            "speculative_appetite": analysis.speculative_appetite,
            "sector_expansion": analysis.sector_expansion,
            "pullback_environment_quality": analysis.pullback_environment_quality,
            "confidence": analysis.confidence,
            "summary": analysis.get_summary()
        }
        
    except Exception as e:
        logger.error(f"Error getting current market regime: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_market_regime_history(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical market regime data.
    
    Returns regime history for the specified number of days.
    Note: This requires historical data tracking to be implemented.
    """
    try:
        # For now, return current regime as placeholder
        # Full implementation would require historical tracking
        regime_engine = MarketRegimeEngine(db)
        analysis = await regime_engine.detect_regime()
        
        return {
            "message": "Historical tracking not yet implemented",
            "current_regime": analysis.regime.value,
            "days_requested": days
        }
        
    except Exception as e:
        logger.error(f"Error getting market regime history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis")
async def get_market_regime_analysis(db: AsyncSession = Depends(get_db)):
    """
    Get detailed market regime analysis with recommendations.
    
    Returns regime analysis with trading recommendations based on
    current market conditions.
    """
    try:
        regime_engine = MarketRegimeEngine(db)
        analysis = await regime_engine.detect_regime()
        
        # Generate recommendations based on regime
        recommendations = _generate_regime_recommendations(analysis)
        
        return {
            "regime": analysis.regime.value,
            "analysis": {
                "breadth_quality": analysis.breadth_quality,
                "leadership_health": analysis.leadership_health,
                "speculative_appetite": analysis.speculative_appetite,
                "sector_expansion": analysis.sector_expansion,
                "pullback_environment_quality": analysis.pullback_environment_quality,
                "confidence": analysis.confidence
            },
            "recommendations": recommendations,
            "summary": analysis.get_summary()
        }
        
    except Exception as e:
        logger.error(f"Error getting market regime analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generate_regime_recommendations(analysis) -> dict:
    """
    Generate trading recommendations based on market regime.
    """
    regime = analysis.regime.value
    
    recommendations = {
        "setup_focus": "",
        "position_sizing": "",
        "risk_management": "",
        "sector_focus": ""
    }
    
    if regime == "risk_on":
        recommendations["setup_focus"] = "Focus on continuation setups and trigger_ready states. Aggressive entries on quality pullbacks."
        recommendations["position_sizing"] = "Normal to slightly larger position sizes. Confidence in continuation is high."
        recommendations["risk_management"] = "Standard stop losses. Trailing stops on successful continuations."
        recommendations["sector_focus"] = "Focus on leading sectors with strong breadth. Look for sector expansion."
    elif regime == "risk_off":
        recommendations["setup_focus"] = "Very selective. Only highest quality setups. Avoid emerging setups."
        recommendations["position_sizing"] = "Smaller position sizes. Reduce exposure significantly."
        recommendations["risk_management"] = "Tighter stop losses. Quick exits on first sign of failure."
        recommendations["sector_focus"] = "Defensive sectors only. Avoid high-beta sectors."
    elif regime == "transition":
        recommendations["setup_focus"] = "Caution. Wait for regime clarification before new entries."
        recommendations["position_sizing"] = "Reduced position sizes. Build positions gradually."
        recommendations["risk_management"] = "Wider stop losses to account for volatility. Quick profit taking."
        recommendations["sector_focus"] = "Neutral. Avoid taking strong directional sector bets."
    elif regime == "choppy":
        recommendations["setup_focus"] = "Avoid new entries. Focus on managing existing positions."
        recommendations["position_sizing"] = "Very small position sizes or stay in cash."
        recommendations["risk_management"] = "Very tight risk management. Quick exits on any whipsaw."
        recommendations["sector_focus"] = "Avoid sector bets. Market lacks clear direction."
    
    return recommendations
