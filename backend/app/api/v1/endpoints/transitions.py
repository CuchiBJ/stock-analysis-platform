"""Operational Transitions API - Live transition feed and actionable setups"""

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from typing import List, Dict, Optional
from datetime import datetime, timedelta, date
from statistics import mean, median
from app.core.deps import get_db
from app.services.transition_engine import (
    TransitionEngine,
    OperationalTransition,
    FreshnessState
)
from app.services.observation_scorer import score_observation_priority, is_pre_reclaim_candidate
from app.services.setup_lifecycle_engine import SetupLifecycleEngine, SetupState
from app.services.market_regime_engine import MarketRegimeEngine
from app.services.regime_aware_engine import RegimeAwareEngine
from app.services.context_decision_filter import fetch_current_context, compute_context_multiplier
from app.services.group_strength_service import fetch_current_group_strengths, compute_group_multiplier
from app.services.websocket_manager import websocket_manager
from app.models.stock import Stock, StockMetrics, TransitionObservation
from sqlalchemy import select, and_, or_, func, text
from datetime import timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Institutional setup quality — REQUIRED for every candidate ──────────────
# The stock must ALREADY be a great institutional setup. Only then do we
# observe its EMA9/EMA21 behavior. Structure is mandatory; the EMA trigger
# is what surfaces it in the feed.
#
# Criteria (Stage 2 / institutional uptrend):
# - Strong long-term performance:        perf_1y > 30%
# - Price above primary trend EMAs:      price > EMA50, price > SMA150
# - Long-term trend confirmed:           SMA150 > SMA200
# - Near 52-week high, far from low:     distance_to_high_52w_atr >= -3 ATR
#                                        price >= 52w_low * 1.5
# - Liquid and tradable:                 avg_volume_10d >= 800k, ADR >= 4%
_LARGE_CAP_SYMBOLS = (
    select(Stock.symbol).where(Stock.market_cap >= 600_000_000)
)

_INSTITUTIONAL_SETUP = and_(
    # Universe membership: market cap ≥ $600M (excludes small/micro-caps + NULLs)
    StockMetrics.symbol.in_(_LARGE_CAP_SYMBOLS),

    # Liquidity and volatility
    StockMetrics.avg_volume_10d >= 800_000,
    StockMetrics.adr_percent >= 4.0,
    StockMetrics.current_price >= 5.0,

    # Long-term uptrend confirmation
    StockMetrics.perf_1y > 30,
    StockMetrics.current_price > StockMetrics.ema50,
    StockMetrics.current_price > StockMetrics.sma150,
    StockMetrics.sma150 > StockMetrics.sma200,

    # Structural position
    StockMetrics.distance_to_high_52w_atr >= -3.0,
    StockMetrics.current_price >= StockMetrics.low_52w * 1.5,
)

# ─── EMA trigger — near or just lost EMA9/EMA21 ──────────────────────────────
# This is the SURFACING condition. The stock already has the setup; what makes
# it actionable today is being at the EMA9/EMA21 inflection point.
#
# Zone definition (ATR-normalized):
#   from -1.0 ATR (just lost EMA, observable pullback)
#   to   +0.5 ATR (about to lose EMA, very close from above)
_EMA9_TRIGGER = and_(
    StockMetrics.distance_to_ema9_atr >= -1.0,
    StockMetrics.distance_to_ema9_atr <= 0.5,
)
_EMA21_TRIGGER = and_(
    StockMetrics.distance_to_ema21_atr >= -1.0,
    StockMetrics.distance_to_ema21_atr <= 0.5,
)

def _passes_ema_trigger(metrics: StockMetrics) -> bool:
    """EMA proximity check — evaluated in Python on today's metrics."""
    ema9  = metrics.distance_to_ema9_atr  if metrics.distance_to_ema9_atr  is not None else 999.0
    ema21 = metrics.distance_to_ema21_atr if metrics.distance_to_ema21_atr is not None else 999.0
    return (-1.0 <= ema9 <= 0.5) or (-1.0 <= ema21 <= 0.5)


# Combined: institutional quality REQUIRED + at least one EMA trigger zone
_ACTIONABLE_FILTER = and_(
    _INSTITUTIONAL_SETUP,
    or_(_EMA9_TRIGGER, _EMA21_TRIGGER),
)

