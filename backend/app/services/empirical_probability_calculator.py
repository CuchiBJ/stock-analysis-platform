"""Empirical continuation probability — stratified success rates from
transition_observations. Falls back to a rule-based sentinel when no cohort
level meets the minimum sample threshold.

Cohort key (Phase 1):  (transition_type, rs_bucket)
  Level 2 from the full ladder — participation_at_detection is not yet stored
  in transition_observations, so Level 1 (with participation) is skipped.

Fallback ladder:
  Level 2: (transition_type, rs_bucket)
  Level 3: (transition_type,)
  Level 4: rule-based sentinel — probability=0.0, source="rule_based"

Cache: per-process in-memory dict, TTL = 600 s.
  Cleared on every outcome_tracker.evaluate_pending_outcomes() write.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.stock import TransitionObservation
import logging

logger = logging.getLogger(__name__)

MIN_SAMPLE_SIZE = 5
_CACHE_TTL_SECONDS = 600

_cache: dict[tuple, tuple[EmpiricalLookupResult, datetime]] = {}


@dataclass
class EmpiricalLookupResult:
    probability: float
    source: str   # "empirical" | "rule_based"
    sample_size: int


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
    ) -> tuple[int, int]:
        """Return (success_count, failure_count). NEUTRAL/PENDING excluded."""
        conditions: list = [
            TransitionObservation.transition_type == transition_type,
            TransitionObservation.outcome_status.in_(['SUCCESS', 'FAILURE']),
        ]
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
        return success, failure

    async def lookup(
        self,
        transition_type: str,
        rs_value: Optional[float],
        participation: Optional[str] = None,
    ) -> EmpiricalLookupResult:
        """
        Attempt empirical lookup, falling back through the ladder.
        participation is accepted but currently unused (not yet stored in DB).
        """
        bucket = _rs_bucket(rs_value)
        cache_key = (transition_type, bucket, participation or 'UNKNOWN')

        cached = _cache.get(cache_key)
        if cached is not None:
            result, ts = cached
            if (datetime.utcnow() - ts).total_seconds() < _CACHE_TTL_SECONDS:
                return result

        # Level 2: (transition_type, rs_bucket)
        success, failure = await self._query_cohort(transition_type, rs_bucket=bucket)
        if success + failure >= MIN_SAMPLE_SIZE:
            result = EmpiricalLookupResult(
                probability=success / (success + failure),
                source='empirical',
                sample_size=success + failure,
            )
            _cache[cache_key] = (result, datetime.utcnow())
            return result

        # Level 3: (transition_type,)
        success, failure = await self._query_cohort(transition_type)
        if success + failure >= MIN_SAMPLE_SIZE:
            result = EmpiricalLookupResult(
                probability=success / (success + failure),
                source='empirical',
                sample_size=success + failure,
            )
            _cache[cache_key] = (result, datetime.utcnow())
            return result

        # Level 4: rule-based sentinel — caller evaluates the formula
        result = EmpiricalLookupResult(probability=0.0, source='rule_based', sample_size=0)
        _cache[cache_key] = (result, datetime.utcnow())
        return result
