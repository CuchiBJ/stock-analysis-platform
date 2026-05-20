#!/usr/bin/env python3
"""
Full Integration Test - Contextual Structure-Aware Scoring System

This script demonstrates the complete integration of:
1. ATR-normalized positioning
2. ATR-aware state detection (SetupLifecycleEngine)
3. Contextual setup scoring (ContextualSetupEngine)
4. Structure-first evaluation
5. MA contextual analysis
6. Pullback character analysis
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
from app.services.contextual_setup_engine import ContextualSetupEngine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@stock-analysis-db:5432/stock_analysis"

async def main():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Initialize engines
        lifecycle_engine = SetupLifecycleEngine(db)
        contextual_engine = ContextualSetupEngine()
        
        # Test with different volatility stocks
        symbols = ["AAOI", "MRVL", "LSCC", "EGY"]
        
        for symbol in symbols:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"TESTING {symbol}")
                logger.info(f"{'='*60}")
                
                # Get latest metrics
                result = await db.execute(
                    select(StockMetrics).where(StockMetrics.symbol == symbol.upper())
                    .order_by(StockMetrics.date.desc())
                    .limit(1)
                )
                metrics = result.scalar_one_or_none()
                
                if metrics:
                    # 1. ATR-normalized positioning
                    logger.info(f"\n--- ATR-NORMALIZED POSITIONING ---")
                    logger.info(f"ATR: {metrics.atr:.2f}")
                    logger.info(f"ATR %: {metrics.atr_percent:.2f}%")
                    logger.info(f"Price: ${metrics.current_price:.2f}")
                    logger.info(f"distance_to_ema21: {metrics.distance_to_ema21:.2f}%")
                    logger.info(f"distance_to_ema21_atr: {metrics.distance_to_ema21_atr:.2f} ATRs")
                    logger.info(f"distance_to_ema50: {metrics.distance_to_ema50:.2f}%")
                    logger.info(f"distance_to_ema50_atr: {metrics.distance_to_ema50_atr:.2f} ATRs")
                    
                    # 2. ATR-aware state detection
                    logger.info(f"\n--- ATR-AWARE STATE DETECTION ---")
                    old_state = lifecycle_engine.detect_current_state(metrics)
                    new_state = lifecycle_engine.detect_current_state_atr(metrics)
                    logger.info(f"Old state (percent-based): {old_state.value}")
                    logger.info(f"New state (ATR-normalized): {new_state.value}")
                    
                    # 3. Contextual setup scoring
                    logger.info(f"\n--- CONTEXTUAL SETUP SCORING ---")
                    readiness = contextual_engine.calculate_readiness_score(metrics)
                    logger.info(f"Total Score: {readiness.total_score:.1f}/100")
                    logger.info(f"  Structure Quality: {readiness.structure_quality:.1f}")
                    logger.info(f"  Volatility Compression: {readiness.volatility_compression:.1f}")
                    logger.info(f"  RS Quality: {readiness.rs_quality:.1f}")
                    logger.info(f"  Pullback Character: {readiness.pullback_character:.1f}")
                    logger.info(f"  MA Context: {readiness.ma_context:.1f}")
                    logger.info(f"  Market Alignment: {readiness.market_alignment:.1f}")
                    logger.info(f"Narrative: {contextual_engine.generate_readiness_narrative(readiness)}")
                    
                    # 4. Structure-first evaluation
                    logger.info(f"\n--- STRUCTURE-FIRST EVALUATION ---")
                    structure_eval = contextual_engine.evaluate_structure_first(metrics)
                    logger.info(f"Structure Integrity: {structure_eval['structure_integrity']:.1f}/100")
                    logger.info(f"Is Actionable: {structure_eval['is_actionable']}")
                    logger.info(f"Rationale: {structure_eval['rationale']}")
                    
                    # 5. MA contextual analysis
                    logger.info(f"\n--- MA CONTEXTUAL ANALYSIS ---")
                    ma_analysis = contextual_engine.analyze_ma_context(metrics)
                    logger.info(f"MA Context Score: {ma_analysis['ma_context_score']:.1f}/100")
                    logger.info(f"  EMA Slope: {ma_analysis['ema_slope']['score']:.1f}")
                    logger.info(f"  MA Stacking: {ma_analysis['ma_stacking']['score']:.1f}")
                    logger.info(f"  MA Compression: {ma_analysis['ma_compression']['score']:.1f}")
                    logger.info(f"  MA Expansion: {ma_analysis['ma_expansion']['score']:.1f}")
                    logger.info(f"  Slope Acceleration: {ma_analysis['slope_acceleration']['score']:.1f}")
                    logger.info(f"Narrative: {ma_analysis['narrative']}")
                    
                    # 6. Pullback character analysis
                    logger.info(f"\n--- PULLBACK CHARACTER ANALYSIS ---")
                    pullback_analysis = contextual_engine.analyze_pullback_character(metrics)
                    logger.info(f"Pullback Character Score: {pullback_analysis['pullback_character_score']:.1f}/100")
                    logger.info(f"  Orderliness: {pullback_analysis['orderliness']['score']:.1f}")
                    logger.info(f"  Volume Dry-up: {pullback_analysis['volume_dryup']['score']:.1f}")
                    logger.info(f"  Spread Tightening: {pullback_analysis['spread_tightening']['score']:.1f}")
                    logger.info(f"  Close Quality: {pullback_analysis['close_quality']['score']:.1f}")
                    logger.info(f"  Volatility Retracement: {pullback_analysis['volatility_retracement']['score']:.1f}")
                    logger.info(f"  Support Reaction: {pullback_analysis['support_reaction']['score']:.1f}")
                    logger.info(f"Narrative: {pullback_analysis['narrative']}")
                    
                    # Summary
                    logger.info(f"\n--- SUMMARY FOR {symbol} ---")
                    logger.info(f"ATR-Normalized Positioning: {'✓' if metrics.distance_to_ema21_atr is not None else '✗'}")
                    logger.info(f"ATR-Aware State Detection: {'✓' if new_state else '✗'}")
                    logger.info(f"Contextual Setup Scoring: {'✓' if readiness.total_score > 0 else '✗'}")
                    logger.info(f"Structure-First Evaluation: {'✓' if structure_eval['structure_integrity'] > 0 else '✗'}")
                    logger.info(f"MA Contextual Analysis: {'✓' if ma_analysis['ma_context_score'] > 0 else '✗'}")
                    logger.info(f"Pullback Character Analysis: {'✓' if pullback_analysis['pullback_character_score'] > 0 else '✗'}")
                    
                else:
                    logger.error(f"No metrics found for {symbol}")
            except Exception as e:
                logger.error(f"Error for {symbol}: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