# backward-compat alias
_EMA_PULLBACK_FILTER = _ACTIONABLE_FILTER


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
        transition_engine = TransitionEngine(db)

        # Step 1: anchor to the latest date with data in the DB
        latest_date_result = await db.execute(
            select(func.max(StockMetrics.date))
        )
        latest_date = latest_date_result.scalar()
        if not latest_date:
            return []

        # Step 2: 7-day lookback covers weekends and long holiday closures (Memorial Day,
        # Thanksgiving, Christmas) for "previous" metrics — 3 days fails when Mon is also closed
        prev_date = latest_date - timedelta(days=7)

        # Step 3: query only current + previous day, institutional quality only
        # EMA trigger is evaluated in Python (step 4) so we have today's current
        result = await db.execute(
            select(StockMetrics)
            .where(
                and_(
                    StockMetrics.date >= prev_date,
                    StockMetrics.date <= latest_date,
                    _INSTITUTIONAL_SETUP,
                )
            )
            .order_by(StockMetrics.date.desc())
            .limit(1000)
        )
        recent_metrics = result.scalars().all()

        # Group by symbol
        symbol_metrics: Dict[str, List[StockMetrics]] = {}
        for metrics in recent_metrics:
            if metrics.symbol not in symbol_metrics:
                symbol_metrics[metrics.symbol] = []
            symbol_metrics[metrics.symbol].append(metrics)

        transitions = []
        for symbol, metrics_list in symbol_metrics.items():
            current = metrics_list[0]

            # Step 4: freshness gate — current MUST be from latest_date
            if current.date != latest_date:
                continue

            # Step 5: EMA trigger evaluated in Python on today's metrics
            if not _passes_ema_trigger(current):
                continue

            if len(metrics_list) >= 2:
                op_transition = await transition_engine.calculate_operational_transition(
                    symbol, current, metrics_list[1]
                )
            else:
                op_transition = type('obj', (object,), {
                    'transition': OperationalTransition.STABLE,
                    'strength': 0.5,
                    'rs_change': 0.0,
                    'volume_change_pct': 0.0,
                    'narrative': 'No previous data for comparison.',
                    'timestamp': datetime.utcnow()
                })()

            severity = _determine_severity(op_transition.transition)
            obs_priority = score_observation_priority(current)
            pre_reclaim = is_pre_reclaim_candidate(current)

            previous = metrics_list[1] if len(metrics_list) >= 2 else None
            dist_pct, ema_label = _dist_to_setup_pct(current, op_transition.transition.value)
            transitions.append({
                "symbol": symbol,
                "transition": op_transition.transition.value,
                "direction": _get_transition_direction(op_transition.transition),
                "strength": op_transition.strength,
                "observation_priority": round(obs_priority, 1),
                "is_pre_reclaim": pre_reclaim,
                "timestamp": op_transition.timestamp.isoformat(),
                "narrative": op_transition.narrative,
                "severity": severity,
                "rs_change": op_transition.rs_change if hasattr(op_transition, 'rs_change') else 0.0,
                "volume_change_pct": op_transition.volume_change_pct if hasattr(op_transition, 'volume_change_pct') else 0.0,
                "current_price": round(current.current_price, 2) if current.current_price else None,
                "change_pct": _day_change_pct(current, previous),
                "dist_to_setup_pct": dist_pct,
                "dist_ema_label": ema_label,
            })

        # Drop stable — no actionable signal
        transitions = [t for t in transitions if t["transition"] != OperationalTransition.STABLE.value]

        # entering_pullback surfaces first, then pre-reclaim candidates by observation priority
        transitions.sort(
            key=lambda x: (
                x["transition"] == OperationalTransition.ENTERING_PULLBACK.value,
                x["is_pre_reclaim"],
                x["observation_priority"],
                x["strength"],
            ),
            reverse=True,
        )
        result_transitions = transitions[:limit]

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
    limit: int = Query(6, ge=1, le=12),
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

        # Fetch market context once — used for score multiplier and warnings
        participation, leadership = await fetch_current_context(db)
        ctx_multiplier = compute_context_multiplier(participation, leadership)
        context_snapshot = {"participation": participation, "leadership": leadership}

        # Fetch group strength snapshot once — used for per-setup group multiplier
        group_perfs = await fetch_current_group_strengths(db)

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
                    StockMetrics.pullback_quality_score >= 55,
                    StockMetrics.distance_to_high_52w_atr >= -3.0,
                    StockMetrics.avg_volume_10d >= 700000,
                    StockMetrics.adr_percent >= 3,
                    _EMA_PULLBACK_FILTER,
                )
            )
            .order_by(StockMetrics.pullback_quality_score.desc())
            .limit(50)
        )
        setups = result.scalars().all()

        # Fetch real days_in_state from state log for all setup symbols at once
        setup_symbols = [s.symbol for s in setups]
        days_in_state_map = await _get_days_in_state(db, setup_symbols)

        # Fetch market_group for all setup symbols in one query
        mg_result = await db.execute(
            select(Stock.symbol, Stock.market_group)
            .where(Stock.symbol.in_(setup_symbols))
        )
        market_group_map: dict = {
            row.symbol: row.market_group for row in mg_result.fetchall()
        }

        lifecycle = SetupLifecycleEngine(db)

        # Regime multiplier applied to continuation probability
        _REGIME_CONT_MULT = {
            'risk_on': 1.00, 'choppy': 0.85, 'transition': 0.80, 'risk_off': 0.65,
        }
        regime_cont_mult = _REGIME_CONT_MULT.get(regime.regime.value, 0.85)

        actionable = []
        for setup in setups:
            days_in_state = days_in_state_map.get(setup.symbol, 1)
            priority_score, score_breakdown = await _calculate_priority_score_with_breakdown(
                setup, regime, transition_engine, db, days_in_state
            )
            setup_type = _classify_setup_type(setup)
            narrative = _generate_priority_narrative(setup, priority_score, setup_type)
            prob, prob_source, sample_size = await lifecycle.calculate_continuation_probability(setup)
            cont_prob = min(1.0, prob * regime_cont_mult)

            # Apply context + group multipliers compositionally
            market_group = market_group_map.get(setup.symbol)
            group_mult = compute_group_multiplier(market_group, group_perfs)
            final_priority_unclamped = priority_score * ctx_multiplier.score_multiplier * group_mult.score_multiplier
            final_priority = min(1.0, final_priority_unclamped)

            # Augment the breakdown with the multiplier layer + final
            score_breakdown_full = dict(score_breakdown)
            score_breakdown_full['ctx_multiplier'] = {
                'value': ctx_multiplier.score_multiplier,
                'max_value': 1.10,
                'kind': 'market_wide',
            }
            score_breakdown_full['group_multiplier'] = {
                'value': group_mult.score_multiplier,
                'max_value': 1.15,
                'kind': 'group_rotation',
                'badge': group_mult.badge,
                'group': market_group,
            }
            score_breakdown_full['final_priority_unclamped'] = round(final_priority_unclamped, 4)
            score_breakdown_full['final_priority'] = round(final_priority, 4)
            score_breakdown_full['clamped'] = final_priority_unclamped > 1.0

            dist_pct, ema_label = _dist_to_setup_pct(setup, setup_type.replace('_pullback', '') if setup_type else '')
            actionable.append({
                "symbol":               setup.symbol,
                "priority_score":       final_priority,
                "score_breakdown":      score_breakdown_full,
                "continuation_prob":    round(cont_prob, 2),
                "probability_source":   prob_source,
                "sample_size":          sample_size,
                "narrative":            narrative,
                "setup_type":           setup_type,
                "pullback_quality":     setup.pullback_quality_score,
                "distance_to_ema21":    setup.distance_to_ema21,
                "distance_to_ema9":     setup.distance_to_ema9,
                "rs_spy":               setup.relative_strength_spy,
                "volume_contraction":   setup.volume_contraction,
                "days_in_state":        days_in_state,
                "current_price":        round(setup.current_price, 2) if setup.current_price else None,
                "change_pct":           round(setup.perf_1w / 5, 1) if setup.perf_1w else None,
                "dist_to_setup_pct":    dist_pct,
                "dist_ema_label":       ema_label,
                "context_warnings":     list(ctx_multiplier.surface_warnings),
                "group_strength": {
                    "group":      market_group,
                    "badge":      group_mult.badge,
                    "multiplier": group_mult.score_multiplier,
                },
            })

        actionable.sort(key=lambda x: x["priority_score"], reverse=True)
        return {
            "context_snapshot": context_snapshot,
            "setups": actionable[:limit],
        }
        
    except Exception as e:
        logger.error(f"Error getting actionable setups: {e}")
        raise


