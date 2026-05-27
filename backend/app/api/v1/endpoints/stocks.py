from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List
from app.core.deps import get_db
from app.models.stock import Stock, StockPrice, StockMetrics, TransitionObservation
from app.schemas.stock import Stock as StockSchema, StockPrice as StockPriceSchema, StockMetrics as StockMetricsSchema
from app.services.quality_leader_gate import evaluate_minervini_criteria
from app.services.symbol_diagnostic import (
    diagnose_actionable,
    diagnose_live,
    diagnose_u_and_r,
    diagnose_emerging_leaders,
    diagnose_building_bases,
    list_check_to_dict,
)
from app.services.group_strength_service import (
    fetch_current_group_strengths,
    compute_group_multiplier,
)
from app.services.context_decision_filter import (
    fetch_current_context,
    compute_context_multiplier,
)

router = APIRouter()


@router.get("/", response_model=List[StockSchema])
async def get_stocks(
    skip: int = 0,
    limit: int = 100,
    sector: str = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Stock).where(Stock.is_active == True)
    if sector:
        query = query.where(Stock.sector == sector)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{symbol}", response_model=StockSchema)
async def get_stock(symbol: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Stock).where(Stock.symbol == symbol.upper()))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock


@router.get("/{symbol}/prices", response_model=List[StockPriceSchema])
async def get_stock_prices(
    symbol: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    query = select(StockPrice).where(
        StockPrice.symbol == symbol.upper()
    ).order_by(StockPrice.date.desc()).limit(days)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{symbol}/metrics", response_model=StockMetricsSchema)
async def get_stock_metrics(symbol: str, db: AsyncSession = Depends(get_db)):
    query = select(StockMetrics).where(
        StockMetrics.symbol == symbol.upper()
    ).order_by(StockMetrics.date.desc()).limit(1)
    result = await db.execute(query)
    metrics = result.scalar_one_or_none()
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return metrics


@router.get("/{symbol}/diagnostic")
async def get_symbol_diagnostic(symbol: str, db: AsyncSession = Depends(get_db)):
    """Explain pass/fail per system list for any active ticker."""
    sym = symbol.upper()
    stock = (await db.execute(select(Stock).where(Stock.symbol == sym))).scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not found")

    latest_date = (await db.execute(select(func.max(StockMetrics.date)))).scalar()
    metrics = (await db.execute(
        select(StockMetrics)
        .where(StockMetrics.symbol == sym)
        .order_by(StockMetrics.date.desc())
        .limit(1)
    )).scalar_one_or_none()

    header = {
        "symbol": stock.symbol,
        "name": stock.name,
        "sector": stock.sector,
        "industry": stock.industry,
        "market_group": stock.market_group,
        "current_price": metrics.current_price if metrics else None,
        "has_metrics": metrics is not None,
        "metrics_date": metrics.date.isoformat() if metrics and metrics.date else None,
        "is_latest": (metrics is not None and latest_date is not None and metrics.date == latest_date),
    }

    if not metrics:
        return {
            "header": header,
            "note": f"No stock_metrics row found for {sym}. Stock may be delisted or outside the universe.",
            "lists": [],
            "transition_history": [],
            "market_context_applied": None,
            "group_strength": None,
            "minervini_status": None,
        }

    # 25-day metrics history for stateful checks (U&R, building bases)
    today = date.today()
    hist_start = today - timedelta(days=25)
    history_rows = (await db.execute(
        select(
            StockMetrics.date,
            StockMetrics.distance_to_ema21_atr,
            StockMetrics.distance_to_ema50_atr,
        )
        .where(StockMetrics.symbol == sym, StockMetrics.date >= hist_start)
        .order_by(StockMetrics.date)
    )).all()
    history_25d = [
        {"date": d, "d21": d21, "d50": d50}
        for d, d21, d50 in history_rows
    ]
    d21_history_nonnull = [h["d21"] for h in history_25d if h["d21"] is not None]

    # Recent observations (last 30d) for transition_history + boolean checks
    obs_cutoff = today - timedelta(days=30)
    obs_rows = (await db.execute(
        select(TransitionObservation)
        .where(TransitionObservation.symbol == sym, TransitionObservation.date_detected >= obs_cutoff)
        .order_by(desc(TransitionObservation.date_detected))
        .limit(10)
    )).scalars().all()
    transition_history = [
        {
            "transition_type": o.transition_type,
            "date_detected": o.date_detected.isoformat() if o.date_detected else None,
            "outcome_status": o.outcome_status,
        }
        for o in obs_rows
    ]
    # Booleans for /live (recent non-stable) and /u_and_r (last 2d non-stable)
    cutoff_2d = today - timedelta(days=2)
    has_recent_non_stable = any(o.transition_type != 'stable' for o in obs_rows)
    has_recent_2d_obs = any(
        o.transition_type != 'stable' and o.date_detected >= cutoff_2d
        for o in obs_rows
    )

    # Group strength + market context (for applied-multiplier reporting)
    group_perfs = await fetch_current_group_strengths(db)
    group_mult = compute_group_multiplier(stock.market_group, group_perfs)
    participation, leadership = await fetch_current_context(db)
    ctx_mult = compute_context_multiplier(participation, leadership)

    group_strength_payload = {
        "group": stock.market_group,
        "badge": group_mult.badge,
        "multiplier": group_mult.score_multiplier,
    }
    market_context_applied = {
        "participation": participation,
        "leadership": leadership,
        "score_multiplier": ctx_mult.score_multiplier,
        "suppress_lenses": list(ctx_mult.suppress_lenses),
        "surface_warnings": list(ctx_mult.surface_warnings),
    }

    # Run the diagnostics
    lists = [
        list_check_to_dict(diagnose_actionable(metrics)),
        list_check_to_dict(diagnose_live(metrics, has_recent_non_stable)),
        list_check_to_dict(diagnose_u_and_r(metrics, history_25d, has_recent_2d_obs)),
        list_check_to_dict(diagnose_emerging_leaders(metrics)),
        list_check_to_dict(diagnose_building_bases(metrics, d21_history_nonnull)),
    ]

    # Compute actual inclusion + rank by hitting the same endpoints/services the UI uses.
    # This makes "passes criteria + cutoff" answers truthful: passing filter ≠ appearing.
    import logging as _logging
    _log = _logging.getLogger(__name__)

    async def _augment_with_rank(list_key: str, fetch_symbols):
        try:
            symbols_in_order = await fetch_symbols()
            in_list = sym in symbols_in_order
            for lst in lists:
                if lst["key"] == list_key:
                    lst["appears_in_endpoint"] = in_list
                    lst["rank_in_endpoint"] = (
                        symbols_in_order.index(sym) + 1 if in_list else None
                    )
                    lst["total_in_endpoint"] = len(symbols_in_order)
                    break
        except Exception as e:
            _log.warning(f"diagnostic: rank for {sym} in {list_key} failed: {e}")

    async def _fetch_actionable_symbols():
        from app.api.v1.endpoints.transitions import get_actionable_setups
        resp = await get_actionable_setups(limit=12, db=db)
        return [s["symbol"] for s in resp.get("setups", [])]

    async def _fetch_live_symbols():
        from app.api.v1.endpoints.transitions import get_live_transitions
        resp = await get_live_transitions(limit=20, background_tasks=None, db=db)
        return [s["symbol"] for s in resp] if isinstance(resp, list) else []

    async def _fetch_uar_symbols():
        from app.services.setup_queue_service import SetupQueueService
        resp = await SetupQueueService(db).list_u_and_r()
        return [r["symbol"] for r in resp]

    async def _fetch_emerging_symbols():
        from app.services.setup_queue_service import SetupQueueService
        resp = await SetupQueueService(db).list_emerging_leaders()
        return [r["symbol"] for r in resp]

    async def _fetch_bases_symbols():
        from app.services.setup_queue_service import SetupQueueService
        resp = await SetupQueueService(db).list_building_bases()
        return [r["symbol"] for r in resp]

    await _augment_with_rank("actionable", _fetch_actionable_symbols)
    await _augment_with_rank("live", _fetch_live_symbols)
    await _augment_with_rank("u_and_r", _fetch_uar_symbols)
    await _augment_with_rank("emerging_leaders", _fetch_emerging_symbols)
    await _augment_with_rank("building_bases", _fetch_bases_symbols)

    # Minervini per-criterion breakdown (helpful when quality_leader fails)
    minervini_status = evaluate_minervini_criteria(metrics)

    return {
        "header": header,
        "lists": lists,
        "transition_history": transition_history,
        "market_context_applied": market_context_applied,
        "group_strength": group_strength_payload,
        "minervini_status": minervini_status,
    }
