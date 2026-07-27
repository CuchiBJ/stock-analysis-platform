"""
Universe Engine - Main Orchestrator

Orchestrates all Universe Engine components:
- Universe Source Layer
- Universe Normalization Layer
- Canonical Identity System
- Universe Validation Layer
- Universe Enrichment Layer
- Universe Lifecycle System
- Universe Tiers
- Auto Discovery Engine
- Discovery Scans
- Universe Health Monitoring
- Universe Event System
- Smart Universe Prioritization
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.universe.sources.universe_source import UniverseSourceManager, TickerInfo
from app.universe.normalization.normalizer import UniverseNormalizer
from app.universe.identity.canonical_identity import CanonicalIdentityManager, InstrumentIdentity, LifecycleState, AssetType
from app.universe.validation.validator import UniverseValidator, ValidationConfig, ValidationResult
from app.universe.enrichment.enricher import UniverseEnricher, EnrichedTicker
from app.universe.lifecycle.lifecycle_tracker import UniverseLifecycleTracker
from app.universe.tiers.tier_manager import TierManager, UniverseTier
from app.universe.discovery.auto_discovery import AutoDiscoveryEngine, DiscoveryCandidate
from app.universe.scans.discovery_scanner import DiscoveryScanner
from app.universe.monitoring.health_monitor import UniverseHealthMonitor, UniverseHealthReport
from app.universe.events.universe_event_bus import universe_event_bus, UniverseEventType
from app.universe.prioritization.prioritizer import SmartUniversePrioritizer, PriorityScore

logger = logging.getLogger(__name__)


class UniverseEngine:
    """
    Universe Engine - Main Orchestrator
    
    Orchestrates all Universe Engine components to:
    1. Ingest tickers from multiple sources
    2. Normalize and validate
    3. Assign canonical identities
    4. Enrich with institutional metrics
    5. Track lifecycle
    6. Assign tiers
    7. Auto-discover new leaders
    8. Monitor health
    9. Emit events
    10. Prioritize processing
    """
    
    def __init__(self, polygon_api_key: str):
        # Core components
        self.identity_manager = CanonicalIdentityManager()
        self.source_manager = UniverseSourceManager(polygon_api_key)
        self.normalizer = UniverseNormalizer()
        self.validator = UniverseValidator()
        self.enricher = UniverseEnricher()
        self.lifecycle_tracker = UniverseLifecycleTracker(self.identity_manager)
        self.tier_manager = TierManager()
        self.discovery_engine = AutoDiscoveryEngine()
        self.discovery_scanner = DiscoveryScanner()
        self.health_monitor = UniverseHealthMonitor()
        self.prioritizer = SmartUniversePrioritizer()
        
        # Configuration
        self.validation_config = ValidationConfig()
        
        # Database session for loading tiers
        self._db_session = None
    
    async def refresh_universe(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Refresh entire universe from sources.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with refresh statistics
        """
        logger.info("Starting universe refresh")
        
        # 1. Fetch from sources
        raw_tickers = await self.source_manager.get_all_active_listings()
        logger.info(f"Fetched {len(raw_tickers)} tickers from sources")
        
        # 2. Normalize
        normalized_tickers = self.normalizer.normalize_tickers(raw_tickers)
        logger.info(f"Normalized {len(normalized_tickers)} tickers")
        
        # 3. Validate
        valid_tickers = self.validator.filter_valid(normalized_tickers)
        logger.info(f"Validated {len(valid_tickers)} tickers")
        
        # 4. Assign identities
        identities = []
        for ticker in valid_tickers:
            existing_identity = self.identity_manager.get_identity_by_symbol(ticker.symbol)
            if existing_identity:
                identities.append(existing_identity)
            else:
                # Create new identity
                identity = self.identity_manager.create_identity(
                    symbol=ticker.symbol,
                    company_name=ticker.name,
                    primary_exchange=ticker.exchange,
                    asset_type=self._map_asset_type(ticker.asset_type)
                )
                identities.append(identity)
        
        logger.info(f"Assigned identities to {len(identities)} tickers")
        
        # 5. Enrich (would need price data in real implementation)
        enriched_tickers = self.enricher.enrich_batch(valid_tickers)
        logger.info(f"Enriched {len(enriched_tickers)} tickers")
        
        # 6. Assign tiers
        market_cap_map = {t.symbol: t.market_cap for t in valid_tickers if t.market_cap}
        tier_assignments = self.tier_manager.assign_tiers_batch(enriched_tickers, market_cap_map)
        logger.info(f"Assigned tiers to {len(tier_assignments)} tickers")
        
        # 7. Emit completion event
        universe_event_bus.emit_universe_refresh_complete(
            total_tickers=len(identities),
            new_tickers=len(identities) - len(self.identity_manager.get_all_identities()) + len(identities)
        )
        
        stats = {
            "total_tickers": len(identities),
            "new_tickers": 0,  # Would need to track in real implementation
            "tier_distribution": self.tier_manager.get_tier_statistics()
        }
        
        logger.info(f"Universe refresh complete: {stats}")
        return stats
    
    async def process_discovery_candidate(self, candidate: DiscoveryCandidate, db: AsyncSession) -> Optional[InstrumentIdentity]:
        """
        Process a discovery candidate and add to universe.
        
        Args:
            candidate: Discovery candidate
            db: Database session
            
        Returns:
            InstrumentIdentity if added, None otherwise
        """
        logger.info(f"Processing discovery candidate: {candidate.symbol}")
        
        # Check if already in universe (database)
        from app.models.universe import InstrumentIdentity as InstrumentIdentityModel
        from app.models.universe import UniverseEnrichment as UniverseEnrichmentModel
        from app.models.universe import UniverseTier as UniverseTierModel
        from app.models.stock import Stock
        from sqlalchemy import select
        
        existing_query = select(InstrumentIdentityModel).where(
            InstrumentIdentityModel.current_symbol == candidate.symbol.upper()
        ).limit(1)
        existing_result = await db.execute(existing_query)
        existing_db = existing_result.scalar_one_or_none()
        
        if existing_db:
            logger.info(f"Symbol {candidate.symbol} already in universe (database)")
            # Also update in-memory manager
            if not self.identity_manager.get_identity_by_symbol(candidate.symbol):
                self.identity_manager.create_identity(
                    symbol=candidate.symbol,
                    company_name=existing_db.company_name or candidate.symbol,
                    primary_exchange=existing_db.primary_exchange or "",
                    asset_type=AssetType(existing_db.asset_type) if existing_db.asset_type else AssetType.COMMON_STOCK
                )
            return self.identity_manager.get_identity_by_symbol(candidate.symbol)
        
        # Create identity in memory
        identity = self.identity_manager.create_identity(
            symbol=candidate.symbol,
            company_name=candidate.symbol,  # Will be enriched later
            asset_type=AssetType.COMMON_STOCK
        )
        
        # Save to database
        db_identity = InstrumentIdentityModel(
            internal_id=identity.internal_id,
            current_symbol=identity.current_symbol,
            historical_symbols=identity.historical_symbols,
            lifecycle_state=identity.lifecycle_state.value,
            company_name=identity.company_name,
            primary_exchange=identity.primary_exchange,
            asset_type=identity.asset_type.value,
            created_at=identity.created_at,
            updated_at=identity.updated_at
        )
        db.add(db_identity)
        await db.commit()
        logger.info(f"Saved identity to database: {candidate.symbol} (ID: {identity.internal_id})")
        
        # Create UniverseEnrichment record
        db_enrichment = UniverseEnrichmentModel(
            instrument_id=identity.internal_id,
            sector="Unknown",  # Will be enriched later
            industry="Unknown",
            float_shares=None,
            avg_volume_20d=0,
            avg_dollar_volume_20d=0,
            rs_baseline_spy=0,
            rs_baseline_qqq=0,
            institutional_quality_score=0,
        )
        db.add(db_enrichment)
        await db.commit()
        logger.info(f"Created enrichment record for: {candidate.symbol}")

        # Assign initial tier (TIER 3 for new discoveries)
        db_tier = UniverseTierModel(
            instrument_id=identity.internal_id,
            tier="tier_3",  # Start at TIER 3 for new discoveries
        )
        db.add(db_tier)
        await db.commit()
        logger.info(f"Assigned tier_3 to: {candidate.symbol}")
        
        # Add to Stock table for scheduler processing
        existing_stock = await db.execute(
            select(Stock).where(Stock.symbol == candidate.symbol.upper()).limit(1)
        )
        if not existing_stock.scalar_one_or_none():
            db_stock = Stock(
                symbol=candidate.symbol.upper(),
                company_name=candidate.symbol,
                is_active=True,
                added_at=datetime.utcnow()
            )
            db.add(db_stock)
            await db.commit()
            logger.info(f"Added to Stock table for scheduler processing: {candidate.symbol}")
        
        # Track as emerging leader
        self.lifecycle_tracker.track_emerging_leader(
            symbol=candidate.symbol,
            detection_date=datetime.utcnow(),
            reason=candidate.trigger.value
        )
        
        # Emit event
        universe_event_bus.emit_new_leader_discovered(
            symbol=candidate.symbol,
            trigger=candidate.trigger.value,
            confidence=candidate.confidence,
            discovery_data=candidate.data
        )
        
        logger.info(f"Added discovery candidate to universe with full onboarding: {candidate.symbol}")
        return identity
    
    async def run_nightly_scans(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Run nightly discovery scans.
        
        Args:
            db: Database session
            
        Returns:
            List of scan results
        """
        logger.info("Starting nightly discovery scans")
        
        # Would fetch ticker data from database in real implementation
        # For now, return empty results
        ticker_data = []
        
        results = self.discovery_scanner.run_all_scans(ticker_data)
        
        # Process candidates
        for result in results:
            for candidate in result.candidates:
                await self.process_discovery_candidate(candidate, db)
        
        logger.info(f"Nightly scans complete: {len(results)} scans run")
        return [r.to_dict() for r in results]
    
    async def generate_health_report(self, db: AsyncSession) -> UniverseHealthReport:
        """
        Generate universe health report.
        
        Args:
            db: Database session
            
        Returns:
            UniverseHealthReport
        """
        logger.info("Generating universe health report")
        
        identities = self.identity_manager.get_all_identities()
        
        # Would fetch real data from database in real implementation
        ticker_last_updates = {}
        ticker_prices = {}
        sector_counts = {}
        current_sectors = set()
        
        report = self.health_monitor.generate_health_report(
            total_tickers=len(identities),
            active_tickers=len([i for i in identities if i.lifecycle_state == LifecycleState.ACTIVE]),
            ticker_last_updates=ticker_last_updates,
            ticker_prices=ticker_prices,
            sector_counts=sector_counts,
            current_sectors=current_sectors
        )
        
        logger.info(f"Health report generated: {report.universe_freshness:.2f}% freshness")
        return report
    
    async def get_universe_statistics(self) -> Dict[str, Any]:
        """
        Get universe statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "identity_statistics": self.identity_manager.get_statistics(),
            "tier_statistics": self.tier_manager.get_tier_statistics(),
            "discovery_statistics": self.discovery_engine.get_discovery_statistics(),
            "scan_statistics": self.discovery_scanner.get_scan_statistics(),
            "health_statistics": self.health_monitor.get_health_statistics(),
            "event_statistics": universe_event_bus.get_statistics()
        }
    
    def _map_asset_type(self, asset_type: str) -> AssetType:
        """Map string asset type to AssetType enum"""
        mapping = {
            "common_stock": AssetType.COMMON_STOCK,
            "etf": AssetType.ETF,
            "adr": AssetType.ADR,
            "warrant": AssetType.WARRANT,
            "preferred": AssetType.PREFERRED,
            "reit": AssetType.REIT,
            "other": AssetType.OTHER
        }
        return mapping.get(asset_type.lower(), AssetType.COMMON_STOCK)
    
    async def close(self):
        """Close all connections"""
        await self.source_manager.close_all()
        logger.info("Universe Engine closed")


# Global universe engine instance
_universe_engine: Optional[UniverseEngine] = None


def get_universe_engine(polygon_api_key: Optional[str] = None) -> UniverseEngine:
    """
    Get global universe engine instance.
    
    Args:
        polygon_api_key: Polygon API key (optional, will work without it)
        
    Returns:
        UniverseEngine instance
    """
    global _universe_engine
    
    if _universe_engine is None:
        _universe_engine = UniverseEngine(polygon_api_key)
    
    return _universe_engine
