"""Calibration reporting — observed empirical success rate per transition type.

Reads `transition_observations` and computes, per `OperationalTransition`
value (excluding STABLE), the observed success rate over the resolved
sample (SUCCESS + FAILURE), exposing pending counts and an ETA for first
resolution when nothing has resolved yet.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.stock import StockMetrics, TransitionObservation
from app.services.batch_transition_scanner import BatchTransitionScanner
from app.services.calibration_statistics import (
    MIN_SETTLED_SAMPLES,
    classify_drift,
    cohort_statistics,
    rate_delta_pp,
)
from app.services.follow_through import BULLISH_TRANSITIONS, FT_BASELINE_CAL_DAYS
from app.services.transition_engine import OperationalTransition

router = APIRouter(prefix="/calibration", tags=["calibration"])

MIN_SAMPLES_REQUIRED = MIN_SETTLED_SAMPLES
RECENT_WINDOW_DAYS = 21
PENDING_STATUSES = ("PENDING", "INSUFFICIENT_DATA")
RESOLVED_STATUSES = ("SUCCESS", "FAILURE")
_STATUS_ORDER = {"empirical": 0, "insufficient": 1, "no_data": 2}


def _classify(n_resolved: int) -> str:
    if n_resolved >= MIN_SAMPLES_REQUIRED:
        return "empirical"
    if n_resolved > 0:
        return "insufficient"
    return "no_data"


def _rates(
    success: int, failure: int, neutral: int, status: str
) -> tuple[Optional[float], Optional[float]]:
    """Return (success_rate, delivery_rate), or (None, None) when not empirical.

    - success_rate: win/loss ratio among DECISIVE outcomes — success / (S+F).
      Excludes NEUTRAL.
    - delivery_rate: share of ALL settled signals that delivered the move —
      success / (S+F+N). A NEUTRAL settled without delivering, so it belongs in
      the denominator; this is the honest "hit rate over every signal" and is
      always <= success_rate. Diverges most when neutrals are many.
    """
    if status != "empirical":
        return None, None
    n_resolved = success + failure
    n_settled = n_resolved + neutral
    success_rate = success / n_resolved if n_resolved > 0 else None
    delivery_rate = success / n_settled if n_settled > 0 else None
    return success_rate, delivery_rate


@router.get("/by-transition-type")
async def calibration_by_transition_type(db: AsyncSession = Depends(get_db)):
    transition_values = [
        t.value for t in OperationalTransition if t.value != "stable"
    ]

    as_of = (await db.execute(select(func.max(StockMetrics.date)))).scalar() or date.today()

    from app.services.market_context_engine import MarketContextEngine
    market_context = await MarketContextEngine(db).analyze()
    if market_context is None or market_context.regime is None:
        raise HTTPException(status_code=404, detail="Current market context is unavailable")
    regime_analysis = market_context.regime
    current_regime = regime_analysis.regime.value
    recent_start = as_of - timedelta(days=RECENT_WINDOW_DAYS)
    baseline_start = recent_start - timedelta(days=FT_BASELINE_CAL_DAYS)

    counts_q = (
        select(
            TransitionObservation.transition_type,
            TransitionObservation.outcome_status,
            func.count(TransitionObservation.id).label("historical_count"),
            func.count(TransitionObservation.id).filter(
                and_(
                    TransitionObservation.date_detected > recent_start,
                    TransitionObservation.date_detected <= as_of,
                )
            ).label("recent_count"),
            func.count(TransitionObservation.id).filter(
                and_(
                    TransitionObservation.date_detected > baseline_start,
                    TransitionObservation.date_detected <= recent_start,
                )
            ).label("baseline_count"),
            func.count(TransitionObservation.id).filter(
                TransitionObservation.regime_at_detection == current_regime
            ).label("regime_count"),
        )
        .where(TransitionObservation.transition_type.in_(transition_values))
        .group_by(
            TransitionObservation.transition_type,
            TransitionObservation.outcome_status,
        )
    )
    raw_rows = (await db.execute(counts_q)).all()

    counts: dict[str, dict[str, dict[str, int]]] = {
        t: {"historical": {}, "recent": {}, "baseline": {}, "current_regime": {}}
        for t in transition_values
    }
    for r in raw_rows:
        counts[r.transition_type]["historical"][r.outcome_status] = r.historical_count
        counts[r.transition_type]["recent"][r.outcome_status] = r.recent_count
        counts[r.transition_type]["baseline"][r.outcome_status] = r.baseline_count
        counts[r.transition_type]["current_regime"][r.outcome_status] = r.regime_count

    rows = []
    total_observations = 0
    total_resolved = 0
    total_pending = 0
    total_settled = 0

    def _cohort(raw: dict[str, int]) -> dict:
        return cohort_statistics(
            success=raw.get("SUCCESS", 0),
            failure=raw.get("FAILURE", 0),
            neutral=raw.get("NEUTRAL", 0),
            pending=raw.get("PENDING", 0) + raw.get("INSUFFICIENT_DATA", 0),
        )

    for t in transition_values:
        historical = _cohort(counts[t]["historical"])
        recent = _cohort(counts[t]["recent"])
        baseline = _cohort(counts[t]["baseline"])
        regime_cohort = _cohort(counts[t]["current_regime"])
        drift = classify_drift(baseline, recent)
        bullish = t in BULLISH_TRANSITIONS

        rows.append(
            {
                "transition_type": t,
                "bullish": bullish,
                "historical": historical,
                "recent": recent,
                "baseline": baseline,
                "current_regime": regime_cohort,
                "drift": drift,
                "recent_delta_pp": rate_delta_pp(recent, baseline),
                "regime_delta_pp": rate_delta_pp(regime_cohort, historical),
                # Legacy historical fields retained for existing consumers.
                "n_resolved": historical["n_resolved"],
                "n_pending": historical["n_pending"],
                "success_count": historical["success_count"],
                "failure_count": historical["failure_count"],
                "neutral_count": historical["neutral_count"],
                "success_rate": historical["success_rate"],
                "delivery_rate": historical["delivery_rate"],
                "status": historical["status"],
            }
        )

        total_observations += historical["n_observed"]
        total_resolved += historical["n_resolved"]
        total_pending += historical["n_pending"]
        total_settled += historical["n_settled"]

    drift_order = {"deteriorating": 0, "stable": 1, "improving": 2, "insufficient": 3}
    rows.sort(
        key=lambda r: (
            0 if r["bullish"] else 1,
            drift_order[r["drift"]],
            -r["recent"]["n_settled"],
            r["transition_type"],
        )
    )

    eta_first_data = None
    if total_settled == 0 and total_pending > 0:
        oldest_pending = (
            await db.execute(
                select(func.min(TransitionObservation.date_detected)).where(
                    TransitionObservation.outcome_status.in_(PENDING_STATUSES)
                )
            )
        ).scalar()
        if oldest_pending is not None:
            # Resolver needs 10 trading-day price rows after detection, not 10
            # calendar days — skip weekends so the ETA reflects market sessions.
            candidate = oldest_pending
            biz_days = 0
            while biz_days < 10:
                candidate += timedelta(days=1)
                if candidate.weekday() < 5:
                    biz_days += 1
            eta_first_data = candidate.isoformat()

    follow_through = None
    posture = None
    if market_context is not None:
        if market_context.follow_through is not None:
            ft = market_context.follow_through
            follow_through = {
                "descriptor": ft.descriptor,
                "basis": ft.basis,
                "window_days": ft.window_days,
                "delivery_rate": ft.delivery_rate,
                "baseline_rate": ft.baseline_rate,
                "resolved": ft.resolved,
                "pending": ft.pending,
            }
        if market_context.posture is not None:
            posture = {
                "state": market_context.posture.state,
                "instruction": market_context.posture.instruction,
            }

    return {
        "min_samples_required": MIN_SAMPLES_REQUIRED,
        "recent_window_days": RECENT_WINDOW_DAYS,
        "as_of": as_of.isoformat(),
        "current_context": {
            "regime": current_regime,
            "regime_confidence": round(regime_analysis.confidence, 4),
            "follow_through": follow_through,
            "posture": posture,
        },
        "total_observations": total_observations,
        "total_resolved": total_resolved,
        "total_settled": total_settled,
        "total_pending": total_pending,
        "eta_first_data": eta_first_data,
        "rows": rows,
    }


@router.post("/scan-now", tags=["admin"])
async def scan_now(
    as_of_date: Optional[date] = Query(None, description="Scan against this date (default: latest metrics date)"),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger the batch transition scanner. Useful for testing
    and for forcing observation accumulation outside the SLOW cycle.
    """
    target_date = as_of_date
    if target_date is None:
        target_date = (await db.execute(select(func.max(StockMetrics.date)))).scalar()
        if target_date is None:
            raise HTTPException(status_code=404, detail="No stock_metrics data available")

    scanner = BatchTransitionScanner(db)
    stats = await scanner.scan_universe(target_date)
    return asdict(stats)


