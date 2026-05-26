"""Calibration reporting — observed empirical success rate per transition type.

Reads `transition_observations` and computes, per `OperationalTransition`
value (excluding STABLE), the observed success rate over the resolved
sample (SUCCESS + FAILURE), exposing pending counts and an ETA for first
resolution when nothing has resolved yet.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.stock import TransitionObservation
from app.services.transition_engine import OperationalTransition

router = APIRouter(prefix="/calibration", tags=["calibration"])

MIN_SAMPLES_REQUIRED = 5
PENDING_STATUSES = ("PENDING", "INSUFFICIENT_DATA")
RESOLVED_STATUSES = ("SUCCESS", "FAILURE")
_STATUS_ORDER = {"empirical": 0, "insufficient": 1, "no_data": 2}


def _classify(n_resolved: int) -> str:
    if n_resolved >= MIN_SAMPLES_REQUIRED:
        return "empirical"
    if n_resolved > 0:
        return "insufficient"
    return "no_data"


@router.get("/by-transition-type")
async def calibration_by_transition_type(db: AsyncSession = Depends(get_db)):
    transition_values = [
        t.value for t in OperationalTransition if t.value != "stable"
    ]

    counts_q = (
        select(
            TransitionObservation.transition_type,
            TransitionObservation.outcome_status,
            func.count(TransitionObservation.id).label("cnt"),
        )
        .where(TransitionObservation.transition_type.in_(transition_values))
        .group_by(
            TransitionObservation.transition_type,
            TransitionObservation.outcome_status,
        )
    )
    raw_rows = (await db.execute(counts_q)).all()

    counts: dict[str, dict[str, int]] = {t: {} for t in transition_values}
    for r in raw_rows:
        counts[r.transition_type][r.outcome_status] = r.cnt

    rows = []
    total_observations = 0
    total_resolved = 0
    total_pending = 0

    for t in transition_values:
        c = counts[t]
        success = c.get("SUCCESS", 0)
        failure = c.get("FAILURE", 0)
        pending = c.get("PENDING", 0) + c.get("INSUFFICIENT_DATA", 0)
        neutral = c.get("NEUTRAL", 0)

        n_resolved = success + failure
        n_pending = pending
        n_observed = n_resolved + n_pending + neutral
        status = _classify(n_resolved)
        success_rate: Optional[float] = (
            success / n_resolved if status == "empirical" else None
        )

        rows.append(
            {
                "transition_type": t,
                "n_resolved": n_resolved,
                "n_pending": n_pending,
                "success_count": success,
                "failure_count": failure,
                "success_rate": success_rate,
                "status": status,
            }
        )

        total_observations += n_observed
        total_resolved += n_resolved
        total_pending += n_pending

    rows.sort(key=lambda r: (_STATUS_ORDER[r["status"]], -r["n_resolved"]))

    eta_first_data = None
    if total_resolved == 0 and total_pending > 0:
        oldest_pending = (
            await db.execute(
                select(func.min(TransitionObservation.date_detected)).where(
                    TransitionObservation.outcome_status.in_(PENDING_STATUSES)
                )
            )
        ).scalar()
        if oldest_pending is not None:
            eta_first_data = (oldest_pending + timedelta(days=10)).isoformat()

    return {
        "min_samples_required": MIN_SAMPLES_REQUIRED,
        "total_observations": total_observations,
        "total_resolved": total_resolved,
        "total_pending": total_pending,
        "eta_first_data": eta_first_data,
        "rows": rows,
    }