# --- Helper functions ---

def _dist_to_setup_pct(metrics, transition: str):
    price = metrics.current_price
    atr = metrics.atr
    if not price or not atr:
        return None, "EMA21"
    d9 = metrics.distance_to_ema9_atr
    d21 = metrics.distance_to_ema21_atr
    if transition == 'entering_pullback' and d9 is not None and abs(d9) <= 0.5:
        ema_price = price - (d9 * atr)
        return round((ema_price - price) / price * 100, 1), "EMA9"
    elif d21 is not None:
        ema_price = price - (d21 * atr)
        return round((ema_price - price) / price * 100, 1), "EMA21"
    return None, "EMA21"


def _day_change_pct(current, previous):
    """Real day change: today's price vs yesterday's price."""
    if not current or not current.current_price:
        return None
    if not previous or not previous.current_price or previous.current_price == 0:
        return None
    return round((current.current_price - previous.current_price) / previous.current_price * 100, 1)


def _determine_severity(transition: OperationalTransition) -> str:
    if transition == OperationalTransition.FAILING:
        return "critical"
    elif transition in [OperationalTransition.WEAKENING, OperationalTransition.DISTRIBUTION]:
        return "negative"
    elif transition in [
        OperationalTransition.VOLUME_DRY_UP,
        OperationalTransition.COMPRESSING,
        OperationalTransition.FLUSH_AND_RECOVER,
        OperationalTransition.SUPPORT_HOLDING,
        OperationalTransition.ENTERING_PULLBACK,
        OperationalTransition.RECLAIMING,
        OperationalTransition.CONTINUATION_HOLDING,
    ]:
        return "positive"
    else:
        return "neutral"