@router.post("/reclassify", tags=["admin"])
async def reclassify_outcomes(db: AsyncSession = Depends(get_db)):
    """Re-corre la clasificación de outcome sobre observaciones ya resueltas
    usando los campos crudos persistidos (no re-descarga precios). Necesario
    tras cambiar la regla de clasificación para que la calibración refleje la
    nueva definición sin esperar a acumular observaciones nuevas.
    """
    from collections import Counter

    from app.services.outcome_tracker import OutcomeTracker

    resolved_or_neutral = ("SUCCESS", "FAILURE", "NEUTRAL")
    q = select(TransitionObservation).where(
        TransitionObservation.outcome_status.in_(resolved_or_neutral)
    )
    observations = (await db.execute(q)).scalars().all()

    tracker = OutcomeTracker(db)
    changed = 0
    by_status: Counter = Counter()
    for obs in observations:
        new_status = tracker._classify_outcome(obs)
        if new_status != obs.outcome_status:
            obs.outcome_status = new_status
            changed += 1
        by_status[new_status] += 1

    await db.commit()

    try:
        from app.services.empirical_probability_calculator import (
            EmpiricalProbabilityCalculator,
        )

        EmpiricalProbabilityCalculator.clear_cache()
    except Exception:
        pass

    return {
        "evaluated": len(observations),
        "changed": changed,
        "by_status": dict(by_status),
    }


