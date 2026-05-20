#!/usr/bin/env python3
"""
Script to fix metrics gap using yfinance as alternative to Polygon
"""
import asyncio
import sys
from pathlib import Path
import yfinance as yf

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.stock import Stock, StockPrice
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@stock-analysis-db:5432/stock_analysis"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get symbols without metrics
        query = (
            select(Stock.symbol)
            .outerjoin(StockPrice, Stock.symbol == StockPrice.symbol)
            .where(StockPrice.symbol.is_(None))
            .where(Stock.is_active == False)  # Get the 798 we marked as inactive
        )
        
        result = await db.execute(query)
        symbols = [row[0] for row in result.fetchall()]
        
        logger.info(f"Found {len(symbols)} symbols without prices (marked as inactive)")
        
        success_count = 0
        failure_count = 0
        
        for i, symbol in enumerate(symbols):
            try:
                logger.info(f"[{i+1}/{len(symbols)}] Fetching historical prices for {symbol} using yfinance...")
                
                # Fetch historical data using yfinance
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1y")
                
                if hist.empty:
                    logger.warning(f"  No data found for {symbol}")
                    failure_count += 1
                    continue
                
                # Store prices in database
                count = 0
                prices_to_add = []
                for date, row in hist.iterrows():
                    date_str = date.strftime("%Y-%m-%d")
                    
                    # Check if already exists
                    existing = await db.execute(
                        select(StockPrice).where(
                            StockPrice.symbol == symbol,
                            StockPrice.date == date_str
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue
                    
                    price = StockPrice(
                        symbol=symbol,
                        date=date_str,
                        open=float(row['Open']) if not row['Open'] is None else None,
                        high=float(row['High']) if not row['High'] is None else None,
                        low=float(row['Low']) if not row['Low'] is None else None,
                        close=float(row['Close']) if not row['Close'] is None else None,
                        volume=int(row['Volume']) if not row['Volume'] is None else None
                    )
                    
                    prices_to_add.append(price)
                    count += 1
                
                # Add all prices at once
                for price in prices_to_add:
                    db.add(price)
                
                await db.commit()
                logger.info(f"  Ingested {count} price records for {symbol} using yfinance")
                success_count += 1
                
                # Mark as active if we got data
                if count > 0:
                    await db.execute(
                        select(Stock).where(Stock.symbol == symbol)
                    )
                    stock = result.scalar_one_or_none()
                    if stock:
                        stock.is_active = True
                        await db.commit()
                        logger.info(f"  Marked {symbol} as active")
                
                # Add delay to avoid rate limiting
                await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"  Failed to ingest prices for {symbol}: {e}")
                failure_count += 1
                await db.rollback()
                continue
        
        logger.info(f"Completed: {success_count} successful, {failure_count} failed")

if __name__ == "__main__":
    asyncio.run(main())
