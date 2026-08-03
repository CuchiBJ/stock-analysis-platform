"""Data-pipeline health endpoint — single source of truth for the UI banner,
the always-on PipelineHealthChip, and the CLI health check. Returns latest
dates, lag, recent errors, per-cycle heartbeats, universe coverage, and
market state so a stale/broken/partial pipeline becomes impossible to ignore.
"""
from __future__ import annotations

from datetime import datetime, timedelta, time as _time
from typing import Optional

import pytz
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.stock import (
    StockMetrics,
    StockPrice,
    SchedulerError,
    PipelineHeartbeat,
)
from app.services.universe_filters import QUALITY_FILTERS

router = APIRouter(prefix="/health", tags=["health"])

# Cycles recorded in pipeline_heartbeats that are NOT part of the data pipeline
# and must not drive the health chip. ibkr_sync is a best-effort nightly broker
# journal pull — it no-ops without Flex credentials and routinely "fails" on
# IBKR rate-limiting (code 1001), which would otherwise flip the whole pipeline
# health to red for a reason unrelated to data freshness. Its heartbeat is still
# persisted for ops; it's just excluded from the health snapshot.
NON_PIPELINE_CYCLES = frozenset({"ibkr_sync"})


MARKET_OPEN_ET = _time(9, 30)
MARKET_WARMUP_END_ET = _time(10, 30)
MARKET_CLOSE_ET = _time(16, 0)
AFTER_HOURS_END_ET = _time(20, 0)
ET = pytz.timezone("US/Eastern")