async def _reclassify_observation_regimes(db: AsyncSession, engine_factory=None) -> dict:
    """Rebuild persisted regime labels from each detection date's snapshot."""
    from collections import Counter

    from app.services.market_regime_engine import MarketRegimeEngine

    engine_factory = engine_factory or MarketRegimeEngine
    date_rows = (
        await db.execute(
            select(
                TransitionObservation.date_detected,
                func.count(TransitionObservation.id).label("cnt"),
            )
            .where(TransitionObservation.date_detected.isnot(None))
            .group_by(TransitionObservation.date_detected)
            .order_by(TransitionObservation.date_detected)
        )
    ).all()

    engine = engine_factory(db)
    evaluated = 0
    changed = 0
    by_regime: Counter = Counter()
    unresolved_dates = []

    for row in date_rows:
        analysis = await engine.detect_regime(row.date_detected)
        if analysis.as_of is None:
            unresolved_dates.append(row.date_detected.isoformat())
            continue
        regime = analysis.regime.value
        evaluated += row.cnt
        by_regime[regime] += row.cnt
        result = await db.execute(
            update(TransitionObservation)
            .where(
                TransitionObservation.date_detected == row.date_detected,
                TransitionObservation.regime_at_detection.is_distinct_from(regime),
            )
            .values(regime_at_detection=regime)
        )
        changed += result.rowcount or 0

    await db.commit()

    from app.services.empirical_probability_calculator import EmpiricalProbabilityCalculator
    from app.services.outcome_tracker import _regime_cache

    EmpiricalProbabilityCalculator.clear_cache()
    _regime_cache.clear()

    return {
        "evaluated": evaluated,
        "changed": changed,
        "dates_evaluated": len(date_rows) - len(unresolved_dates),
        "by_regime": dict(by_regime),
        "unresolved_dates": unresolved_dates,
    }


@router.post("/reclassify-regimes", tags=["admin"])
async def reclassify_regimes(db: AsyncSession = Depends(get_db)):
    """Correct regime_at_detection using the no-lookahead market snapshot."""
    return await _reclassify_observation_regimes(db)
