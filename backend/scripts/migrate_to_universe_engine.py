"""
Migrate existing Stock data to Universe Engine

This script migrates data from the legacy Stock table to the new
Universe Engine tables (InstrumentIdentity, UniverseEnrichment, UniverseTier).
"""

import asyncio
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.core.deps import get_db
from app.models.stock import Stock
from app.models.universe import InstrumentIdentity, UniverseEnrichment, UniverseTier
from app.universe.identity.canonical_identity import LifecycleState, AssetType
from app.universe.tiers.tier_manager import UniverseTier as TierEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_stock_to_universe(db: AsyncSession, stock: Stock) -> InstrumentIdentity:
    """
    Migrate a single Stock record to InstrumentIdentity.
    
    Args:
        db: Database session
        stock: Stock record to migrate
        
    Returns:
        InstrumentIdentity
    """
    # Generate internal UUID
    internal_id = str(uuid.uuid4())
    
    # Determine asset type
    asset_type = AssetType.COMMON_STOCK
    if stock.is_adr:
        asset_type = AssetType.ADR
    
    # Determine lifecycle state
    lifecycle_state = LifecycleState.ACTIVE.value if stock.is_active else LifecycleState.DELISTED.value
    
    # Create InstrumentIdentity
    identity = InstrumentIdentity(
        internal_id=internal_id,
        current_symbol=stock.symbol,
        historical_symbols=[stock.symbol],
        lifecycle_state=lifecycle_state,
        company_name=stock.name,
        primary_exchange="",  # Would need to fetch from source
        asset_type=asset_type.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(identity)
    await db.flush()
    
    logger.info(f"Migrated {stock.symbol} -> {internal_id}")
    return identity


async def migrate_enrichment(db: AsyncSession, identity: InstrumentIdentity, stock: Stock):
    """
    Create UniverseEnrichment record for migrated identity.
    
    Args:
        db: Database session
        identity: InstrumentIdentity
        stock: Original Stock record
    """
    enrichment = UniverseEnrichment(
        instrument_id=identity.internal_id,
        sector=stock.sector,
        industry=stock.industry,
        float_shares=int(stock.float_shares) if stock.float_shares and stock.float_shares < 2147483647 else None,
        avg_volume_20d=None,  # Would need to calculate from stock_prices
        avg_dollar_volume_20d=None,
        atr=None,
        atr_percent=None,
        volatility_profile=None,
        institutional_quality_score=None,
        rs_baseline_spy=None,
        rs_baseline_qqq=None,
        tradability_score=None,
        market_cap_tier=None,
        last_enriched_at=datetime.utcnow()
    )
    
    db.add(enrichment)
    await db.flush()
    
    logger.info(f"Created enrichment for {identity.current_symbol}")


async def migrate_tier(db: AsyncSession, identity: InstrumentIdentity, stock: Stock):
    """
    Create UniverseTier record for migrated identity.
    
    Args:
        db: Database session
        identity: InstrumentIdentity
        stock: Original Stock record
    """
    # Determine tier based on market cap
    if stock.market_cap:
        if stock.market_cap >= 10_000_000_000:  # $10B
            tier = TierEnum.TIER_1.value
        elif stock.market_cap >= 2_000_000_000:  # $2B
            tier = TierEnum.TIER_2.value
        elif stock.market_cap >= 500_000_000:  # $500M
            tier = TierEnum.TIER_3.value
        else:
            tier = TierEnum.TIER_4.value
    else:
        tier = TierEnum.TIER_4.value
    
    tier_record = UniverseTier(
        instrument_id=identity.internal_id,
        tier=tier,
        assigned_at=datetime.utcnow(),
        priority_score=None,
        institutional_quality_score=None,
        leadership_score=None,
        setup_quality_score=None,
        sector_relevance_score=None,
        regime_alignment_score=None,
        requires_realtime=(tier == TierEnum.TIER_1.value),
        requires_websocket=(tier == TierEnum.TIER_1.value),
        requires_deep_analysis=(tier == TierEnum.TIER_1.value),
        requires_setup_analysis=(tier in [TierEnum.TIER_1.value, TierEnum.TIER_2.value])
    )
    
    db.add(tier_record)
    await db.flush()
    
    logger.info(f"Assigned tier {tier} to {identity.current_symbol}")


async def migrate_all_stocks(db: AsyncSession):
    """
    Migrate all Stock records to Universe Engine.
    
    Args:
        db: Database session
    """
    logger.info("Starting migration of Stock records to Universe Engine")
    
    # Fetch all stocks
    result = await db.execute(select(Stock))
    stocks = result.scalars().all()
    
    logger.info(f"Found {len(stocks)} stocks to migrate")
    
    migrated_count = 0
    failed_count = 0
    
    for stock in stocks:
        try:
            # Migrate to InstrumentIdentity
            identity = await migrate_stock_to_universe(db, stock)
            
            # Create enrichment
            await migrate_enrichment(db, identity, stock)
            
            # Create tier assignment
            await migrate_tier(db, identity, stock)
            
            migrated_count += 1
            
            if migrated_count % 100 == 0:
                logger.info(f"Migrated {migrated_count}/{len(stocks)} stocks")
                await db.commit()
        
        except Exception as e:
            logger.error(f"Failed to migrate {stock.symbol}: {e}")
            failed_count += 1
            await db.rollback()
    
    # Final commit
    await db.commit()
    
    logger.info(f"Migration complete: {migrated_count} succeeded, {failed_count} failed")
    
    return {
        "total": len(stocks),
        "migrated": migrated_count,
        "failed": failed_count
    }


async def main():
    """Main migration function"""
    async for db in get_db():
        stats = await migrate_all_stocks(db)
        logger.info(f"Migration statistics: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
