"""Bulk reconstruction of recent sector previous-session extreme incidence."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import date
from time import monotonic
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock, StockMetrics, StockPrice
from app.services.market_context_breadth import EXTREME_LOOKBACK_SESSIONS, evaluate_session_extreme
from app.services.universe_filters import QUALITY_FILTERS

_CACHE_TTL = 300
_CACHE_LIMIT = 4
_cache: OrderedDict[date, tuple[float, dict[str, Any]]] = OrderedDict()


def _sector(value: str | None) -> str:
    return (value or "").strip() or "Sin sector"


def _remember(as_of: date, result: dict[str, Any]) -> None:
    _cache[as_of] = (monotonic(), deepcopy(result))
    _cache.move_to_end(as_of)
    while len(_cache) > _CACHE_LIMIT:
        _cache.popitem(last=False)


async def get_sector_evolution(db: AsyncSession, as_of: date) -> dict[str, Any]:
    cached = _cache.get(as_of)
    if cached is not None and monotonic() - cached[0] < _CACHE_TTL:
        _cache.move_to_end(as_of)
        return deepcopy(cached[1])

    descending_dates = (await db.execute(
        select(StockPrice.date).where(StockPrice.symbol == "SPY", StockPrice.date <= as_of)
        .distinct().order_by(desc(StockPrice.date)).limit(EXTREME_LOOKBACK_SESSIONS + 5)
    )).scalars().all()
    all_dates = sorted(set(descending_dates))
    if as_of not in all_dates:
        result = {"as_of": as_of.isoformat(), "status": "no_reference_session", "sessions": []}
        _remember(as_of, result)
        return deepcopy(result)
    target_dates = all_dates[-5:]

    quality_rows = (await db.execute(
        select(StockMetrics.date, StockMetrics.symbol, Stock.sector)
        .join(Stock, Stock.symbol == StockMetrics.symbol)
        .where(StockMetrics.date.in_(target_dates), *QUALITY_FILTERS).distinct()
    )).all()
    symbols_by_date: dict[date, set[str]] = {day: set() for day in target_dates}
    metadata: dict[str, Any] = {}
    for row in quality_rows:
        symbols_by_date[row.date].add(row.symbol)
        metadata[row.symbol] = row.sector
    symbols = {symbol for symbols_for_day in symbols_by_date.values() for symbol in symbols_for_day}

    price_by_symbol_date: dict[str, dict[date, tuple[Any, Any]]] = {}
    if symbols and all_dates:
        price_rows = (await db.execute(
            select(StockPrice.symbol, StockPrice.date, StockPrice.high, StockPrice.low)
            .where(StockPrice.symbol.in_(symbols), StockPrice.date.in_(all_dates))
        )).all()
        for row in price_rows:
            price_by_symbol_date.setdefault(row.symbol, {})[row.date] = (row.high, row.low)

    sessions = []
    for target in target_dates:
        prior_dates = [day for day in all_dates if day < target][-EXTREME_LOOKBACK_SESSIONS:]
        sector_counts: dict[str, dict[str, int | str]] = {}
        symbols_for_day = symbols_by_date[target]
        for symbol in sorted(symbols_for_day):
            sector = _sector(metadata.get(symbol))
            group = sector_counts.setdefault(sector, {
                "sector": sector, "eligible_symbols": 0, "excluded_symbols": 0,
                "high_count": 0, "low_count": 0,
            })
            by_date = price_by_symbol_date.get(symbol, {})
            current = by_date.get(target)
            prior_pairs = [by_date[day] for day in prior_dates if day in by_date]
            eligible, high_event, low_event = evaluate_session_extreme(
                current[0] if current else None, current[1] if current else None, prior_pairs,
            )
            if eligible:
                group["eligible_symbols"] += 1
                group["high_count"] += int(high_event)
                group["low_count"] += int(low_event)
            else:
                group["excluded_symbols"] += 1

        sectors = [sector_counts[key] for key in sorted(sector_counts)]
        sessions.append({
            "date": target.isoformat(),
            "eligible_symbols": sum(int(group["eligible_symbols"]) for group in sectors),
            "excluded_symbols": sum(int(group["excluded_symbols"]) for group in sectors),
            "high_count": sum(int(group["high_count"]) for group in sectors),
            "low_count": sum(int(group["low_count"]) for group in sectors),
            "sectors": sectors,
        })

    result = {"as_of": as_of.isoformat(), "status": "available", "sessions": sessions}
    _remember(as_of, result)
    return result
