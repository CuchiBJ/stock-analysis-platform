"""Data-pipeline health endpoint — single source of truth for the UI banner
and the CLI health check. Returns latest dates, lag, and recent scheduler
errors so a stale/broken pipeline becomes impossible to ignore.
"""
from __future__ import annotations

from datetime import datetime, timedelta, date as date_cls
from typing import Optional

import pytz
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.stock import StockMetrics, StockPrice, SchedulerError

router = APIRouter(prefix="/health", tags=["health"])


async def build_health_snapshot(db: AsyncSession) -> dict:
    """Pure-ish builder so the CLI script can reuse it."""
    metrics_latest = (await db.execute(select(func.max(StockMetrics.date)))).scalar()
    price_latest = (await db.execute(select(func.max(StockPrice.date)))).scalar()

    metrics_lag_days: Optional[int] = None
    if metrics_latest and price_latest:
        metrics_lag_days = (price_latest - metrics_latest).days
    is_stale = bool(metrics_lag_days is not None and metrics_lag_days > 0)

    et = pytz.timezone("US/Eastern")
    now_et = datetime.now(et)
    today_et = now_et.date()
    is_weekday = today_et.weekday() < 5  # Mon=0 .. Fri=4

    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    errors_count = (await db.execute(
        select(func.count(SchedulerError.id))
        .where(SchedulerError.occurred_at >= cutoff_24h)
        .where(SchedulerError.resolved.is_(False))
    )).scalar() or 0

    recent_rows = (await db.execute(
        select(SchedulerError)
        .where(SchedulerError.occurred_at >= cutoff_24h)
        .where(SchedulerError.resolved.is_(False))
        .order_by(desc(SchedulerError.occurred_at))
        .limit(5)
    )).scalars().all()
    recent_errors = [
        {
            "task_name": r.task_name,
            "exception_type": r.exception_type,
            "exception_message": (r.exception_message or "")[:300],
            "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
        }
        for r in recent_rows
    ]

    warnings = []
    if is_stale:
        warnings.append(f"Stock metrics {metrics_lag_days} day(s) behind stock prices")
    if errors_count > 0:
        warnings.append(f"{errors_count} scheduler error(s) in the last 24h")

    return {
        "as_of": datetime.utcnow().isoformat(),
        "stock_metrics_latest": metrics_latest.isoformat() if metrics_latest else None,
        "stock_price_latest": price_latest.isoformat() if price_latest else None,
        "metrics_lag_days": metrics_lag_days,
        "is_stale": is_stale,
        "today_et": today_et.isoformat(),
        "is_weekday": is_weekday,
        "recent_errors_24h": errors_count,
        "recent_errors": recent_errors,
        "warnings": warnings,
    }


@router.get("/data-freshness")
async def data_freshness(db: AsyncSession = Depends(get_db)):
    return await build_health_snapshot(db)
