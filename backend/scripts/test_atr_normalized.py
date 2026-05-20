#!/usr/bin/env python3
"""
Script to test ATR-normalized positioning calculation
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
        
        # Test with different volatility stocks
        symbols = ["AAOI", "MRVL", "LSCC", "EGY"]
        
        for symbol in symbols:
            try:
                logger.info(f"Calculating metrics for {symbol}...")
                metrics = await calculator.calculate_metrics_for_symbol(symbol)
                if metrics:
                    logger.info(f"  {symbol}:")
                    logger.info(f"    ATR: {metrics.atr:.2f}")
                    logger.info(f"    ATR %: {metrics.atr_percent:.2f}%")
                    logger.info(f"    Price: {metrics.current_price:.2f}")
                    logger.info(f"    distance_to_ema21: {metrics.distance_to_ema21:.2f}%")
                    logger.info(f"    distance_to_ema21_atr: {metrics.distance_to_ema21_atr:.2f} ATRs")
                    logger.info(f"    distance_to_ema50: {metrics.distance_to_ema50:.2f}%")
                    logger.info(f"    distance_to_ema50_atr: {metrics.distance_to_ema50_atr:.2f} ATRs")
                else:
                    logger.error(f"Failed to calculate metrics for {symbol}")
            except Exception as e:
                logger.error(f"Error for {symbol}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
