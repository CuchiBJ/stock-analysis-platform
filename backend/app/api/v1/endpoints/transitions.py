"""Operational Transitions API - Live transition feed and actionable setups"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from app.core.deps import get_db
from app.services.transition_engine import (
    TransitionEngine,
    OperationalTransition,
    FreshnessState
)
from app.services.setup_lifecycle_engine import SetupLifecycleEngine
from app.services.market_regime_engine import MarketRegimeEngine
from app.models.stock import StockMetrics
from sqlalchemy import select, and_, func
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/live")
async def get_live_transitions(
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
):
    """
    Get most recent operational transitions.
    
    Returns live feed of setup transitions with operational narratives.
    """
    try:
        transition_engine = TransitionEngine(db)
        
        # Get recent stock metrics (last 7 days instead of 2 days to capture more transitions)
        cutoff_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        result = await db.execute(
            select(StockMetrics)
            .where(
                and_(
                    StockMetrics.date >= cutoff_date,
                    StockMetrics.pullback_quality_score >= 55,  # Institutional quality
                    StockMetrics.distance_to_ema21_atr >= -0.8,  # ATR-normalized: near EMA21 (pullback or extended)
                    StockMetrics.distance_to_ema21_atr <= 0.5,  # ATR-normalized: not too extended above
                    StockMetrics.distance_to_high_52w_atr >= -3.0,  # ATR-normalized: within 3 ATRs of high
                    StockMetrics.avg_volume_10d >= 700000,
                    StockMetrics.adr_percent >= 3,
                    StockMetrics.current_price >= StockMetrics.low_52w * 1.7,
                    StockMetrics.current_price > StockMetrics.ema50
                )
            )
            .order_by(StockMetrics.date.desc())
            .limit(500)  # Get more records to ensure we have enough per symbol
        )
        recent_metrics = result.scalars().all()
        
        # Group by symbol and calculate transitions
        symbol_metrics: Dict[str, List[StockMetrics]] = {}
        for metrics in recent_metrics:
            if metrics.symbol not in symbol_metrics:
                symbol_metrics[metrics.symbol] = []
            symbol_metrics[metrics.symbol].append(metrics)
        
        transitions = []
        for symbol, metrics_list in symbol_metrics.items():
            current = metrics_list[0]
            
            if len(metrics_list) >= 2:
                previous = metrics_list[1]
                
                # Calculate operational transition
                op_transition = await transition_engine.calculate_operational_transition(
                    symbol, current, previous
                )
            else:
                # No previous data, assume stable
                op_transition = type('obj', (object,), {
                    'transition': OperationalTransition.STABLE,
                    'strength': 0.5,
                    'rs_change': 0.0,
                    'volume_change_pct': 0.0,
                    'narrative': 'No previous data for comparison.',
                    'timestamp': datetime.utcnow()
                })()
            
            # Determine severity
            severity = _determine_severity(op_transition.transition)
            
            transitions.append({
                "symbol": symbol,
                "transition": op_transition.transition.value,
                "direction": _get_transition_direction(op_transition.transition),
                "strength": op_transition.strength,
                "timestamp": op_transition.timestamp.isoformat(),
                "narrative": op_transition.narrative,
                "severity": severity,
                "rs_change": op_transition.rs_change if hasattr(op_transition, 'rs_change') else 0.0,
                "volume_change_pct": op_transition.volume_change_pct if hasattr(op_transition, 'volume_change_pct') else 0.0
            })
        
        # Sort by strength and severity
        transitions.sort(key=lambda x: (x["strength"], _severity_score(x["severity"])), reverse=True)
        
        return transitions[:limit]
        
    except Exception as e:
        logger.error(f"Error getting live transitions: {e}")
        raise


@router.get("/operational/{symbol}")
async def get_symbol_operational_transition(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get operational transition for a specific symbol.
    """
    try:
        transition_engine = TransitionEngine(db)
        
        # Get current and previous metrics
        result = await db.execute(
            select(StockMetrics)
            .where(StockMetrics.symbol == symbol.upper())
            .order_by(StockMetrics.date.desc())
            .limit(2)
        )
        metrics_list = result.scalars().all()
        
        if len(metrics_list) < 2:
            return {
                "symbol": symbol.upper(),
                "transition": "stable",
                "strength": 0.5,
                "narrative": "Insufficient data for transition analysis."
            }
        
        current = metrics_list[0]
        previous = metrics_list[1]
        
        # Calculate operational transition
        op_transition = await transition_engine.calculate_operational_transition(
            symbol.upper(), current, previous
        )
        
        return {
            "symbol": symbol.upper(),
            "transition": op_transition.transition.value,
            "strength": op_transition.strength,
            "rs_change": op_transition.rs_change,
            "volume_change_pct": op_transition.volume_change_pct,
            "structure_change": op_transition.structure_change,
            "narrative": op_transition.narrative,
            "timestamp": op_transition.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting symbol operational transition: {e}")
        raise


@router.get("/freshness/{symbol}")
async def get_symbol_freshness(
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get freshness metrics for a specific symbol.
    """
    try:
        transition_engine = TransitionEngine(db)
        lifecycle_engine = SetupLifecycleEngine(db)
        
        # Get current setup state
        current_state = await lifecycle_engine.get_current_state(symbol.upper())
        
        # Calculate days in state (simplified - use metrics date)
        result = await db.execute(
            select(StockMetrics)
            .where(StockMetrics.symbol == symbol.upper())
            .order_by(StockMetrics.date.desc())
            .limit(1)
        )
        metrics = result.scalar_one_or_none()
        
        if not metrics:
            return {"error": "Symbol not found"}
        
        # Simplified days calculation (in production, track actual state changes)
        days_in_state = 1  # Placeholder
        days_since_reclaim = None
        days_since_trigger = None
        
        # Calculate freshness
        freshness = await transition_engine.calculate_freshness(
            symbol.upper(),
            current_state,
            days_in_state,
            days_since_reclaim,
            days_since_trigger
        )
        
        return {
            "symbol": symbol.upper(),
            "freshness_state": freshness.state.value,
            "days_in_state": freshness.days_in_state,
            "days_since_reclaim": freshness.days_since_reclaim,
            "setup_decay": freshness.setup_decay,
            "freshness_score": freshness.freshness_score
        }
        
    except Exception as e:
        logger.error(f"Error getting symbol freshness: {e}")
        raise


@router.get("/actionable")
async def get_actionable_setups(
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db)
):
    """
    Get top actionable setups ranked by priority.
    
    Ranking based on:
    - Transition strength (40%)
    - Freshness (25%)
    - Regime alignment (20%)
    - Leader quality (15%)
    """
    try:
        transition_engine = TransitionEngine(db)
        regime_engine = MarketRegimeEngine(db)
        
        # Get market regime
        regime = await regime_engine.detect_regime()
        
        # Get active setups with high pullback quality (latest date per symbol)
        # Use subquery to filter to latest date per symbol
        subquery = (
            select(StockMetrics.symbol, func.max(StockMetrics.date).label('max_date'))
            .group_by(StockMetrics.symbol)
            .subquery()
        )
        
        result = await db.execute(
            select(StockMetrics)
            .join(subquery, and_(
                StockMetrics.symbol == subquery.c.symbol,
                StockMetrics.date == subquery.c.max_date
            ))
            .where(
                and_(
                    StockMetrics.pullback_quality_score >= 55,  # Institutional quality
                    StockMetrics.distance_to_ema21_atr >= -0.8,  # ATR-normalized: near EMA21 (pullback or extended)
                    StockMetrics.distance_to_ema21_atr <= 0.5,  # ATR-normalized: not too extended above
                    StockMetrics.distance_to_high_52w_atr >= -3.0,  # ATR-normalized: within 3 ATRs of high
                    StockMetrics.avg_volume_10d >= 700000,
                    StockMetrics.adr_percent >= 3
                )
            )
            .order_by(StockMetrics.pullback_quality_score.desc())
            .limit(50)
        )
        setups = result.scalars().all()
        
        actionable = []
        for setup in setups:
            # Calculate priority score
            priority_score = await _calculate_priority_score(
                setup, regime, transition_engine, db
            )
            
            # Generate narrative
            narrative = _generate_priority_narrative(setup, priority_score)
            
            actionable.append({
                "symbol": setup.symbol,
                "priority_score": priority_score,
                "narrative": narrative,
                "pullback_quality": setup.pullback_quality_score,
                "distance_to_ema21": setup.distance_to_ema21,
                "rs_spy": setup.relative_strength_spy,
                "volume_contraction": setup.volume_contraction
            })
        
        # Sort by priority score
        actionable.sort(key=lambda x: x["priority_score"], reverse=True)
        
        return actionable[:limit]
        
    except Exception as e:
        logger.error(f"Error getting actionable setups: {e}")
        raise


# --- Helper functions ---

def _determine_severity(transition: OperationalTransition) -> str:
    """Determine severity level of transition."""
    if transition in [OperationalTransition.FAILING]:
        return "critical"
    elif transition in [OperationalTransition.WEAKENING]:
        return "negative"
    elif transition in [OperationalTransition.IMPROVING, OperationalTransition.TIGHTENING, OperationalTransition.RECLAIMING]:
        return "positive"
    else:
        return "neutral"


def _severity_score(severity: str) -> int:
    """Convert severity to numeric score for sorting."""
    scores = {"critical": 3, "negative": 2, "neutral": 1, "positive": 0}
    return scores.get(severity, 0)


def _get_transition_direction(transition: OperationalTransition) -> str:
    """Get direction of transition for display."""
    if transition in [OperationalTransition.IMPROVING, OperationalTransition.TIGHTENING, OperationalTransition.RECLAIMING]:
        return "improving"
    elif transition in [OperationalTransition.WEAKENING, OperationalTransition.FAILING]:
        return "deteriorating"
    else:
        return "stable"


async def _calculate_priority_score(
    setup: StockMetrics,
    regime,
    transition_engine: TransitionEngine,
    db: AsyncSession
) -> float:
    """Calculate priority score for actionable setup."""
    score = 0.0
    
    # Transition strength (40%) - simplified for now
    score += 0.4 * (setup.pullback_quality_score / 100.0)
    
    # Freshness (25%) - assume fresh for now
    score += 0.25 * 0.8
    
    # Regime alignment (20%)
    if regime.regime.value in ["risk_on"]:
        score += 0.2 * 0.8
    else:
        score += 0.2 * 0.5
    
    # Leader quality (15%)
    leader_quality = setup.pullback_quality_score / 100.0
    score += 0.15 * leader_quality
    
    return score


def _generate_priority_narrative(setup: StockMetrics, priority_score: float) -> str:
    """Generate short narrative for actionable setup."""
    components = []
    
    if setup.distance_to_ema21 >= 0:
        components.append("EMA21 held")
    else:
        components.append("Near EMA21")
    
    if setup.volume_contraction and setup.volume_contraction > 20:
        components.append(f"Vol -{setup.volume_contraction:.0f}%")
    
    if setup.relative_strength_spy and setup.relative_strength_spy > 105:
        components.append("RS strong")
    
    if priority_score > 0.8:
        components.append("High priority")
    
    return ". ".join(components) + "."