def _severity_score(severity: str) -> int:
    return {"critical": 3, "negative": 2, "neutral": 1, "positive": 0}.get(severity, 0)


def _get_transition_direction(transition: OperationalTransition) -> str:
    """Direction for frontend display. Pre-reclaim = 'preparing' (new)."""
    if transition in [
        OperationalTransition.VOLUME_DRY_UP,
        OperationalTransition.COMPRESSING,
        OperationalTransition.FLUSH_AND_RECOVER,
        OperationalTransition.SUPPORT_HOLDING,
        OperationalTransition.ENTERING_PULLBACK,
    ]:
        return "preparing"
    elif transition in [
        OperationalTransition.RECLAIMING,
        OperationalTransition.CONTINUATION_HOLDING,
    ]:
        return "reclaiming"
    elif transition in [
        OperationalTransition.WEAKENING,
        OperationalTransition.DISTRIBUTION,
        OperationalTransition.FAILING,
    ]:
        return "deteriorating"
    else:
        return "stable"


_REGIME_ALIGNMENT_WEIGHTS = {
    'risk_on': 0.20, 'choppy': 0.14, 'transition': 0.12, 'risk_off': 0.08,
}

# Freshness decay: score drops as days_in_state increases
# 1-3 days = peak, 4-7 days = good, 8-14 = moderate, 15+ = stale
def _freshness_score(days: int) -> float:
    if days <= 3:   return 1.0
    if days <= 7:   return 0.75
    if days <= 14:  return 0.45
    if days <= 20:  return 0.20
    return 0.10


async def _get_days_in_state(db: AsyncSession, symbols: list[str]) -> dict[str, int]:
    """Return {symbol: days_in_current_state} from setup_state_log.
    Falls back to 1 for symbols with no log entry.
    """
    if not symbols:
        return {}
    try:
        result = await db.execute(text("""
            SELECT DISTINCT ON (symbol) symbol, entered_at
            FROM setup_state_log
            WHERE symbol = ANY(:symbols) AND exited_at IS NULL
            ORDER BY symbol, entered_at DESC
        """), {"symbols": symbols})
        now = datetime.now(timezone.utc)
        return {
            row[0]: max(1, (now - row[1].replace(tzinfo=timezone.utc)).days)
            for row in result.fetchall()
        }
    except Exception:
        return {}


