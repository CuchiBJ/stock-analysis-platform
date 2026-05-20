#!/usr/bin/env python3
"""
Script to calculate metrics for symbols that have prices but no metrics
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.stock import Stock, StockMetrics, StockPrice
from app.data.ingestors.metrics_calculator import MetricsCalculator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@stock-analysis-db:5432/stock_analysis"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get symbols with prices but no metrics
        query = (
            select(Stock.symbol)
            .outerjoin(StockMetrics, Stock.symbol == StockMetrics.symbol)
            .join(StockPrice, Stock.symbol == StockPrice.symbol)
            .where(StockMetrics.symbol.is_(None))
            .where(Stock.is_active == True)
            .distinct()
        )
        
        result = await db.execute(query)
        symbols = [row[0] for row in result.fetchall()]
        
        logger.info(f"Found {len(symbols)} symbols with prices but no metrics")
        
        calculator = MetricsCalculator(db)
        
        success_count = 0
        failure_count = 0
        
        for i, symbol in enumerate(symbols):
            try:
                logger.info(f"[{i+1}/{len(symbols)}] Calculating metrics for {symbol}...")
                await calculator.calculate_metrics_for_symbol(symbol.upper())
                logger.info(f"  Metrics calculated for {symbol}")
                success_count += 1
                    
            except Exception as e:
                logger.error(f"  Failed to calculate metrics for {symbol}: {e}")
                failure_count += 1
                continue
        
        logger.info(f"Completed: {success_count} successful, {failure_count} failed")

if __name__ == "__main__":
    asyncio.run(main())
