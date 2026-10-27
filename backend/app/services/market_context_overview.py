"""Dated benchmark evidence and constituents for the dedicated context page."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import date
import math
from time import monotonic
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockMetrics, StockPrice
from app.services.benchmarks import compute_index_trend
from app.services.market_context_breadth import calculate_breadth_comparisons

_CACHE_TTL = 300
_CACHE_LIMIT = 4
_cache: OrderedDict[date, tuple[float, dict[str, Any]]] = OrderedDict()


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


async def build_dated_index(db: AsyncSession, symbol: str, as_of: date) -> dict[str, Any]:
    result = dict.fromkeys(("price", "change_pct", "date", "previous_date", "previous_price", "metrics_date", "trend",
                           "above_ema50", "above_ema200", "new_high_52w"))
    result["symbol"] = symbol
    prices = (await db.execute(
        select(StockPrice.date, StockPrice.close)
        .where(StockPrice.symbol == symbol, StockPrice.date <= as_of)
        .order_by(desc(StockPrice.date)).limit(1)
    )).all()
    if not prices:
        return result
    latest = prices[0]
    result["date"] = latest.date.isoformat()
    price = _positive(latest.close)
    result["price"] = price
    # Daily change requires the immediately preceding market session, not an
    # arbitrary older quote when a benchmark has a gap in its stored series.
    previous_date = (await db.execute(
        select(StockPrice.date)
        .where(StockPrice.symbol == "SPY", StockPrice.date < latest.date)
        .order_by(desc(StockPrice.date)).limit(1)
    )).scalar_one_or_none()
    previous = None
    if previous_date is not None:
        result["previous_date"] = previous_date.isoformat()
        previous = _positive((await db.execute(
            select(StockPrice.close)
            .where(StockPrice.symbol == symbol, StockPrice.date == previous_date)
        )).scalar_one_or_none())
        result["previous_price"] = previous
    if price is not None and previous is not None:
        result["change_pct"] = (price / previous - 1) * 100
    metrics = (await db.execute(
        select(StockMetrics.date, StockMetrics.ema50, StockMetrics.ema200,
               StockMetrics.sma150, StockMetrics.sma200, StockMetrics.high_52w)
        .where(StockMetrics.symbol == symbol, StockMetrics.date <= latest.date)
        .order_by(desc(StockMetrics.date)).limit(1)
    )).first()
    if metrics is None:
        return result
    result["metrics_date"] = metrics.date.isoformat()
    if price is None:
        return result
    ema50, ema200, sma150, sma200, high = (
        _positive(value) for value in
        (metrics.ema50, metrics.ema200, metrics.sma150, metrics.sma200, metrics.high_52w)
    )
    if all(value is not None for value in (ema50, ema200, sma150, sma200)):
        result["trend"] = compute_index_trend(price, ema50, ema200, sma150, sma200)
    result["above_ema50"] = price > ema50 if ema50 is not None else None
    result["above_ema200"] = price > ema200 if ema200 is not None else None
    result["new_high_52w"] = price >= high if high is not None else None
    return result


async def get_overview_evidence(db: AsyncSession, as_of: date) -> dict[str, Any]:
    cached = _cache.get(as_of)
    if cached is not None and monotonic() - cached[0] < _CACHE_TTL:
        _cache.move_to_end(as_of)
        return deepcopy(cached[1])
    # A single AsyncSession cannot execute concurrent statements.
    indices = [await build_dated_index(db, symbol, as_of) for symbol in ("SPY", "QQQ")]
    breadth = await calculate_breadth_comparisons(db, as_of, include_constituents=True)
    extremes = breadth["new_session_highs_vs_lows"]
    sectors = extremes.pop("sectors")
    evidence = {
        "indices": indices,
        "breadth": breadth,
        "extremes": {"date": breadth["date"], **extremes, "sectors": sectors},
    }
    _cache[as_of] = (monotonic(), deepcopy(evidence))
    _cache.move_to_end(as_of)
    while len(_cache) > _CACHE_LIMIT:
        _cache.popitem(last=False)
    return evidence
