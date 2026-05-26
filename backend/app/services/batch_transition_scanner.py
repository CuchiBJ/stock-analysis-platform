"""Batch transition scanner — walks the quality-filtered universe and
invokes TransitionEngine on each (current, previous) metrics pair so
that non-STABLE observations get persisted in `transition_observations`.

Designed to run after each SLOW metrics cycle (when current metrics are
fresh) plus expose a manual trigger for testing and forced runs.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockMetrics
from app.services.transition_engine import TransitionEngine, OperationalTransition
from app.services.universe_filters import QUALITY_FILTERS

logger = logging.getLogger(__name__)


@dataclass
class ScanStats:
    as_of_date: Optional[str]
    scanned: int
    non_stable_detected: int
    recorded: int
    errors: int
    duration_sec: float


class BatchTransitionScanner:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def scan_universe(self, as_of_date: date) -> ScanStats:
        t0 = time.monotonic()

        latest = (
            await self.db.execute(select(func.max(StockMetrics.date)))
        ).scalar()
        if latest is None or latest != as_of_date:
            logger.warning(
                f"BatchTransitionScanner: as_of_date={as_of_date} does not match latest metrics date={latest}; aborting"
            )
            return ScanStats(
                as_of_date=as_of_date.isoformat() if as_of_date else None,
                scanned=0, non_stable_detected=0, recorded=0, errors=0,
                duration_sec=round(time.monotonic() - t0, 2),
            )

        curr_q = (
            select(StockMetrics)
            .where(StockMetrics.date == as_of_date)
            .where(and_(*QUALITY_FILTERS))
            .order_by(StockMetrics.symbol.asc())
        )
        currents = (await self.db.execute(curr_q)).scalars().all()
        symbols = [m.symbol for m in currents]
        if not symbols:
            return ScanStats(
                as_of_date=as_of_date.isoformat(),
                scanned=0, non_stable_detected=0, recorded=0, errors=0,
                duration_sec=round(time.monotonic() - t0, 2),
            )

        prev_subq = (
            select(
                StockMetrics.symbol.label("sym"),
                func.max(StockMetrics.date).label("prev_date"),
            )
            .where(StockMetrics.symbol.in_(symbols))
            .where(StockMetrics.date < as_of_date)
            .group_by(StockMetrics.symbol)
            .subquery()
        )
        prev_q = (
            select(StockMetrics)
            .join(
                prev_subq,
                and_(
                    StockMetrics.symbol == prev_subq.c.sym,
                    StockMetrics.date == prev_subq.c.prev_date,
                ),
            )
        )
        prev_rows = (await self.db.execute(prev_q)).scalars().all()
        prev_by_symbol = {p.symbol: p for p in prev_rows}

        engine = TransitionEngine(self.db)

        scanned = 0
        non_stable = 0
        errors = 0

        for curr in currents:
            prev = prev_by_symbol.get(curr.symbol)
            if prev is None:
                continue
            scanned += 1
            try:
                result = await engine.calculate_operational_transition(
                    symbol=curr.symbol,
                    current_metrics=curr,
                    previous_metrics=prev,
                )
                if result.transition != OperationalTransition.STABLE:
                    non_stable += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    f"BatchTransitionScanner: {curr.symbol} raised {type(exc).__name__}: {exc}"
                )

        await self.db.commit()

        stats = ScanStats(
            as_of_date=as_of_date.isoformat(),
            scanned=scanned,
            non_stable_detected=non_stable,
            recorded=non_stable,  # upper bound; idempotency collisions silently dedupe
            errors=errors,
            duration_sec=round(time.monotonic() - t0, 2),
        )
        logger.info(
            f"BatchTransitionScanner: scanned={stats.scanned} non_stable={stats.non_stable_detected} "
            f"recorded={stats.recorded} errors={stats.errors} duration={stats.duration_sec}s"
        )
        return stats
