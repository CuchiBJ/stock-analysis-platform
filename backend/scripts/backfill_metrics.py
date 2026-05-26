#!/usr/bin/env python3
"""
Historical metrics backfill.

Calculates metrics for the last N trading dates so that TransitionEngine
can compare today vs yesterday and produce real (non-stable) transitions.

Only processes the quality universe (stocks that already have recent metrics).
Skips (symbol, date) pairs that already exist.

Usage:
    python scripts/backfill_metrics.py           # last 20 trading days
    python scripts/backfill_metrics.py --days 10 # last 10 trading days
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.data.ingestors.metrics_calculator import MetricsCalculator
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"


async def get_trading_dates(db: AsyncSession, n: int) -> list[str]:
    """Return the last N distinct trading dates present in stock_prices."""
    result = await db.execute(text("""
        SELECT DISTINCT date
        FROM stock_prices
        ORDER BY date DESC
        LIMIT :n
    """), {"n": n + 5})  # fetch a few extra in case of thin days
    dates = [row[0] for row in result.fetchall()]
    return sorted(dates)[-n:]  # keep last N in chronological order


async def get_quality_symbols(db: AsyncSession) -> list[str]:
    """Symbols in the quality universe (have recent metrics with quality filters)."""
    result = await db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (symbol) symbol, avg_volume_10d, current_price, adr_percent
            FROM stock_metrics
            ORDER BY symbol, date DESC
        )
        SELECT symbol
        FROM latest
        WHERE avg_volume_10d >= 500000
          AND current_price  >= 5.0
          AND adr_percent    >= 2.0
        ORDER BY symbol
    """))
    return [row[0] for row in result.fetchall()]


async def get_existing_pairs(db: AsyncSession, dates: list[str]) -> set[tuple]:
    """Return set of (symbol, date) pairs that already have metrics."""
    if not dates:
        return set()
    result = await db.execute(text("""
        SELECT symbol, date
        FROM stock_metrics
        WHERE date = ANY(:dates)
    """), {"dates": dates})
    return {(row[0], row[1]) for row in result.fetchall()}


async def backfill(n_days: int) -> None:
    engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        dates   = await get_trading_dates(db, n_days)
        symbols = await get_quality_symbols(db)
        existing = await get_existing_pairs(db, dates)

    logger.info(f"Trading dates to backfill: {dates[0]} → {dates[-1]} ({len(dates)} days)")
    logger.info(f"Quality universe: {len(symbols)} symbols")
    logger.info(f"Already computed: {len(existing)} (symbol, date) pairs — will skip")

    total_needed = len(dates) * len(symbols) - len(existing)
    logger.info(f"Pairs to compute: ~{total_needed}")

    ok = skip = fail = 0
    BATCH = 50  # commit every N symbols per date

    for date in dates:
        symbols_for_date = [s for s in symbols if (s, date) not in existing]
        if not symbols_for_date:
            logger.info(f"{date}: all {len(symbols)} already computed, skipping")
            continue

        logger.info(f"{date}: computing {len(symbols_for_date)} symbols …")

        for batch_start in range(0, len(symbols_for_date), BATCH):
            batch = symbols_for_date[batch_start:batch_start + BATCH]
            async with async_session() as db:
                for symbol in batch:
                    try:
                        calc = MetricsCalculator(db)
                        result = await calc.calculate_metrics_for_symbol(
                            symbol, days=200, as_of_date=date
                        )
                        if result is not None:
                            ok += 1
                        else:
                            skip += 1
                    except Exception as e:
                        logger.warning(f"  {symbol} @ {date}: {e}")
                        fail += 1

        logger.info(
            f"  {date} done — running totals: {ok} ok, {skip} skipped (no data), {fail} errors"
        )

    await engine.dispose()
    logger.info(f"Backfill complete: {ok} computed, {skip} skipped, {fail} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=20, help="Number of trading days to backfill")
    args = parser.parse_args()
    asyncio.run(backfill(args.days))
