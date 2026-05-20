"""
Test Universe Engine with real data

This script tests the Universe Engine components with real data from Polygon.
"""

import asyncio
import logging
import os
from datetime import datetime

from app.universe.universe_engine import get_universe_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_universe_engine():
    """Test Universe Engine with real data"""
    logger.info("Starting Universe Engine test")
    
    # Get Polygon API key from environment
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY environment variable not set")
        return
    
    try:
        # Initialize Universe Engine
        logger.info("Initializing Universe Engine")
        universe_engine = get_universe_engine(polygon_api_key)
        
        # Test identity manager
        logger.info("Testing Identity Manager")
        identity = universe_engine.identity_manager.create_identity(
            symbol="TEST",
            company_name="Test Company",
            primary_exchange="NASDAQ",
            asset_type="common_stock"
        )
        logger.info(f"Created identity: {identity.internal_id}")
        
        # Test tier manager
        logger.info("Testing Tier Manager")
        tier = universe_engine.tier_manager.determine_tier(None, market_cap=15_000_000_000)
        logger.info(f"Determined tier: {tier.value}")
        
        # Test normalizer
        logger.info("Testing Normalizer")
        from app.universe.sources.universe_source import TickerInfo
        ticker = TickerInfo(
            symbol="aapl",
            name="Apple Inc.",
            exchange="XNAS",
            market_cap=2500000000000
        )
        normalized = universe_engine.normalizer.normalize_ticker(ticker)
        logger.info(f"Normalized ticker: {normalized.symbol}, exchange: {normalized.exchange}")
        
        # Test validator
        logger.info("Testing Validator")
        result = universe_engine.validator.validate(normalized)
        logger.info(f"Validation result: passed={result.passed}")
        
        # Test enricher
        logger.info("Testing Enricher")
        enriched = universe_engine.enricher.enrich_ticker(normalized)
        logger.info(f"Enriched ticker: market_cap_tier={enriched.market_cap_tier}")
        
        # Test prioritizer
        logger.info("Testing Prioritizer")
        priority_score = universe_engine.prioritizer.calculate_priority_score(enriched, market_cap=2500000000000)
        logger.info(f"Priority score: {priority_score.overall_score:.2f}, tier: {priority_score.recommended_tier.value}")
        
        # Test discovery engine
        logger.info("Testing Discovery Engine")
        candidate = universe_engine.discovery_engine.detect_volume_explosion(
            symbol="TEST",
            current_volume=10_000_000,
            avg_volume=2_000_000,
            current_price=100.0
        )
        if candidate:
            logger.info(f"Discovery candidate found: {candidate.symbol}, trigger: {candidate.trigger.value}")
        
        # Test event bus
        logger.info("Testing Event Bus")
        from app.universe.events.universe_event_bus import universe_event_bus
        universe_event_bus.emit_new_leader_discovered(
            symbol="TEST",
            trigger="volume_explosion",
            confidence=85.0,
            discovery_data={}
        )
        logger.info("Event emitted successfully")
        
        # Test statistics
        logger.info("Testing Statistics")
        stats = await universe_engine.get_universe_statistics()
        logger.info(f"Identity statistics: {stats['identity_statistics']}")
        
        logger.info("Universe Engine test completed successfully")
        
    except Exception as e:
        logger.error(f"Universe Engine test failed: {e}")
        raise
    finally:
        # Close connections
        if 'universe_engine' in locals():
            await universe_engine.close()
            logger.info("Universe Engine closed")


async def main():
    """Main test function"""
    await test_universe_engine()


if __name__ == "__main__":
    asyncio.run(main())
