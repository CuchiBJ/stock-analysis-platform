#!/usr/bin/env python3
"""
Script to test ATR calculation for a single symbol
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.stock import StockMetrics
from app.data.ingestors.metrics_calculator import MetricsCalculator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@stock-analysis-db:5432/stock_analysis"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        calculator = MetricsCalculator(db)
        
        # Test with EGY
        symbol = "EGY"
        logger.info(f"Calculating metrics for {symbol}...")
        
        try:
            metrics = await calculator.calculate_metrics_for_symbol(symbol)
            if metrics:
                logger.info(f"ATR: {metrics.atr}")
                logger.info(f"ATR %: {metrics.atr_percent}")
                logger.info(f"Current price: {metrics.current_price}")
            else:
                logger.error(f"Failed to calculate metrics for {symbol}")
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