def compute_market_state(now_et: datetime) -> dict:
    """Pure helper — derive market session phase from an ET-aware datetime."""
    is_weekday = now_et.weekday() < 5
    t = now_et.time()
    if not is_weekday:
        return {
            "is_open": False,
            "is_warmup": False,
            "minutes_since_open": None,
            "session_phase": "closed",
        }

    open_dt = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    minutes_since_open = int((now_et - open_dt).total_seconds() // 60)

    if t < MARKET_OPEN_ET:
        phase = "pre_market"
        is_open = False
        is_warmup = False
    elif t <= MARKET_WARMUP_END_ET:
        phase = "warmup"
        is_open = True
        is_warmup = True
    elif t <= MARKET_CLOSE_ET:
        phase = "regular"
        is_open = True
        is_warmup = False
    elif t <= AFTER_HOURS_END_ET:
        phase = "after_hours"
        is_open = False
        is_warmup = False
    else:
        phase = "closed"
        is_open = False
        is_warmup = False

    return {
        "is_open": is_open,
        "is_warmup": is_warmup,
        "minutes_since_open": minutes_since_open,
        "session_phase": phase,
    }


async def _coverage(db: AsyncSession, now_et: datetime) -> dict:
    """Coverage = reference quality cohort refreshed today / cohort size.

    Both numerator and denominator are restricted to the QUALITY universe (the
    curated institutional set: mid/large cap, liquid, non-penny, min ADR) — the
    same set the UI banner promises ("Quality universe symbols refreshed since
    today's market open"). These are the TIER-1 names the pipeline refreshes
    every cycle, so healthy coverage climbs to ~100% intraday.

    Why NOT the full price universe: not every symbol with a price ever gets
    metrics (insufficient history, filtered out), so a full-universe denominator
    caps coverage well below 100% even on a fully-processed day. And anchoring to
    a still-loading `max(date)` makes the denominator swing through the day.

    The cohort is frozen from the last COMPLETE session (the most recent metrics
    date strictly before the working session). Both numerator and denominator use
    that same symbol set. Reapplying QUALITY_FILTERS to today's values would turn
    legitimate membership changes (for example ADR falling below 4%) into false
    coverage gaps even when the symbol was refreshed successfully.
    """
    latest_price_date = (await db.execute(select(func.max(StockPrice.date)))).scalar()
    if latest_price_date is None:
        return {"expected": 0, "actual": 0, "pct": 0.0}

    # Stable denominator: quality-universe size on the last complete metrics
    # session (strictly before today's still-filling working date).
    ref_date = (
        await db.execute(
            select(func.max(StockMetrics.date)).where(StockMetrics.date < latest_price_date)
        )
    ).scalar()
    if ref_date is None:
        return {"expected": 0, "actual": 0, "pct": 0.0}

    quality_cohort = (
        select(StockMetrics.symbol)
        .where(StockMetrics.date == ref_date, *QUALITY_FILTERS)
        .distinct()
        .subquery()
    )
    expected = (
        await db.execute(select(func.count()).select_from(quality_cohort))
    ).scalar() or 0

    market_open_et = ET.localize(
        datetime.combine(now_et.date(), MARKET_OPEN_ET)
    )
    # Keep the tz-aware value: comparing a naive datetime parameter against a
    # TIMESTAMPTZ column under asyncpg silently produces 0 matches because the
    # naive value is interpreted in an unexpected zone. Tz-aware UTC is safe.
    market_open_utc = market_open_et.astimezone(pytz.UTC)

    actual_q = (
        select(func.count(func.distinct(StockMetrics.symbol)))
        .where(
            StockMetrics.date == latest_price_date,
            StockMetrics.updated_at >= market_open_utc,
            StockMetrics.symbol.in_(select(quality_cohort.c.symbol)),
        )
    )
    actual = (await db.execute(actual_q)).scalar() or 0

    # Defensive cap: the fixed cohort makes actual <= expected by construction.
    pct = min(100.0, actual / expected * 100.0) if expected > 0 else 0.0
    return {"expected": int(expected), "actual": int(actual), "pct": round(pct, 1)}


async def _heartbeats(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(PipelineHeartbeat)
            .where(PipelineHeartbeat.cycle_name.notin_(NON_PIPELINE_CYCLES))
            .order_by(PipelineHeartbeat.cycle_name)
        )
    ).scalars().all()
    now = datetime.utcnow()
    out: list[dict] = []
    for r in rows:
        last_run = r.last_run_at
        # Normalize to naive UTC for delta arithmetic
        if last_run is not None and last_run.tzinfo is not None:
            last_run_naive = last_run.astimezone(pytz.UTC).replace(tzinfo=None)
        else:
            last_run_naive = last_run
        age_seconds = int((now - last_run_naive).total_seconds()) if last_run_naive else None
        out.append({
            "cycle_name": r.cycle_name,
            "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            "last_success_at": r.last_success_at.isoformat() if r.last_success_at else None,
            "last_duration_seconds": float(r.last_duration_seconds or 0.0),
            "symbols_processed": r.symbols_processed,
            "symbols_expected": r.symbols_expected,
            "status": r.status,
            "last_error_message": r.last_error_message,
            "age_seconds": age_seconds,
        })
    return out


async def build_health_snapshot(db: AsyncSession) -> dict:
    """Pure-ish builder so the CLI script can reuse it."""
    metrics_latest = (await db.execute(select(func.max(StockMetrics.date)))).scalar()
    price_latest = (await db.execute(select(func.max(StockPrice.date)))).scalar()

    metrics_lag_days: Optional[int] = None
    if metrics_latest and price_latest:
        metrics_lag_days = (price_latest - metrics_latest).days
    is_stale = bool(metrics_lag_days is not None and metrics_lag_days > 0)

    now_et = datetime.now(ET)
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

    heartbeats = await _heartbeats(db)
    coverage = await _coverage(db, now_et)
    market_state = compute_market_state(now_et)

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
        "pipeline_heartbeats": heartbeats,
        "coverage": coverage,
        "market_state": market_state,
        "warnings": warnings,
    }


@router.get("/data-freshness")
async def data_freshness(db: AsyncSession = Depends(get_db)):
    return await build_health_snapshot(db)
