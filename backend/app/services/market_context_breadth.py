"""OHLC-based breadth comparisons for one resolved Market Context session."""
from __future__ import annotations

import math
from decimal import Decimal
from datetime import date
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import StockMetrics, StockPrice
from app.services.universe_filters import QUALITY_FILTERS

ANNUAL_LOOKBACK_SESSIONS = 252


def _valid_price(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _measure(up: int, down: int, eligible: int, universe: int) -> dict[str, int | float | None]:
    events = up + down
    return {
        "up_count": up,
        "down_count": down,
        "eligible_symbols": eligible,
        "excluded_symbols": max(0, universe - eligible),
        "up_ratio": up / events if events else None,
    }


async def calculate_breadth_comparisons(
    db: AsyncSession, as_of: date,
) -> dict[str, Any]:
    """Calculate OHLC breadth using filtered symbols and available market sessions.

    Each query is set-based. Annual coverage requires a valid high and low for
    each of the same 252 SPY market-session dates, so orphan rows cannot create
    phantom sessions or extend the window.
    """
    symbol_query = (
        select(StockMetrics.symbol)
        .where(StockMetrics.date == as_of, *QUALITY_FILTERS)
        .distinct()
        .subquery()
    )
    universe_symbols = set((await db.execute(select(symbol_query.c.symbol))).scalars().all())
    universe_size = len(universe_symbols)

    current_rows = (await db.execute(
        select(StockPrice.symbol, StockPrice.open, StockPrice.high, StockPrice.low, StockPrice.close)
        .join(symbol_query, symbol_query.c.symbol == StockPrice.symbol)
        .where(StockPrice.date == as_of)
    )).all()
    current = {row.symbol: row for row in current_rows}

    prior_dates = (await db.execute(
        select(StockPrice.date)
        .where(StockPrice.symbol == "SPY", StockPrice.date < as_of)
        .distinct()
        .order_by(desc(StockPrice.date))
        .limit(ANNUAL_LOOKBACK_SESSIONS)
    )).scalars().all()

    annual_highs: dict[str, list[Any]] = {}
    annual_lows: dict[str, list[Any]] = {}
    if len(prior_dates) == ANNUAL_LOOKBACK_SESSIONS:
        history_rows = (await db.execute(
            select(StockPrice.symbol, StockPrice.date, StockPrice.high, StockPrice.low)
            .join(symbol_query, symbol_query.c.symbol == StockPrice.symbol)
            .where(StockPrice.date.in_(prior_dates))
        )).all()
        history: dict[str, dict[Any, tuple[Any, Any]]] = {}
        for row in history_rows:
            history.setdefault(row.symbol, {})[row.date] = (row.high, row.low)
        for symbol, by_date in history.items():
            if len(by_date) != ANNUAL_LOOKBACK_SESSIONS or any(
                day not in by_date or not _valid_price(by_date[day][0]) or not _valid_price(by_date[day][1])
                or _decimal(by_date[day][0]) < _decimal(by_date[day][1])
                for day in prior_dates
            ):
                continue
            annual_highs[symbol] = [by_date[day][0] for day in prior_dates]
            annual_lows[symbol] = [by_date[day][1] for day in prior_dates]

    annual_up = annual_down = 0
    annual_eligible = 0
    for symbol, row in current.items():
        prior_highs = annual_highs.get(symbol)
        prior_lows = annual_lows.get(symbol)
        if (prior_highs is None or prior_lows is None or not _valid_price(row.high)
                or not _valid_price(row.low) or _decimal(row.high) < _decimal(row.low)):
            continue
        annual_eligible += 1
        if _decimal(row.high) > max(_decimal(value) for value in prior_highs):
            annual_up += 1
        if _decimal(row.low) < min(_decimal(value) for value in prior_lows):
            annual_down += 1

    opening_up = opening_down = opening_eligible = 0
    for row in current.values():
        if not _valid_price(row.open) or not _valid_price(row.close):
            continue
        opening_eligible += 1
        if _decimal(row.close) > _decimal(row.open):
            opening_up += 1
        elif _decimal(row.close) < _decimal(row.open):
            opening_down += 1

    previous_date = prior_dates[0] if prior_dates else None
    previous_closes: dict[str, Any] = {}
    if previous_date is not None:
        previous_rows = (await db.execute(
            select(StockPrice.symbol, StockPrice.close)
            .join(symbol_query, symbol_query.c.symbol == StockPrice.symbol)
            .where(StockPrice.date == previous_date)
        )).all()
        previous_closes = {row.symbol: row.close for row in previous_rows}

    move_up = move_down = move_eligible = 0
    for symbol, row in current.items():
        previous_close = previous_closes.get(symbol)
        if (not _valid_price(row.close) or not _valid_price(previous_close)):
            continue
        move_eligible += 1
        close, previous = _decimal(row.close), _decimal(previous_close)
        if close >= previous * Decimal("1.04"):
            move_up += 1
        elif close <= previous * Decimal("0.96"):
            move_down += 1

    return {
        "date": as_of.isoformat(),
        "new_52w_highs_vs_lows": _measure(annual_up, annual_down, annual_eligible, universe_size),
        "up_from_open_vs_down": _measure(opening_up, opening_down, opening_eligible, universe_size),
        "up_4pct_vs_down_4pct": _measure(move_up, move_down, move_eligible, universe_size),
    }
