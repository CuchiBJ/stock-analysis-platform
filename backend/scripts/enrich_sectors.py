#!/usr/bin/env python3
"""
Enrich stocks with sector/industry/market_cap from Yahoo Finance.

Modes:
  --all      All stocks without sector (default, 30 workers)
  --quality  Only quality-universe stocks (vol>=500K, price>=5, ADR>=2), 10 workers

Uses ThreadPoolExecutor + batch UPDATE for performance.
"""
import argparse
import asyncio
import sys
import time
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

_ALL_QUERY = "SELECT symbol FROM stocks WHERE sector IS NULL ORDER BY symbol"
_QUALITY_QUERY = """
    SELECT sm.symbol
    FROM stock_metrics sm
    JOIN stocks s ON s.symbol = sm.symbol
    WHERE s.sector IS NULL
      AND sm.avg_volume_10d >= 500000
      AND sm.current_price  >= 5.0
      AND sm.adr_percent    >= 2.0
    ORDER BY sm.avg_volume_10d DESC
"""


def fetch_info(args: tuple):
    symbol, throttle_ms = args
    if throttle_ms:
        time.sleep(throttle_ms / 1000)
    try:
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


async def run(query: str, workers: int, throttle_ms: int, batch_log: int):
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        result = await db.execute(text(query))
        symbols = [row[0] for row in result.fetchall()]

    logger.info(f"Fetching sectors for {len(symbols)} stocks ({workers} workers)...")

    ok = fail = 0
    results = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_info, (s, throttle_ms)): s for s in symbols}
        for i, future in enumerate(as_completed(futures)):
            info = future.result()
            if info:
                results.append(info)
                ok += 1
            else:
                fail += 1
            if (i + 1) % batch_log == 0:
                logger.info(f"  [{i+1}/{len(symbols)}] {ok} with sector, {fail} not found")

    if not results:
        logger.info("No sectors fetched.")
        return

    logger.info(f"Fetched {ok} sectors. Writing to DB...")

    # executemany — one round-trip for all rows via UPSERT
    async with async_session() as db:
        await db.execute(
            text("""
                INSERT INTO stocks (symbol, sector, industry, market_cap, name)
                VALUES (:symbol, :sector, :industry, :market_cap, :name)
                ON CONFLICT (symbol) DO UPDATE SET
                    sector     = EXCLUDED.sector,
                    industry   = EXCLUDED.industry,
                    market_cap = EXCLUDED.market_cap,
                    name       = COALESCE(EXCLUDED.name, stocks.name)
            """),
            results,
        )
        await db.commit()

    await engine.dispose()
    logger.info(f"Done: {ok} sectors updated, {fail} not found in Yahoo.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality", action="store_true",
                        help="Only enrich quality-universe stocks")
    args = parser.parse_args()

    if args.quality:
        asyncio.run(run(_QUALITY_QUERY, workers=10, throttle_ms=50, batch_log=100))
    else:
        asyncio.run(run(_ALL_QUERY, workers=30, throttle_ms=0, batch_log=500))
