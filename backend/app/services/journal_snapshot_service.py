"""Journal snapshot service — captures system engine outputs at trade entry.

Every successful `POST /journal/trades` invokes `take_entry_snapshot()` which
returns a dict with the four system snapshots that get persisted on the trade
row. Each snapshot is computed via a try/except so partial failure of one
engine doesn't prevent the others from being recorded.

Snapshot dimensions:
- regime_at_entry: composite "<participation>/<leadership>" from MarketContextEngine
- system_score_at_entry: priority_score (0-1) from SetupPriorityEngine if metrics exist
- group_strength_at_entry: "leader"|"neutral"|"weak" from GroupStrengthService for the symbol's market_group
- leader_health_at_entry: overall_health_score (0-1) from LeaderHealthCalculator (market-wide)

All four fields are nullable in the response — a None means the underlying
engine had no data or an exception was caught (logged as warning).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock, StockMetrics

logger = logging.getLogger(__name__)


async def _snapshot_regime(db: AsyncSession) -> Optional[str]:
    try:
        from app.services.market_context_engine import MarketContextEngine
        ctx = await MarketContextEngine(db).analyze()
        if ctx is None:
            return None
        return f"{ctx.participation.descriptor}/{ctx.leadership.descriptor}"
    except Exception as exc:
        logger.warning("snapshot_regime failed: %s", exc)
        return None


async def _snapshot_group_strength(db: AsyncSession, symbol: str) -> Optional[str]:
    try:
        from app.services.group_strength_service import (
            compute_group_multiplier,
            fetch_current_group_strengths,
        )
        stock = await db.get(Stock, symbol)
        if stock is None or not stock.market_group:
            return None
        group_perfs = await fetch_current_group_strengths(db)
        return compute_group_multiplier(stock.market_group, group_perfs).badge
    except Exception as exc:
        logger.warning("snapshot_group_strength failed for %s: %s", symbol, exc)
        return None


async def _snapshot_leader_health(db: AsyncSession) -> Optional[float]:
    try:
        from app.services.leader_health_calculator import LeaderHealthCalculator
        metrics = await LeaderHealthCalculator(db).calculate_leader_health()
        return metrics.overall_health_score
    except Exception as exc:
        logger.warning("snapshot_leader_health failed: %s", exc)
        return None


async def _snapshot_system_score(
    db: AsyncSession, symbol: str, entry_date: date, regime: Optional[str]
) -> Optional[float]:
    """Compute the priority_score the system would assign for this symbol at
    the entry date. Requires a StockMetrics row at or before entry_date.
    Returns None when no metrics exist for the symbol."""
    try:
        result = await db.execute(
            select(StockMetrics)
            .where(StockMetrics.symbol == symbol)
            .where(StockMetrics.date <= entry_date)
            .order_by(StockMetrics.date.desc())
            .limit(1)
        )
        metrics = result.scalar_one_or_none()
        if metrics is None:
            return None
        from app.services.setup_lifecycle_engine import SetupLifecycleEngine
        from app.services.setup_priority_engine import SetupPriorityEngine
        state = SetupLifecycleEngine(db).detect_current_state(metrics)
        priority = SetupPriorityEngine().calculate_priority_score(metrics, state, regime)
        return priority.priority_score
    except Exception as exc:
        logger.warning("snapshot_system_score failed for %s @ %s: %s", symbol, entry_date, exc)
        return None


async def take_entry_snapshot(
    db: AsyncSession, symbol: str, entry_date: date
) -> dict:
    """Returns dict with the 4 snapshot fields. Never raises — failed lookups
    return None for that field."""
    regime = await _snapshot_regime(db)
    return {
        "regime_at_entry": regime,
        "group_strength_at_entry": await _snapshot_group_strength(db, symbol),
        "leader_health_at_entry": await _snapshot_leader_health(db),
        "system_score_at_entry": await _snapshot_system_score(db, symbol, entry_date, regime),
    }