async def _calculate_priority_score(
    setup: StockMetrics,
    regime,
    transition_engine: TransitionEngine,
    db: AsyncSession,
    days_in_state: int = 1,
) -> float:
    """Calculate priority score for actionable setup.

    Thin wrapper around _calculate_priority_score_with_breakdown for callers
    that don't need the component-level detail.
    """
    score, _ = await _calculate_priority_score_with_breakdown(
        setup, regime, transition_engine, db, days_in_state
    )
    return score


def _pullback_quality_subcomponents(m: StockMetrics) -> list[dict]:
    """Break down pullback_quality_score (0-100) into its 6 sub-components,
    so the operator can see EXACTLY where the score is leaking.

    Mirrors _calculate_pullback_quality_score in metrics_calculator.py.
    """
    subs: list[dict] = []

    # EMA9 proximity (max 25)
    d9 = m.distance_to_ema9_atr
    if d9 is None:
        pts9 = 0; verdict9 = 'EMA9 distance no calculada'
    elif abs(d9) <= 0.5:
        pts9 = 25; verdict9 = 'En sweet spot (≤0.5 ATR)'
    elif abs(d9) <= 1.0:
        pts9 = 20; verdict9 = f'Cerca pero no en sweet spot (actual {d9:+.2f} ATR, ideal ≤0.5)'
    elif abs(d9) <= 1.5:
        pts9 = 15; verdict9 = f'Pullback moderado (actual {d9:+.2f} ATR, ideal ≤0.5)'
    elif abs(d9) <= 2.0:
        pts9 = 10; verdict9 = f'Pullback profundo (actual {d9:+.2f} ATR)'
    else:
        pts9 = 0;  verdict9 = f'Demasiado lejos del EMA9 ({d9:+.2f} ATR)'
    subs.append({'name': 'EMA9 proximity', 'points': pts9, 'max_points': 25,
                 'raw_value': d9, 'verdict': verdict9})

    # EMA21 proximity (max 20)
    d21 = m.distance_to_ema21_atr
    if d21 is None:
        pts21 = 0; verdict21 = 'EMA21 distance no calculada'
    elif abs(d21) <= 0.5:
        pts21 = 20; verdict21 = 'En sweet spot (≤0.5 ATR)'
    elif abs(d21) <= 1.0:
        pts21 = 15; verdict21 = f'Cerca pero no en sweet spot (actual {d21:+.2f} ATR)'
    elif abs(d21) <= 1.5:
        pts21 = 10; verdict21 = f'Pullback moderado al EMA21 ({d21:+.2f} ATR)'
    elif abs(d21) <= 2.0:
        pts21 = 5;  verdict21 = f'Pullback profundo del EMA21 ({d21:+.2f} ATR)'
    else:
        pts21 = 0;  verdict21 = f'Demasiado lejos del EMA21 ({d21:+.2f} ATR)'
    subs.append({'name': 'EMA21 proximity', 'points': pts21, 'max_points': 20,
                 'raw_value': d21, 'verdict': verdict21})

    # 52W high proximity (max 20)
    dh = m.distance_to_high_52w_atr
    if dh is None:
        ptsh = 0; verdicth = '52W distance no calculada'
    elif dh >= -1.0:
        ptsh = 20; verdicth = f'A {dh:+.2f} ATR del máximo anual (excelente)'
    elif dh >= -2.0:
        ptsh = 15; verdicth = f'A {dh:+.2f} ATR del máximo (cerca de fuerza)'
    elif dh >= -3.0:
        ptsh = 10; verdicth = f'A {dh:+.2f} ATR del máximo (margen aceptable)'
    elif dh >= -4.0:
        ptsh = 5;  verdicth = f'A {dh:+.2f} ATR del máximo (lejos)'
    else:
        ptsh = 0;  verdicth = f'Demasiado lejos del máximo anual ({dh:+.2f} ATR)'
    subs.append({'name': 'Cercanía a máximo 52w', 'points': ptsh, 'max_points': 20,
                 'raw_value': dh, 'verdict': verdicth})

    # Weekly tightness (max 10) — buckets calibrated to real distribution
    # of the institutional universe (p95 ≈ 0.37, max ≈ 0.42)
    wt = m.weekly_tightness
    if wt is None:
        pts_wt = 0; verdict_wt = 'Sin datos suficientes'
    elif wt >= 0.40:
        pts_wt = 10; verdict_wt = f'Base muy apretada (top 5% del universo, wt={wt:.2f})'
    elif wt >= 0.35:
        pts_wt = 7;  verdict_wt = f'Base apretada (top 20%, wt={wt:.2f})'
    elif wt >= 0.30:
        pts_wt = 4;  verdict_wt = f'Base moderada (zona median, wt={wt:.2f})'
    elif wt >= 0.25:
        pts_wt = 2;  verdict_wt = f'Base floja (bottom 25%, wt={wt:.2f})'
    else:
        pts_wt = 0;  verdict_wt = f'Sin contracción semanal (wt={wt:.2f})'
    subs.append({'name': 'Tightness semanal', 'points': pts_wt, 'max_points': 10,
                 'raw_value': wt, 'verdict': verdict_wt})

    # Volume contraction (max 10) — bucketed
    vc = m.volume_contraction
    if vc is None:
        pts_vc = 0; verdict_vc = 'Sin datos suficientes'
    elif vc >= 0.60:
        pts_vc = 10; verdict_vc = f'Volumen contrayendo fuerte (vc={vc:.2f}, top 5%)'
    elif vc >= 0.40:
        pts_vc = 8;  verdict_vc = f'Volumen contrayendo bien (vc={vc:.2f}, top 25%)'
    elif vc >= 0.20:
        pts_vc = 5;  verdict_vc = f'Volumen contrayendo moderado (vc={vc:.2f}, zona median)'
    elif vc >= 0.05:
        pts_vc = 2;  verdict_vc = f'Volumen apenas contrayendo (vc={vc:.2f})'
    else:
        pts_vc = 0;  verdict_vc = f'Volumen NO contrayendo (vc={vc:.2f}) — falta dry-up'
    subs.append({'name': 'Volume contraction', 'points': pts_vc, 'max_points': 10,
                 'raw_value': vc, 'verdict': verdict_vc})

    # Weekly trend quality (max 25) — bucketed, heaviest sub-component
    wtq = m.weekly_trend_quality
    if wtq is None:
        pts_wtq = 0; verdict_wtq = 'Sin datos suficientes'
    elif wtq >= 0.70:
        pts_wtq = 25; verdict_wtq = f'Tendencia semanal excelente (wtq={wtq:.2f}, top 5%)'
    elif wtq >= 0.60:
        pts_wtq = 19; verdict_wtq = f'Tendencia semanal sólida (wtq={wtq:.2f}, top 20%)'
    elif wtq >= 0.50:
        pts_wtq = 13; verdict_wtq = f'Tendencia semanal moderada (wtq={wtq:.2f}, zona median)'
    elif wtq >= 0.40:
        pts_wtq = 7;  verdict_wtq = f'Tendencia semanal débil (wtq={wtq:.2f})'
    else:
        pts_wtq = 2;  verdict_wtq = f'Tendencia semanal deteriorada (wtq={wtq:.2f}) — issue estructural'
    subs.append({'name': 'Weekly trend quality', 'points': pts_wtq, 'max_points': 25,
                 'raw_value': wtq, 'verdict': verdict_wtq})

    return subs


