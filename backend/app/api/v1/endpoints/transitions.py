"""Operational transitions and formation-stage preparation API."""

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timedelta, date
from statistics import mean, median
from app.core.deps import get_db
from app.services.transition_engine import TransitionEngine
from app.services.setup_lifecycle_engine import SetupLifecycleEngine
from app.services.websocket_manager import websocket_manager
from app.services.live_transition_service import LiveTransitionSelector
from app.services.forming_setup_service import FormationSetupService
from app.schemas.transitions import FormationEnvelopeResponse
from app.models.stock import StockMetrics, TransitionObservation
from sqlalchemy import select, and_, func
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/live")
async def get_live_transitions(
    limit: int = Query(10, ge=1, le=20),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get most recent operational transitions.
    
    Returns live feed of setup transitions with operational narratives.
    """
    try:
        result_transitions = await LiveTransitionSelector(db).select(limit=limit)

        # Broadcast top transition to WebSocket subscribers (non-blocking)
        if result_transitions and websocket_manager.get_connection_count() > 0:
            top = result_transitions[0]
            async def _broadcast():
                await websocket_manager.broadcast('transitions', {'channel': 'transitions', 'data': top})
            if background_tasks:
                background_tasks.add_task(_broadcast)

        return result_transitions
        
    except Exception as e:
        logger.error(f"Error getting live transitions: {e}")
        raise


@router.get("/forming", response_model=FormationEnvelopeResponse)
async def get_forming_setups(
    limit: int = Query(6, ge=1, le=6),
    db: AsyncSession = Depends(get_db),
):
    """Return scarce institutional structures preparing for a feed transition."""
    return await FormationSetupService(db).get_forming_setups(limit=limit)


@router.get("/forming/all", response_model=FormationEnvelopeResponse)
async def get_all_forming_setups(
    db: AsyncSession = Depends(get_db),
):
    """Return the complete ranked formation catalog for progressive disclosure."""
    return await FormationSetupService(db).get_forming_setups(limit=None)


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


@router.get("/track-record")
async def track_record(
    transition_type: str = Query(..., description="Transition type, e.g. entering_pullback"),
    regime: Optional[str] = Query(None, description="Market regime filter (bull/bear/etc)"),
    days: int = Query(90, ge=1, le=365, description="Lookback window in days"),
    db: AsyncSession = Depends(get_db),
):
    since = date.today() - timedelta(days=days)
    filters = [
        TransitionObservation.transition_type == transition_type.lower(),
        TransitionObservation.date_detected >= since,
        TransitionObservation.outcome_status != 'PENDING',
        TransitionObservation.outcome_status != 'INSUFFICIENT_DATA',
    ]
    if regime:
        filters.append(TransitionObservation.regime_at_detection == regime.lower())
    q = select(TransitionObservation).where(and_(*filters))
    rows = (await db.execute(q)).scalars().all()

    n = len(rows)
    if n == 0:
        return {
            "transition_type": transition_type, "regime": regime, "window_days": days,
            "sample_size": 0, "success_rate": None, "failure_rate": None, "neutral_rate": None,
            "avg_pct_5d": None, "avg_max_gain_atr_10d": None, "avg_max_drawdown_atr_10d": None,
            "median_pct_5d": None, "minimum_sample_warning": "No data",
        }

    succ = sum(1 for r in rows if r.outcome_status == 'SUCCESS')
    fail = sum(1 for r in rows if r.outcome_status == 'FAILURE')
    neut = sum(1 for r in rows if r.outcome_status == 'NEUTRAL')
    pct5 = [r.pct_5d for r in rows if r.pct_5d is not None]
    gain_atr = [r.max_gain_atr_within_10d for r in rows if r.max_gain_atr_within_10d is not None]
    dd_atr = [r.max_drawdown_atr_within_10d for r in rows if r.max_drawdown_atr_within_10d is not None]

    warning = "Sample size below 30 — stats unreliable" if n < 30 else None

    return {
        "transition_type": transition_type,
        "regime": regime,
        "window_days": days,
        "sample_size": n,
        "success_rate": round(succ / n, 3),
        "failure_rate": round(fail / n, 3),
        "neutral_rate": round(neut / n, 3),
        "avg_pct_5d": round(mean(pct5), 2) if pct5 else None,
        "avg_max_gain_atr_10d": round(mean(gain_atr), 2) if gain_atr else None,
        "avg_max_drawdown_atr_10d": round(mean(dd_atr), 2) if dd_atr else None,
        "median_pct_5d": round(median(pct5), 2) if pct5 else None,
        "minimum_sample_warning": warning,
    }


@router.get("/observations/{symbol}")
async def observations_for_symbol(
    symbol: str,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(TransitionObservation)
        .where(TransitionObservation.symbol == symbol.upper())
        .order_by(TransitionObservation.detected_at.desc())
        .limit(50)
    )
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "transition_type": r.transition_type,
            "date_detected": r.date_detected.isoformat() if r.date_detected else None,
            "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            "regime_at_detection": r.regime_at_detection,
            "price_at_detection": r.price_at_detection,
            "atr_at_detection": r.atr_at_detection,
            "ema9_at_detection": r.ema9_at_detection,
            "ema21_at_detection": r.ema21_at_detection,
            "ema50_at_detection": r.ema50_at_detection,
            "rs_spy_at_detection": r.rs_spy_at_detection,
            "vcp_score_at_detection": r.vcp_score_at_detection,
            "outcome_status": r.outcome_status,
            "outcome_evaluated_at": r.outcome_evaluated_at.isoformat() if r.outcome_evaluated_at else None,
            "pct_1d": r.pct_1d,
            "pct_5d": r.pct_5d,
            "pct_20d": r.pct_20d,
            "max_gain_atr_10d": r.max_gain_atr_within_10d,
            "max_drawdown_atr_10d": r.max_drawdown_atr_within_10d,
            "reached_ema21_within_10d": r.reached_ema21_within_10d,
            "broke_ema50_within_10d": r.broke_ema50_within_10d,
        }
        for r in rows
    ]
