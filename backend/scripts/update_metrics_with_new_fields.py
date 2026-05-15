#!/usr/bin/env python3
"""Update existing metrics with new fields (EMA9/21, weekly structure, pullback quality)"""
import asyncio
import sys
sys.path.insert(0, '/home/fernando/repositorios/stock-analysis-platform/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.data.ingestors.metrics_calculator import MetricsCalculator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        calculator = MetricsCalculator(db)
        
        # Get all symbols with existing metrics (to update them with new fields)
        result = await db.execute(
            text("""
                SELECT DISTINCT symbol 
                FROM stock_metrics
                ORDER BY symbol
                LIMIT 1000
            """)
        )
        symbols = [row[0] for row in result]
        
        logger.info(f"Found {len(symbols)} symbols with existing metrics to update")
        
        count = 0
        for i, symbol in enumerate(symbols):
            try:
                await calculator.calculate_metrics_for_symbol(symbol, days=200)
                count += 1
                logger.info(f"[{i+1}/{len(symbols)}] Updated metrics for {symbol}")
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Error updating metrics for {symbol}: {e}")
        
        logger.info(f"Metrics update complete: {count} symbols")

if __name__ == "__main__":
    asyncio.run(main())