async def _calculate_priority_score_with_breakdown(
    setup: StockMetrics,
    regime,
    transition_engine: TransitionEngine,
    db: AsyncSession,
    days_in_state: int = 1,
) -> tuple[float, dict]:
    """Calculate priority score AND return a per-component breakdown.

    The breakdown dict has shape:
      {
        'components': [{ name, value, max_possible, contribution, max_contribution,
                         to_improve, kind, note }],
        'base_score': float,        # sum of contributions BEFORE regime-state confidence adjust
        'after_regime_adjust': float,  # final base post-RegimeAwareEngine
      }
    """
    components: list[dict] = []

    # ── 1. Pullback quality (40%) ────────────────────────────────────────
    pq = (setup.pullback_quality_score or 0.0) / 100.0
    pq_contrib = 0.4 * pq
    components.append({
        'name': 'pullback_quality',
        'value': pq * 100,
        'max_value': 100.0,
        'contribution': pq_contrib,
        'max_contribution': 0.40,
        'to_improve': round(0.40 - pq_contrib, 4),
        'kind': 'symbol_controllable',
        'note': 'Improve via closer EMA9/21 proximity, tighter weekly range, more volume contraction, better weekly trend quality.',
        'sub_components': _pullback_quality_subcomponents(setup),
    })

    # ── 2. Freshness (25%) ──────────────────────────────────────────────
    fr = _freshness_score(days_in_state)
    fr_contrib = 0.25 * fr
    components.append({
        'name': 'freshness',
        'value': fr * 100,
        'max_value': 100.0,
        'contribution': fr_contrib,
        'max_contribution': 0.25,
        'to_improve': round(0.25 - fr_contrib, 4),
        'kind': 'time_dependent',
        'note': f'Days in state: {days_in_state}. Peak is 1-3d. Once aging, only a fresh state transition resets freshness.',
    })

    # ── 3. Regime alignment (max 0.20) ───────────────────────────────────
    regime_val = _REGIME_ALIGNMENT_WEIGHTS.get(regime.regime.value, 0.14)
    components.append({
        'name': 'regime_alignment',
        'value': regime_val,
        'max_value': 0.20,
        'contribution': regime_val,
        'max_contribution': 0.20,
        'to_improve': round(0.20 - regime_val, 4),
        'kind': 'market_wide',
        'note': f'Current regime: {regime.regime.value}. Market-wide, uncontrollable per-symbol.',
    })

    # ── 4. Leader quality (15%, same input as pq) ────────────────────────
    lq_contrib = 0.15 * pq
    components.append({
        'name': 'leader_quality',
        'value': pq * 100,
        'max_value': 100.0,
        'contribution': lq_contrib,
        'max_contribution': 0.15,
        'to_improve': round(0.15 - lq_contrib, 4),
        'kind': 'symbol_controllable',
        'note': 'Same input as pullback_quality (raises both contributions together).',
    })

    base_score = pq_contrib + fr_contrib + regime_val + lq_contrib

    # ── 5. Regime × setup-state confidence adjust (RegimeAwareEngine) ────
    setup_type = _classify_setup_type(setup)
    setup_state = (
        SetupState.TIGHTENING if setup_type == 'ema9_pullback'
        else SetupState.CONTROLLED_PULLBACK
    )
    final = base_score
    try:
        adj = RegimeAwareEngine(db).calculate_regime_adjustment(setup_state, base_score, regime)
        final = adj.adjusted_confidence
    except Exception:
        pass

    breakdown = {
        'components': components,
        'base_score': round(base_score, 4),
        'after_regime_adjust': round(final, 4),
    }
    return final, breakdown


