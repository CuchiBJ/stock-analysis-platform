#!/usr/bin/env python3
"""
Script to test contextual setup engine
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
from app.services.contextual_setup_engine import ContextualSetupEngine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@stock-analysis-db:5432/stock_analysis"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        engine_obj = ContextualSetupEngine()
        
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
                    # Calculate contextual readiness score
                    readiness = engine_obj.calculate_readiness_score(metrics)
                    narrative = engine_obj.generate_readiness_narrative(readiness)
                    
                    # Calculate structure-first evaluation
                    structure_eval = engine_obj.evaluate_structure_first(metrics)
                    
                    # Calculate MA contextual analysis
                    ma_analysis = engine_obj.analyze_ma_context(metrics)
                    
                    # Calculate pullback character analysis
                    pullback_analysis = engine_obj.analyze_pullback_character(metrics)
                    
                    logger.info(f"  {symbol}:")
                    logger.info(f"    Total Score: {readiness.total_score:.1f}/100")
                    logger.info(f"    Structure Quality: {readiness.structure_quality:.1f}")
                    logger.info(f"    Volatility Compression: {readiness.volatility_compression:.1f}")
                    logger.info(f"    RS Quality: {readiness.rs_quality:.1f}")
                    logger.info(f"    Pullback Character: {readiness.pullback_character:.1f}")
                    logger.info(f"    MA Context: {readiness.ma_context:.1f}")
                    logger.info(f"    Market Alignment: {readiness.market_alignment:.1f}")
                    logger.info(f"    Narrative: {narrative}")
                    logger.info(f"    Structure Integrity: {structure_eval['structure_integrity']:.1f}/100")
                    logger.info(f"    Is Actionable: {structure_eval['is_actionable']}")
                    logger.info(f"    Structure Rationale: {structure_eval['rationale']}")
                    logger.info(f"    MA Context Score: {ma_analysis['ma_context_score']:.1f}/100")
                    logger.info(f"    MA Narrative: {ma_analysis['narrative']}")
                    logger.info(f"    Pullback Character Score: {pullback_analysis['pullback_character_score']:.1f}/100")
                    logger.info(f"    Pullback Narrative: {pullback_analysis['narrative']}")
                else:
                    logger.error(f"No metrics found for {symbol}")
            except Exception as e:
                logger.error(f"Error for {symbol}: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
