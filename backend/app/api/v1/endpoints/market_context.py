"""API endpoint for Market Context Engine — Phase 1."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.stock import StockPrice, StockMetrics
from app.services.benchmarks import compute_index_trend
from app.services.market_context_engine import MarketContextEngine
from app.services.market_posture_record_service import market_posture_record_service, serialize_posture

router = APIRouter(prefix="/market-context", tags=["market-context"])


async def _build_index_block(db: AsyncSession, symbol: str = "SPY"):
    """Live-ish SPY tile: freshest intraday price from stock_prices, daily
    variation vs the previous day's close, trend from the stock_metrics MAs.

    Returns None when there is no price row for the symbol.
    """
    price_rows = (await db.execute(
        select(StockPrice.date, StockPrice.close)
        .where(StockPrice.symbol == symbol)
        .order_by(desc(StockPrice.date))
        .limit(2)
    )).all()
    if not price_rows:
        return None

    price = price_rows[0].close
    prev_close = price_rows[1].close if len(price_rows) > 1 else None
    change_pct = (
        (price - prev_close) / prev_close * 100.0
        if prev_close not in (None, 0)
        else None
    )

    m = (await db.execute(
        select(
            StockMetrics.ema50, StockMetrics.ema200,
            StockMetrics.sma150, StockMetrics.sma200, StockMetrics.high_52w,
        )
        .where(StockMetrics.symbol == symbol)
        .order_by(desc(StockMetrics.date))
        .limit(1)
    )).first()
    ema50 = m.ema50 if m else None
    ema200 = m.ema200 if m else None
    sma150 = m.sma150 if m else None
    sma200 = m.sma200 if m else None
    high_52w = m.high_52w if m else None

    return {
        "symbol": symbol,
        "price": price,
        "change_pct": change_pct,
        "trend": compute_index_trend(price, ema50, ema200, sma150, sma200),
        "above_ema50": (ema50 is not None and price > ema50),
        "above_ema200": (ema200 is not None and price > ema200),
        "new_high_52w": (high_52w is not None and price >= high_52w),
    }


@router.get("/current")
async def get_current_market_context(db: AsyncSession = Depends(get_db)):
    """Get current multi-dimensional market context (cached ~5 min).

    Returns participation, leadership and health-persistence engines for the
    latest stock_metrics date. The remaining engines are listed in
    `engines_pending`.
    """
    engine = MarketContextEngine(db)
    ctx = await engine.analyze()

    if ctx is None:
        raise HTTPException(status_code=404, detail="No market data available — stock_metrics is empty")

    response = _serialize_context(ctx, await _build_index_block(db))
    await market_posture_record_service.observe(db, ctx.as_of, response["posture"])
    return response


def _serialize_context(ctx, index):
    return {
        "as_of": ctx.as_of.isoformat(),
        "universe_size": ctx.universe_size,
        "regime": None if ctx.regime is None else {
            "descriptor": ctx.regime.regime.value,
            "as_of": ctx.regime.as_of.isoformat() if ctx.regime.as_of else None,
            "confidence": ctx.regime.confidence,
            "factors": {
                "breadth_quality": ctx.regime.breadth_quality,
                "leadership_health": ctx.regime.leadership_health,
                "speculative_appetite": ctx.regime.speculative_appetite,
                "sector_expansion": ctx.regime.sector_expansion,
                "pullback_environment_quality": ctx.regime.pullback_environment_quality,
            },
        },
        "posture": serialize_posture(ctx.posture),
        "participation": {
            "descriptor":           ctx.participation.descriptor,
            "delta_5d":             ctx.participation.delta_5d,
            "delta_sample_size_20d": ctx.participation.delta_sample_size_20d,
            "metrics":              ctx.participation.metrics,
            "history":              ctx.participation_history,
            "breadth_comparisons":  ctx.participation.breadth_comparisons,
        },
        "leadership": {
            "descriptor": ctx.leadership.descriptor,
            "delta_5d":   ctx.leadership.delta_5d,
            "metrics":    ctx.leadership.metrics,
            "history":    ctx.leadership_history,
        },
        "follow_through": None if ctx.follow_through is None else {
            "descriptor":           ctx.follow_through.descriptor,
            "basis":                ctx.follow_through.basis,
            "window_days":          ctx.follow_through.window_days,
            "signals":              ctx.follow_through.signals,
            "resolved":             ctx.follow_through.resolved,
            "success":              ctx.follow_through.success,
            "failure":              ctx.follow_through.failure,
            "neutral":              ctx.follow_through.neutral,
            "pending":              ctx.follow_through.pending,
            "delivery_rate":        ctx.follow_through.delivery_rate,
            "baseline_rate":        ctx.follow_through.baseline_rate,
            "baseline_n":           ctx.follow_through.baseline_n,
            "delta_pp":             ctx.follow_through.delta_pp,
            "provisional_on_track": ctx.follow_through.provisional_on_track,
            "provisional_failing":  ctx.follow_through.provisional_failing,
            "provisional_unclear":  ctx.follow_through.provisional_unclear,
            "per_family":           ctx.follow_through.per_family,
        },
        "health": None if ctx.health is None else {
            "state":                  ctx.health.state,
            "window_days":            ctx.health.window_days,
            "episodes":               ctx.health.episodes,
            "damaged_days":           ctx.health.damaged_days,
            "days_since_last_damage": ctx.health.days_since_last_damage,
            "repair_streak":          ctx.health.repair_streak,
            "repair_clean_days":      ctx.health.repair_clean_days,
            "repair_window_days":     ctx.health.repair_window_days,
            "repair_required_clean_days": ctx.health.repair_required_clean_days,
            "recent_severe_days":     ctx.health.recent_severe_days,
            "severe_lookback_days":   ctx.health.severe_lookback_days,
            "recovery_confirmation_streak": ctx.health.recovery_confirmation_streak,
            "recovery_confirmation_required_days": ctx.health.recovery_confirmation_required_days,
            "exceptional_recovery_session": ctx.health.exceptional_recovery_session,
            "series":                 ctx.health.series,
        },
        "engines_pending": ctx.engines_pending,
        "index": index,
    }


@router.get("/overview")
async def get_market_context_overview(db: AsyncSession = Depends(get_db)):
    from app.services.market_context_overview import get_overview_evidence

    engine = MarketContextEngine(db)
    ctx = await engine.analyze()
    if ctx is None:
        raise HTTPException(status_code=404, detail="No market data available — stock_metrics is empty")
    evolution = await engine.evolution_history(ctx.as_of)
    evidence = await get_overview_evidence(db, ctx.as_of)
    spy = evidence["indices"][0]
    index = {key: value for key, value in spy.items()
             if key not in ("date", "previous_date", "previous_price", "metrics_date")}
    context = _serialize_context(ctx, index if spy["price"] is not None else None)
    posture_observed = await market_posture_record_service.observe(
        db, ctx.as_of, context["posture"]
    )
    # Counts and constituents must reflect the same calculation, even when the
    # engine's own cached context predates a data refresh within this session.
    context["participation"]["breadth_comparisons"] = evidence["breadth"]
    posture_history = {"status": "unavailable", "records": []}
    spy_date = market_posture_record_service.valid_date(spy.get("date"))
    as_of = market_posture_record_service.valid_date(ctx.as_of)
    if posture_observed and as_of is not None:
        reference_dates = [as_of]
        if spy_date == as_of:
            previous_date = market_posture_record_service.valid_date(spy.get("previous_date"))
            if previous_date is not None and previous_date < as_of:
                reference_dates.append(previous_date)
        posture_history = await market_posture_record_service.history(db, reference_dates)
    return {"context": context, "indices": evidence["indices"], "extremes": evidence["extremes"],
            "evolution": evolution, "posture_history": posture_history}


@router.get("/volatility")
async def get_market_volatility(as_of: date):
    import asyncio
    from app.services.market_volatility import get_vix_current_quote, get_vix_quote

    daily, current = await asyncio.gather(get_vix_quote(as_of), get_vix_current_quote(as_of))
    return {"vix": daily, "current_quote": current}


@router.get("/sector-evolution")
async def get_market_context_sector_evolution(
    as_of: date, db: AsyncSession = Depends(get_db),
):
    from app.services.market_context_sector_evolution import get_sector_evolution

    return await get_sector_evolution(db, as_of)
