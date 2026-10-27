"""OHLC-based breadth comparisons for one resolved Market Context session."""
from __future__ import annotations

import math
from decimal import Decimal
from datetime import date
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock, StockMetrics, StockPrice
from app.services.universe_filters import QUALITY_FILTERS

EXTREME_LOOKBACK_SESSIONS = 1


def _valid_price(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(number) and number > 0


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def evaluate_session_extreme(
    current_high: Any, current_low: Any, prior_pairs: list[tuple[Any, Any]],
) -> tuple[bool, bool, bool]:
    """Return (eligible, new_high, new_low) for the immediately preceding session."""
    if len(prior_pairs) != EXTREME_LOOKBACK_SESSIONS:
        return False, False, False
    if (not _valid_price(current_high) or not _valid_price(current_low)
            or _decimal(current_high) < _decimal(current_low)):
        return False, False, False
    for high, low in prior_pairs:
        if (not _valid_price(high) or not _valid_price(low)
                or _decimal(high) < _decimal(low)):
            return False, False, False
    high_event = _decimal(current_high) > max(_decimal(high) for high, _ in prior_pairs)
    low_event = _decimal(current_low) < min(_decimal(low) for _, low in prior_pairs)
    return True, high_event, low_event


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
    db: AsyncSession, as_of: date, *, include_constituents: bool = False,
) -> dict[str, Any]:
    """Calculate OHLC breadth using filtered symbols and available market sessions.

    Each query is set-based. Coverage requires valid highs and lows for the
    current and immediately preceding stored SPY session. Orphan rows and
    older symbol prices cannot replace that reference session.
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
        .limit(EXTREME_LOOKBACK_SESSIONS)
    )).scalars().all()

    session_highs: dict[str, list[Any]] = {}
    session_lows: dict[str, list[Any]] = {}
    if len(prior_dates) == EXTREME_LOOKBACK_SESSIONS:
        history_rows = (await db.execute(
            select(StockPrice.symbol, StockPrice.date, StockPrice.high, StockPrice.low)
            .join(symbol_query, symbol_query.c.symbol == StockPrice.symbol)
            .where(StockPrice.date.in_(prior_dates))
        )).all()
        history: dict[str, dict[Any, tuple[Any, Any]]] = {}
        for row in history_rows:
            history.setdefault(row.symbol, {})[row.date] = (row.high, row.low)
        for symbol, by_date in history.items():
            if len(by_date) != EXTREME_LOOKBACK_SESSIONS or any(day not in by_date for day in prior_dates):
                continue
            session_highs[symbol] = [by_date[day][0] for day in prior_dates]
            session_lows[symbol] = [by_date[day][1] for day in prior_dates]

    high_symbols: list[str] = []
    low_symbols: list[str] = []
    session_eligible_symbols: set[str] = set()
    session_up = session_down = 0
    session_eligible = 0
    for symbol, row in current.items():
        prior_highs = session_highs.get(symbol)
        prior_lows = session_lows.get(symbol)
        if prior_highs is None or prior_lows is None:
            continue
        eligible, high_event, low_event = evaluate_session_extreme(
            row.high, row.low, list(zip(prior_highs, prior_lows)),
        )
        if not eligible:
            continue
        session_eligible += 1
        if include_constituents:
            session_eligible_symbols.add(symbol)
        if high_event:
            session_up += 1
            if include_constituents:
                high_symbols.append(symbol)
        if low_event:
            session_down += 1
            if include_constituents:
                low_symbols.append(symbol)

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

    result = {
        "date": as_of.isoformat(),
        "new_session_highs_vs_lows": _measure(session_up, session_down, session_eligible, universe_size),
        "up_from_open_vs_down": _measure(opening_up, opening_down, opening_eligible, universe_size),
        "up_4pct_vs_down_4pct": _measure(move_up, move_down, move_eligible, universe_size),
    }

    if include_constituents:
        metadata = {}
        if universe_symbols:
            rows = (await db.execute(
                select(Stock.symbol, Stock.name, Stock.sector).where(Stock.symbol.in_(universe_symbols))
            )).all()
            metadata = {row.symbol: row for row in rows}
        sectors: dict[str, dict[str, Any]] = {}
        sector_by_symbol: dict[str, str] = {}
        for symbol in sorted(universe_symbols):
            stock = metadata.get(symbol)
            sector = (stock.sector or "").strip() if stock else ""
            sector = sector or "Sin sector"
            sector_by_symbol[symbol] = sector
            group = sectors.setdefault(sector, {
                "sector": sector, "highs": [], "lows": [],
                "eligible_symbols": 0, "excluded_symbols": 0,
            })
            if symbol in session_eligible_symbols:
                group["eligible_symbols"] += 1
            else:
                group["excluded_symbols"] += 1
        for side, members in (("highs", high_symbols), ("lows", low_symbols)):
            for symbol in sorted(members):
                stock = metadata.get(symbol)
                group = sectors[sector_by_symbol[symbol]]
                group[side].append({"symbol": symbol, "name": stock.name if stock else symbol})
        result["new_session_highs_vs_lows"]["sectors"] = [sectors[key] for key in sorted(sectors)]
    return result