def _classify_setup_type(setup: StockMetrics) -> str:
    """Determine whether setup is an EMA9 or EMA21 pullback using ATR-normalized distances."""
    ema9_atr  = setup.distance_to_ema9_atr
    ema21_atr = setup.distance_to_ema21_atr

    is_ema9 = (
        ema9_atr  is not None and -0.5 <= ema9_atr  <= 0.3 and
        ema21_atr is not None and ema21_atr > 0.3
    )
    if is_ema9:
        return "ema9_pullback"
    return "ema21_pullback"


def _generate_priority_narrative(setup: StockMetrics, priority_score: float, setup_type: str = "ema21_pullback") -> str:
    """Generate short narrative for actionable setup."""
    components = []

    if setup_type == "ema9_pullback":
        atr = setup.distance_to_ema9_atr or 0
        components.append("EMA9 held" if atr >= 0 else f"EMA9 pullback ({atr:.2f} ATR)")
    else:
        atr = setup.distance_to_ema21_atr or 0
        components.append("EMA21 held" if atr >= 0 else f"Near EMA21 ({atr:.2f} ATR)")

    if setup.volume_contraction and setup.volume_contraction > 20:
        components.append(f"Vol -{setup.volume_contraction:.0f}%")

    if setup.relative_strength_spy and setup.relative_strength_spy > 105:
        components.append("RS strong")

    if priority_score > 0.8:
        components.append("High priority")

    return ". ".join(components) + "."


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
