#!/usr/bin/env python3
"""
One-off: add SPCX (Space Exploration Technologies Corp.) to the universe.
Inserts into `stocks`, loads 1y prices into `stock_prices`, then calculates metrics.
Mirrors the flow in expand_universe.py + calculate_metrics_for_new_symbols.py.
"""
import asyncio
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.data.ingestors.metrics_calculator import MetricsCalculator
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
SYMBOL = "SPCX"
PERIOD = "1y"


async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    t = yf.Ticker(SYMBOL)
    info = {}
    try:
        info = t.info or {}
    except Exception as e:
        logger.warning(f"Could not fetch info: {e}")

    name = info.get("longName") or info.get("shortName") or SYMBOL
    sector = info.get("sector")
    industry = info.get("industry")
    market_cap = info.get("marketCap")

    async with async_session() as db:
        await db.execute(
            text("""
                INSERT INTO stocks (symbol, name, sector, industry, market_cap, is_active, is_adr)
                VALUES (:s, :name, :sector, :industry, :mcap, true, false)
                ON CONFLICT (symbol) DO UPDATE
                SET name = EXCLUDED.name,
                    sector = COALESCE(EXCLUDED.sector, stocks.sector),
                    industry = COALESCE(EXCLUDED.industry, stocks.industry),
                    market_cap = COALESCE(EXCLUDED.market_cap, stocks.market_cap),
                    is_active = true
            """),
            {"s": SYMBOL, "name": name, "sector": sector, "industry": industry, "mcap": market_cap},
        )
        await db.commit()
        logger.info(f"Inserted/updated stock: {SYMBOL} | {name} | sector={sector} | industry={industry} | mcap={market_cap}")

        # Prices
        hist = t.history(period=PERIOD, auto_adjust=True)
        hist = hist.dropna(subset=["Close"])
        rows = [
            {
                "symbol": SYMBOL,
                "date": d.date(),
                "open": float(r["Open"]) if pd.notna(r["Open"]) else None,
                "high": float(r["High"]) if pd.notna(r["High"]) else None,
                "low": float(r["Low"]) if pd.notna(r["Low"]) else None,
                "close": float(r["Close"]) if pd.notna(r["Close"]) else None,
                "volume": int(r["Volume"]) if pd.notna(r["Volume"]) else None,
            }
            for d, r in hist.iterrows()
        ]
        if rows:
            await db.execute(
                text("""
                    INSERT INTO stock_prices (symbol, date, open, high, low, close, volume)
                    VALUES (:symbol,:date,:open,:high,:low,:close,:volume)
                    ON CONFLICT (symbol, date) DO NOTHING
                """),
                rows,
            )
            await db.commit()
        logger.info(f"Loaded {len(rows)} price rows for {SYMBOL}")

        # Metrics
        calculator = MetricsCalculator(db)
        await calculator.calculate_metrics_for_symbol(SYMBOL)
        logger.info(f"Metrics calculated for {SYMBOL}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
