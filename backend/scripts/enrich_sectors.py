#!/usr/bin/env python3
"""
Enrich stocks with sector/industry/market_cap from Yahoo Finance.
Uses ThreadPoolExecutor for parallel fetching (~10 min for 7k stocks).
"""
import asyncio
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
WORKERS = 30  # concurrent yfinance requests


def fetch_info(symbol: str):
    try:
        info = yf.Ticker(symbol).info
        sector = info.get("sector")
        if not sector:
            return None
        return {
            "symbol": symbol,
            "sector": sector,
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "name": info.get("longName") or info.get("shortName"),
        }
    except Exception:
        return None


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(text(
            "SELECT symbol FROM stocks WHERE sector IS NULL ORDER BY symbol"
        ))
        symbols = [row[0] for row in result.fetchall()]

    logger.info(f"Fetching sectors for {len(symbols)} stocks ({WORKERS} workers)...")

    ok = fail = 0
    results = []

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(fetch_info, s): s for s in symbols}
        for i, future in enumerate(as_completed(futures)):
            info = future.result()
            if info:
                results.append(info)
                ok += 1
            else:
                fail += 1

            if (i + 1) % 500 == 0:
                logger.info(f"  [{i+1}/{len(symbols)}] {ok} ok, {fail} no sector")

    logger.info(f"Fetched {ok} sectors. Writing to DB...")

    # Bulk update
    async with async_session() as db:
        for item in results:
            await db.execute(text("""
                UPDATE stocks SET
                    sector = :sector,
                    industry = :industry,
                    market_cap = :market_cap,
                    name = COALESCE(NULLIF(:name, ''), name)
                WHERE symbol = :symbol
            """), item)
        await db.commit()

    await engine.dispose()
    logger.info(f"Done: {ok} sectors updated, {fail} stocks without sector data.")


if __name__ == "__main__":
    asyncio.run(main())
