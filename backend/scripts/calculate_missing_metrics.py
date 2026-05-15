#!/usr/bin/env python3
"""Calculate metrics for stocks with prices but no metrics"""
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
    # Database setup
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        calculator = MetricsCalculator(db)
        
        # Get symbols that have prices but no metrics
        result = await db.execute(
            text("""
                SELECT DISTINCT sp.symbol 
                FROM stock_prices sp 
                LEFT JOIN stock_metrics sm ON sp.symbol = sm.symbol 
                WHERE sm.symbol IS NULL
                LIMIT 1000
            """)
        )
        symbols = [row[0] for row in result]
        
        logger.info(f"Found {len(symbols)} symbols with prices but no metrics")
        
        count = 0
        for i, symbol in enumerate(symbols):
            try:
                await calculator.calculate_metrics_for_symbol(symbol, days=200)
                count += 1
                logger.info(f"[{i+1}/{len(symbols)}] Calculated metrics for {symbol}")
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Error calculating metrics for {symbol}: {e}")
        
        logger.info(f"Metrics calculation complete: {count} symbols")

if __name__ == "__main__":
    asyncio.run(main())
