#!/usr/bin/env python3
"""
Script to fix metrics gap by ingesting historical prices for symbols without metrics
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from app.data.ingestors.price_ingestor import PriceIngestor
from app.models.stock import Stock, StockMetrics
import logging

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
            .outerjoin(StockMetrics, Stock.symbol == StockMetrics.symbol)
            .where(StockMetrics.symbol.is_(None))
            .where(Stock.is_active == True)
        )
        
        result = await db.execute(query)
        symbols = [row[0] for row in result.fetchall()]
        
        logger.info(f"Found {len(symbols)} symbols without metrics")
        
        ingestor = PriceIngestor(db)
        
        success_count = 0
        failure_count = 0
        
        # Process one symbol at a time to avoid client closure issues
        for i, symbol in enumerate(symbols):
            try:
                logger.info(f"[{i+1}/{len(symbols)}] Ingesting historical prices for {symbol}...")
                
                # Create new ingestor for each symbol
                ingestor = PriceIngestor(db)
                count = await ingestor.ingest_historical_prices(symbol, days=365)
                logger.info(f"  Ingested {count} price records for {symbol}")
                success_count += 1
                
                # Add delay to avoid rate limiting
                await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"  Failed to ingest prices for {symbol}: {e}")
                failure_count += 1
                continue
        
        logger.info(f"Completed: {success_count} successful, {failure_count} failed")

if __name__ == "__main__":
    asyncio.run(main())
