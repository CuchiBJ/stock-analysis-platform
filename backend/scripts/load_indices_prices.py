#!/usr/bin/env python3
"""Load prices for major indices (SPY, QQQ, IWM, DIA)"""
import sys
sys.path.insert(0, '/home/fernando/repositorios/stock-analysis-platform/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
import yfinance as yf
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Database setup
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Major indices ETFs
    index_symbols = ['SPY', 'QQQ', 'IWM', 'DIA']
    
    async with async_session() as db:
        for symbol in index_symbols:
            try:
                # Use Yahoo Finance for historical prices
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1y")
                
                if hist.empty:
                    logger.warning(f"No price data for {symbol}")
                    continue
                
                # Insert prices into database
                for date, row in hist.iterrows():
                    volume = int(row['Volume']) if row['Volume'] < 2147483647 else 2147483647
                    await db.execute(
                        text("""
                            INSERT INTO stock_prices (symbol, date, open, high, low, close, volume)
                            VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
                            ON CONFLICT (symbol, date) DO NOTHING
                        """),
                        {
                            "symbol": symbol,
                            "date": str(date.date()),
                            "open": float(row['Open']),
                            "high": float(row['High']),
                            "low": float(row['Low']),
                            "close": float(row['Close']),
                            "volume": volume
                        }
                    )
                
                await db.commit()
                logger.info(f"Loaded prices for {symbol} ({len(hist)} days)")
                
                # Small delay to avoid rate limits
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error loading prices for {symbol}: {e}")
                await db.rollback()
        
        logger.info(f"Index prices ingestion complete")

if __name__ == "__main__":
    asyncio.run(main())
