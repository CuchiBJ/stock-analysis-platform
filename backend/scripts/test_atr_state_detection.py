#!/usr/bin/env python3
"""
Script to test ATR-aware state detection
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.stock import StockMetrics
from app.services.setup_lifecycle_engine import SetupLifecycleEngine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@stock-analysis-db:5432/stock_analysis"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        engine_obj = SetupLifecycleEngine(db)
        
        # Test with different volatility stocks
        symbols = ["AAOI", "MRVL", "LSCC", "EGY"]
        
        for symbol in symbols:
            try:
                logger.info(f"Testing {symbol}...")
                
                # Get latest metrics
                result = await db.execute(
                    select(StockMetrics).where(StockMetrics.symbol == symbol.upper())
                    .order_by(StockMetrics.date.desc())
                    .limit(1)
                )
                metrics = result.scalar_one_or_none()
                
                if metrics:
                    # Compare old vs new state detection
                    old_state = engine_obj.detect_current_state(metrics)
                    new_state = engine_obj.detect_current_state_atr(metrics)
                    
                    logger.info(f"  {symbol}:")
                    logger.info(f"    Old state (percent-based): {old_state.value}")
                    logger.info(f"    New state (ATR-normalized): {new_state.value}")
                    logger.info(f"    distance_to_ema21: {metrics.distance_to_ema21:.2f}%")
                    logger.info(f"    distance_to_ema21_atr: {metrics.distance_to_ema21_atr:.2f} ATRs")
                    logger.info(f"    ATR %: {metrics.atr_percent:.2f}%")
                else:
                    logger.error(f"No metrics found for {symbol}")
            except Exception as e:
                logger.error(f"Error for {symbol}: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
