#!/usr/bin/env python3
"""
Enrich sectors ONLY for quality universe stocks (liquid, relevant).
Targets stocks with metrics that pass institutional quality filters.
"""
import asyncio
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
WORKERS = 10   # conservative to avoid Yahoo rate limits
BATCH_LOG = 100


def fetch_info(symbol: str):
    try:
        time.sleep(0.05)  # 50ms throttle per worker
        info = yf.Ticker(symbol).info
        sector = info.get("sector")
        if not sector:
            return None
        return {
            "symbol":     symbol,
            "sector":     sector,
            "industry":   info.get("industry"),
            "market_cap": info.get("marketCap"),
            "name":       info.get("longName") or info.get("shortName"),
        }
    except Exception:
        return None


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Only quality universe stocks without sector
        result = await db.execute(text("""
            SELECT sm.symbol
            FROM stock_metrics sm
            JOIN stocks s ON s.symbol = sm.symbol
            WHERE s.sector IS NULL
              AND sm.avg_volume_10d >= 500000
              AND sm.current_price >= 5.0
              AND sm.adr_percent >= 2.0
            ORDER BY sm.avg_volume_10d DESC
        """))
        symbols = [row[0] for row in result.fetchall()]

    logger.info(f"Quality stocks needing sectors: {len(symbols)} ({WORKERS} workers)")

    ok = fail = 0
    results = []

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_info, s): s for s in symbols}
        for i, future in enumerate(as_completed(futures)):
            info = future.result()
            if info:
                results.append(info)
                ok += 1
            else:
                fail += 1
            if (i + 1) % BATCH_LOG == 0:
                logger.info(f"  [{i+1}/{len(symbols)}] {ok} with sector, {fail} not found")

    logger.info(f"Fetched {ok} sectors. Writing to DB...")

    async with async_session() as db:
        for item in results:
            await db.execute(text("""
                UPDATE stocks SET
                    sector     = :sector,
                    industry   = :industry,
                    market_cap = :market_cap,
                    name       = COALESCE(NULLIF(:name, ''), name)
                WHERE symbol = :symbol
            """), item)
        await db.commit()

    await engine.dispose()
    logger.info(f"Done: {ok} sectors updated, {fail} not found in Yahoo.")


if __name__ == "__main__":
    asyncio.run(main())
