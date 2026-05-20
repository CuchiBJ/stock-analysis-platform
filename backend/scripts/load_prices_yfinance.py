#!/usr/bin/env python3
"""Load historical prices for all stocks using yfinance (bulk download)."""
import asyncio
import sys
from pathlib import Path
import yfinance as yf
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from app.models.stock import Stock, StockPrice
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
BATCH_SIZE = 50  # tickers per yfinance bulk download
PERIOD = "1y"


async def get_symbols_without_prices(db: AsyncSession) -> list[str]:
    result = await db.execute(
        text("""
            SELECT s.symbol FROM stocks s
            LEFT JOIN (SELECT DISTINCT symbol FROM stock_prices) p ON s.symbol = p.symbol
            WHERE p.symbol IS NULL
            ORDER BY s.symbol
        """)
    )
    return [row[0] for row in result.fetchall()]


async def insert_prices(db: AsyncSession, symbol: str, hist: pd.DataFrame) -> int:
    count = 0
    for date, row in hist.iterrows():
        date_str = date.strftime("%Y-%m-%d")
        await db.execute(
            text("""
                INSERT INTO stock_prices (symbol, date, open, high, low, close, volume)
                VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
                ON CONFLICT (symbol, date) DO NOTHING
            """),
            {
                "symbol": symbol,
                "date": date_str,
                "open": float(row["Open"]) if pd.notna(row["Open"]) else None,
                "high": float(row["High"]) if pd.notna(row["High"]) else None,
                "low": float(row["Low"]) if pd.notna(row["Low"]) else None,
                "close": float(row["Close"]) if pd.notna(row["Close"]) else None,
                "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else None,
            }
        )
        count += 1
    return count


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        symbols = await get_symbols_without_prices(db)
        logger.info(f"Symbols without prices: {len(symbols)}")

        total_success = 0
        total_fail = 0

        for i in range(0, len(symbols), BATCH_SIZE):
            batch = symbols[i:i + BATCH_SIZE]
            logger.info(f"Downloading batch {i//BATCH_SIZE + 1}: {batch[0]}..{batch[-1]} ({len(batch)} tickers)")

            try:
                data = yf.download(batch, period=PERIOD, auto_adjust=True, progress=False, threads=True)
            except Exception as e:
                logger.error(f"Batch download failed: {e}")
                total_fail += len(batch)
                continue

            if data.empty:
                logger.warning("Empty data for batch, skipping")
                total_fail += len(batch)
                continue

            # yfinance returns MultiIndex columns when >1 ticker
            for symbol in batch:
                try:
                    if len(batch) == 1:
                        hist = data
                    else:
                        if symbol not in data.columns.get_level_values(1):
                            logger.warning(f"  {symbol}: no data")
                            total_fail += 1
                            continue
                        hist = data.xs(symbol, axis=1, level=1)

                    hist = hist.dropna(subset=["Close"])
                    if hist.empty:
                        logger.warning(f"  {symbol}: empty after dropna")
                        total_fail += 1
                        continue

                    count = await insert_prices(db, symbol, hist)
                    await db.commit()
                    logger.info(f"  {symbol}: {count} records")
                    total_success += 1

                except Exception as e:
                    logger.error(f"  {symbol}: failed - {e}")
                    await db.rollback()
                    total_fail += 1

        logger.info(f"Done: {total_success} ok, {total_fail} failed")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
