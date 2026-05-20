#!/usr/bin/env python3
"""
Load all NASDAQ + NYSE common stocks and their 1-year price history.
Uses NASDAQ Trader FTP for ticker list, yfinance for prices.
"""
import asyncio
import sys
from pathlib import Path
import requests
import io
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
BATCH_SIZE = 100
PERIOD = "1y"

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


def fetch_tickers() -> list[str]:
    """Fetch all common stocks from NASDAQ + NYSE via SEC EDGAR (no rate limits)."""
    headers = {"User-Agent": "stock-analysis/1.0 contact@example.com"}
    logger.info("Fetching tickers from SEC EDGAR...")

    r = requests.get(SEC_TICKERS_URL, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    fields = data.get("fields", [])
    rows = data.get("data", [])
    df = pd.DataFrame(rows, columns=fields)

    logger.info(f"  Total SEC records: {len(df)}")

    # Keep only NASDAQ and NYSE
    df = df[df["exchange"].isin(["NASDAQ", "NYSE", "NYSE MKT", "NYSE ARCA"])]
    logger.info(f"  NASDAQ + NYSE records: {len(df)}")

    # Clean tickers: alphabetic only, max 5 chars, no duplicates
    clean = []
    seen = set()
    for t in df["ticker"].dropna().tolist():
        t = str(t).strip().upper()
        if t and t not in seen and t.isalpha() and len(t) <= 5:
            clean.append(t)
            seen.add(t)

    logger.info(f"Total unique common stocks: {len(clean)}")
    return clean


async def insert_stocks(db: AsyncSession, tickers: list[str]):
    logger.info(f"Inserting {len(tickers)} tickers into stocks table...")
    for symbol in tickers:
        await db.execute(
            text("""
                INSERT INTO stocks (symbol, name, is_active, is_adr)
                VALUES (:symbol, :symbol, true, false)
                ON CONFLICT (symbol) DO NOTHING
            """),
            {"symbol": symbol}
        )
    await db.commit()
    logger.info("Stocks inserted.")


async def load_prices(db: AsyncSession, tickers: list[str]):
    total = len(tickers)
    success = 0
    fail = 0

    for i in range(0, total, BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(f"Batch {batch_num}/{total_batches}: {batch[0]}..{batch[-1]} ({len(batch)} tickers)")

        try:
            data = yf.download(
                batch, period=PERIOD, auto_adjust=True,
                progress=False, threads=True
            )
        except Exception as e:
            logger.error(f"  Download failed: {e}")
            fail += len(batch)
            continue

        if data.empty:
            logger.warning("  Empty batch")
            fail += len(batch)
            continue

        multi = isinstance(data.columns, pd.MultiIndex)

        for symbol in batch:
            try:
                if multi:
                    if symbol not in data.columns.get_level_values(1):
                        fail += 1
                        continue
                    hist = data.xs(symbol, axis=1, level=1).dropna(subset=["Close"])
                else:
                    hist = data.dropna(subset=["Close"])

                if hist.empty:
                    fail += 1
                    continue

                rows = [
                    {
                        "symbol": symbol,
                        "date": date.strftime("%Y-%m-%d"),
                        "open":   float(row["Open"])   if pd.notna(row["Open"])   else None,
                        "high":   float(row["High"])   if pd.notna(row["High"])   else None,
                        "low":    float(row["Low"])    if pd.notna(row["Low"])    else None,
                        "close":  float(row["Close"])  if pd.notna(row["Close"])  else None,
                        "volume": int(row["Volume"])   if pd.notna(row["Volume"]) else None,
                    }
                    for date, row in hist.iterrows()
                ]

                await db.execute(
                    text("""
                        INSERT INTO stock_prices (symbol, date, open, high, low, close, volume)
                        VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
                        ON CONFLICT (symbol, date) DO NOTHING
                    """),
                    rows
                )
                await db.commit()
                success += 1

            except Exception as e:
                logger.error(f"  {symbol}: {e}")
                await db.rollback()
                fail += 1

        logger.info(f"  Progress: {success} ok, {fail} failed so far")

    logger.info(f"Prices complete: {success} ok, {fail} failed")


async def main():
    tickers = fetch_tickers()

    engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        await insert_stocks(db, tickers)
        await load_prices(db, tickers)

    await engine.dispose()
    logger.info("All done. Run metric calculation next.")


if __name__ == "__main__":
    asyncio.run(main())
