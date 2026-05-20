#!/usr/bin/env python3
"""
Standalone metrics calculation — runs outside uvicorn so --reload doesn't kill it.
Only processes stocks that have prices but no metrics yet.
"""
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


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Only stocks with prices but without metrics
        result = await db.execute(text("""
            SELECT DISTINCT sp.symbol
            FROM stock_prices sp
            LEFT JOIN stock_metrics sm ON sp.symbol = sm.symbol
            WHERE sm.symbol IS NULL
            ORDER BY sp.symbol
        """))
        symbols = [row[0] for row in result.fetchall()]

    logger.info(f"Stocks needing metrics: {len(symbols)}")

    ok = fail = 0
    BATCH = 100  # commit and refresh session every N symbols
    for batch_start in range(0, len(symbols), BATCH):
        batch = symbols[batch_start:batch_start + BATCH]
        async with async_session() as db:
            for i, symbol in enumerate(batch, start=batch_start):
                try:
                    calc = MetricsCalculator(db)
                    await calc.calculate_metrics_for_symbol(symbol)
                    ok += 1
                except Exception as e:
                    logger.error(f"  {symbol}: {e}")
                    fail += 1
        if ok % 500 == 0 or batch_start + BATCH >= len(symbols):
            logger.info(f"[{batch_start + len(batch)}/{len(symbols)}] {ok} ok, {fail} failed")

    await engine.dispose()
    logger.info(f"Done: {ok} ok, {fail} failed")


if __name__ == "__main__":
    asyncio.run(main())
