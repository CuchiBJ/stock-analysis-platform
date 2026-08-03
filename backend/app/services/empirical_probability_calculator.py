"""Context-aware empirical continuation probability.

The fallback ladder prefers cohorts comparable to the current setup while
requiring progressively larger samples as specificity decreases:
  1. recent transition + regime + RS bucket (20)
  2. recent transition (30)
  3. transition + regime + RS bucket (20)
  4. transition + regime (30)
  5. transition + RS bucket (30)
  6. transition across all contexts (50)
  7. rule-based sentinel

Cache: per-process in-memory dict, TTL = 600 s.
  Cleared on every outcome_tracker.evaluate_pending_outcomes() write.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.stock import TransitionObservation
import logging

logger = logging.getLogger(__name__)

MIN_CONTEXT_RS_SAMPLE = 20
MIN_CONTEXT_SAMPLE = 30
MIN_RS_SAMPLE = 30
MIN_GLOBAL_SAMPLE = 50
RECENT_CONTEXT_DAYS = 21
_CACHE_TTL_SECONDS = 600

_cache: dict[tuple, tuple[EmpiricalLookupResult, datetime]] = {}


@dataclass
class EmpiricalLookupResult:
    probability: float
    source: str   # "empirical" | "rule_based"
    sample_size: int
    basis: str


def _rs_bucket(rs_value: Optional[float]) -> str:
    """Map a raw RS value to one of five bucket labels."""
    if rs_value is None:
        return 'unknown'
    if rs_value >= 120.0:
        return 'gte_120'
    if rs_value >= 110.0:
        return '110_120'
    if rs_value >= 100.0:
        return '100_110'
    return 'lt_100'


class EmpiricalProbabilityCalculator:
    def __init__(self, db: AsyncSession):
        self.db = db

    @classmethod
    def clear_cache(cls) -> None:
        _cache.clear()

    async def _query_cohort(
        self,
        transition_type: str,
        rs_bucket: Optional[str] = None,
        regime: Optional[str] = None,
        since: Optional[date] = None,
        as_of_date: Optional[date] = None,
    ) -> tuple[int, int, int]:
        """Return (success, failure, neutral). Pending outcomes are excluded."""
        conditions: list = [
            TransitionObservation.transition_type == transition_type,
            TransitionObservation.outcome_status.in_(['SUCCESS', 'FAILURE', 'NEUTRAL']),
        ]
        if regime is not None:
            conditions.append(TransitionObservation.regime_at_detection == regime)
        if since is not None:
            conditions.append(TransitionObservation.date_detected > since)
        if as_of_date is not None:
            conditions.append(TransitionObservation.date_detected <= as_of_date)
        if rs_bucket is not None:
            if rs_bucket == 'unknown':
                conditions.append(TransitionObservation.rs_spy_at_detection.is_(None))
            elif rs_bucket == 'lt_100':
                conditions.append(TransitionObservation.rs_spy_at_detection < 100.0)
            elif rs_bucket == '100_110':
                conditions.append(TransitionObservation.rs_spy_at_detection >= 100.0)
                conditions.append(TransitionObservation.rs_spy_at_detection < 110.0)
            elif rs_bucket == '110_120':
                conditions.append(TransitionObservation.rs_spy_at_detection >= 110.0)
                conditions.append(TransitionObservation.rs_spy_at_detection < 120.0)
            elif rs_bucket == 'gte_120':
                conditions.append(TransitionObservation.rs_spy_at_detection >= 120.0)

        q = (
            select(
                TransitionObservation.outcome_status,
                func.count(TransitionObservation.id).label('cnt'),
            )
            .where(and_(*conditions))
            .group_by(TransitionObservation.outcome_status)
        )
        rows = (await self.db.execute(q)).all()
        success = sum(r.cnt for r in rows if r.outcome_status == 'SUCCESS')
        failure = sum(r.cnt for r in rows if r.outcome_status == 'FAILURE')
        neutral = sum(r.cnt for r in rows if r.outcome_status == 'NEUTRAL')
        return success, failure, neutral

    async def lookup(
        self,
        transition_type: str,
        rs_value: Optional[float],
        current_regime: Optional[str] = None,
        as_of_date: Optional[date] = None,
    ) -> EmpiricalLookupResult:
        """
        Attempt context-aware empirical lookup, falling back through the ladder.
        """
        if not transition_type or transition_type.lower() == "stable":
            return EmpiricalLookupResult(
                probability=0.0,
                source="rule_based",
                sample_size=0,
                basis="rule_formula",
            )

        transition_type = transition_type.lower()
        bucket = _rs_bucket(rs_value)
        regime = (current_regime or "").lower()
        usable_regime = regime if regime and regime != "unknown" else None
        cache_key = (
            transition_type,
            bucket,
            usable_regime or "UNKNOWN",
            as_of_date.isoformat() if as_of_date else "LIVE",
        )

        cached = _cache.get(cache_key)
        if cached is not None:
            result, ts = cached
            if (datetime.utcnow() - ts).total_seconds() < _CACHE_TTL_SECONDS:
                return result

        recent_since = as_of_date - timedelta(days=RECENT_CONTEXT_DAYS) if as_of_date else None
        ladder: list[
            tuple[str, int, Optional[str], Optional[str], Optional[date]]
        ] = []
        if recent_since is not None and usable_regime is not None:
            ladder.append(
                ("transition_recent_regime_rs", MIN_CONTEXT_RS_SAMPLE, bucket, usable_regime, recent_since)
            )
        if recent_since is not None:
            ladder.append(
                ("transition_recent", MIN_CONTEXT_SAMPLE, None, None, recent_since)
            )
        if usable_regime is not None:
            ladder.extend([
                ("transition_regime_rs", MIN_CONTEXT_RS_SAMPLE, bucket, usable_regime, None),
                ("transition_regime", MIN_CONTEXT_SAMPLE, None, usable_regime, None),
            ])
        ladder.extend([
            ("transition_rs", MIN_RS_SAMPLE, bucket, None, None),
            ("transition_all", MIN_GLOBAL_SAMPLE, None, None, None),
        ])

        for basis, minimum, cohort_bucket, cohort_regime, cohort_since in ladder:
            success, failure, neutral = await self._query_cohort(
                transition_type,
                rs_bucket=cohort_bucket,
                regime=cohort_regime,
                since=cohort_since,
                as_of_date=as_of_date if cohort_since is not None else None,
            )
            sample_size = success + failure + neutral
            if sample_size >= minimum:
                result = EmpiricalLookupResult(
                    probability=success / sample_size,
                    source="empirical",
                    sample_size=sample_size,
                    basis=basis,
                )
                _cache[cache_key] = (result, datetime.utcnow())
                return result

        # Level 4: rule-based sentinel — caller evaluates the formula
        result = EmpiricalLookupResult(
            probability=0.0,
            source="rule_based",
            sample_size=0,
            basis="rule_formula",
        )
        _cache[cache_key] = (result, datetime.utcnow())
        return result
