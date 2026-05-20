"""
Universe Tiers

TIER 1 - Institutional Leaders (Full realtime lifecycle tracking)
TIER 2 - Active Watchlist (Partial realtime)
TIER 3 - Passive Market Universe (Daily recalculation)
TIER 4 - Dormant/Inactive (Minimal maintenance)

Dynamic tier movement based on quality changes.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.universe.enrichment.enricher import EnrichedTicker

logger = logging.getLogger(__name__)


class UniverseTier(Enum):
    """Universe tier classification"""
    TIER_1 = "tier_1"  # Institutional leaders - Full realtime
    TIER_2 = "tier_2"  # Active watchlist - Partial realtime
    TIER_3 = "tier_3"  # Passive universe - Daily recalculation
    TIER_4 = "tier_4"  # Dormant/inactive - Minimal maintenance


@dataclass
class TierConfig:
    """Tier configuration"""
    tier: UniverseTier
    # Market cap requirements
    min_market_cap: float = 0
    # Volume requirements
    min_avg_volume: int = 0
    min_avg_dollar_volume: float = 0
    # RS requirements
    min_rs: float = 0
    # Institutional quality requirements
    min_institutional_quality: float = 0
    # Processing level
    realtime: bool = False
    websocket: bool = False
    deep_analysis: bool = False
    setup_analysis: bool = False
    # Update frequency
    update_frequency: str = "daily"  # realtime, intraday, daily, weekly
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tier": self.tier.value,
            "min_market_cap": self.min_market_cap,
            "min_avg_volume": self.min_avg_volume,
            "min_avg_dollar_volume": self.min_avg_dollar_volume,
            "min_rs": self.min_rs,
            "min_institutional_quality": self.min_institutional_quality,
            "realtime": self.realtime,
            "websocket": self.websocket,
            "deep_analysis": self.deep_analysis,
            "setup_analysis": self.setup_analysis,
            "update_frequency": self.update_frequency
        }


class TierManager:
    """
    Universe Tier Manager
    
    TIER 1 - Institutional Leaders
    - Criteria: Market cap > $10B, volume > 5M/day, RS > 1.5
    - Processing: Full WebSocket streaming, deep analysis, realtime tracking
    - Count: ~200-500 tickers
    
    TIER 2 - Active Watchlist
    - Criteria: Market cap > $2B, volume > 1M/day, RS > 1.2
    - Processing: Daily intraday updates, setup analysis
    - Count: ~1000-2000 tickers
    
    TIER 3 - Passive Market Universe
    - Criteria: Market cap > $500M, volume > 500K/day
    - Processing: Daily recalculation, no realtime
    - Count: ~3000-5000 tickers
    
    TIER 4 - Dormant/Inactive
    - Criteria: Market cap < $500M or volume < 500K/day
    - Processing: Weekly refresh, minimal analysis
    - Count: ~1000-2000 tickers
    
    Dynamic tier movement:
    - Promote: TIER 4 → TIER 3 → TIER 2 → TIER 1 (quality improvement)
    - Demote: TIER 1 → TIER 2 → TIER 3 → TIER 4 (quality deterioration)
    """
    
    def __init__(self):
        self._tier_configs = self._init_tier_configs()
        self._ticker_tiers: Dict[str, UniverseTier] = {}
        self._tier_changes: List[Dict[str, Any]] = []
        self._loaded_from_db = False
    
    def _init_tier_configs(self) -> Dict[UniverseTier, TierConfig]:
        """Initialize tier configurations"""
        return {
            UniverseTier.TIER_1: TierConfig(
                tier=UniverseTier.TIER_1,
                min_market_cap=10_000_000_000,  # $10B
                min_avg_volume=5_000_000,  # 5M shares
                min_avg_dollar_volume=50_000_000,  # $50M
                min_rs=1.5,
                min_institutional_quality=70,
                realtime=True,
                websocket=True,
                deep_analysis=True,
                setup_analysis=True,
                update_frequency="realtime"
            ),
            UniverseTier.TIER_2: TierConfig(
                tier=UniverseTier.TIER_2,
                min_market_cap=2_000_000_000,  # $2B
                min_avg_volume=1_000_000,  # 1M shares
                min_avg_dollar_volume=10_000_000,  # $10M
                min_rs=1.2,
                min_institutional_quality=50,
                realtime=False,
                websocket=False,
                deep_analysis=False,
                setup_analysis=True,
                update_frequency="intraday"
            ),
            UniverseTier.TIER_3: TierConfig(
                tier=UniverseTier.TIER_3,
                min_market_cap=500_000_000,  # $500M
                min_avg_volume=500_000,  # 500K shares
                min_avg_dollar_volume=1_000_000,  # $1M
                min_rs=0,
                min_institutional_quality=0,
                realtime=False,
                websocket=False,
                deep_analysis=False,
                setup_analysis=False,
                update_frequency="daily"
            ),
            UniverseTier.TIER_4: TierConfig(
                tier=UniverseTier.TIER_4,
                min_market_cap=0,
                min_avg_volume=0,
                min_avg_dollar_volume=0,
                min_rs=0,
                min_institutional_quality=0,
                realtime=False,
                websocket=False,
                deep_analysis=False,
                setup_analysis=False,
                update_frequency="weekly"
            )
        }
    
    def determine_tier(self, enriched_ticker: EnrichedTicker, market_cap: Optional[float] = None) -> UniverseTier:
        """
        Determine tier for a ticker based on enrichment data.
        
        Args:
            enriched_ticker: Enriched ticker information
            market_cap: Market cap (optional, can be derived)
            
        Returns:
            UniverseTier
        """
        # Check TIER 1 criteria
        tier1_config = self._tier_configs[UniverseTier.TIER_1]
        if self._meets_tier_criteria(enriched_ticker, tier1_config, market_cap):
            return UniverseTier.TIER_1
        
        # Check TIER 2 criteria
        tier2_config = self._tier_configs[UniverseTier.TIER_2]
        if self._meets_tier_criteria(enriched_ticker, tier2_config, market_cap):
            return UniverseTier.TIER_2
        
        # Check TIER 3 criteria
        tier3_config = self._tier_configs[UniverseTier.TIER_3]
        if self._meets_tier_criteria(enriched_ticker, tier3_config, market_cap):
            return UniverseTier.TIER_3
        
        # Default to TIER 4
        return UniverseTier.TIER_4
    
    def _meets_tier_criteria(
        self,
        enriched_ticker: EnrichedTicker,
        config: TierConfig,
        market_cap: Optional[float] = None
    ) -> bool:
        """
        Check if ticker meets tier criteria.
        
        Args:
            enriched_ticker: Enriched ticker
            config: Tier configuration
            market_cap: Market cap
            
        Returns:
            True if meets criteria
        """
        # Market cap check
        if market_cap and market_cap < config.min_market_cap:
            return False
        
        # Volume check
        if enriched_ticker.avg_volume_20d and enriched_ticker.avg_volume_20d < config.min_avg_volume:
            return False
        
        # Dollar volume check
        if enriched_ticker.avg_dollar_volume_20d and enriched_ticker.avg_dollar_volume_20d < config.min_avg_dollar_volume:
            return False
        
        # RS check
        if config.min_rs > 0:
            rs = enriched_ticker.rs_baseline_spy or enriched_ticker.rs_baseline_qqq
            if rs and rs < config.min_rs:
                return False
        
        # Institutional quality check
        if config.min_institutional_quality > 0:
            if enriched_ticker.institutional_quality_score and enriched_ticker.institutional_quality_score < config.min_institutional_quality:
                return False
        
        return True
    
    def assign_tier(self, symbol: str, enriched_ticker: EnrichedTicker, market_cap: Optional[float] = None) -> UniverseTier:
        """
        Assign tier to a ticker.
        
        Args:
            symbol: Ticker symbol
            enriched_ticker: Enriched ticker information
            market_cap: Market cap
            
        Returns:
            Assigned UniverseTier
        """
        new_tier = self.determine_tier(enriched_ticker, market_cap)
        old_tier = self._ticker_tiers.get(symbol)
        
        # Track tier change
        if old_tier and old_tier != new_tier:
            self._tier_changes.append({
                "symbol": symbol,
                "old_tier": old_tier.value,
                "new_tier": new_tier.value,
                "timestamp": datetime.utcnow().isoformat()
            })
            logger.info(f"Tier change: {symbol} {old_tier.value} → {new_tier.value}")
        
        self._ticker_tiers[symbol] = new_tier
        return new_tier
    
    def assign_tiers_batch(self, enriched_tickers: List[EnrichedTicker], market_cap_map: Optional[Dict[str, float]] = None) -> Dict[str, UniverseTier]:
        """
        Assign tiers to multiple tickers.
        
        Args:
            enriched_tickers: List of enriched tickers
            market_cap_map: Optional mapping of symbol to market cap
            
        Returns:
            Dictionary mapping symbol to tier
        """
        tier_assignments = {}
        
        for ticker in enriched_tickers:
            market_cap = market_cap_map.get(ticker.symbol) if market_cap_map else None
            tier = self.assign_tier(ticker.symbol, ticker, market_cap)
            tier_assignments[ticker.symbol] = tier
        
        logger.info(f"Assigned tiers to {len(tier_assignments)} tickers")
        return tier_assignments
    
    def get_tier(self, symbol: str) -> Optional[UniverseTier]:
        """
        Get tier for a symbol.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            UniverseTier or None if not assigned
        """
        return self._ticker_tiers.get(symbol)
    
    def get_tickers_by_tier(self, tier: UniverseTier) -> List[str]:
        """
        Get all tickers in a specific tier.
        
        Args:
            tier: Universe tier
            
        Returns:
            List of symbols in the tier
        """
        return [symbol for symbol, t in self._ticker_tiers.items() if t == tier]
    
    def promote_tier(self, symbol: str) -> Optional[UniverseTier]:
        """
        Promote ticker to next higher tier.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            New tier or None if already at TIER 1
        """
        current_tier = self.get_tier(symbol)
        if not current_tier:
            return None
        
        if current_tier == UniverseTier.TIER_1:
            return current_tier  # Already at highest tier
        
        # Promote to next tier
        tier_order = [UniverseTier.TIER_4, UniverseTier.TIER_3, UniverseTier.TIER_2, UniverseTier.TIER_1]
        current_index = tier_order.index(current_tier)
        new_tier = tier_order[current_index + 1]
        
        self._ticker_tiers[symbol] = new_tier
        
        logger.info(f"Promoted {symbol} to {new_tier.value}")
        return new_tier
    
    def demote_tier(self, symbol: str) -> Optional[UniverseTier]:
        """
        Demote ticker to next lower tier.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            New tier or None if already at TIER 4
        """
        current_tier = self.get_tier(symbol)
        if not current_tier:
            return None
        
        if current_tier == UniverseTier.TIER_4:
            return current_tier  # Already at lowest tier
        
        # Demote to next tier
        tier_order = [UniverseTier.TIER_4, UniverseTier.TIER_3, UniverseTier.TIER_2, UniverseTier.TIER_1]
        current_index = tier_order.index(current_tier)
        new_tier = tier_order[current_index - 1]
        
        self._ticker_tiers[symbol] = new_tier
        
        logger.info(f"Demoted {symbol} to {new_tier.value}")
        return new_tier
    
    def reevaluate_tier(self, symbol: str, enriched_ticker: EnrichedTicker, market_cap: Optional[float] = None) -> UniverseTier:
        """
        Reevaluate and potentially update tier for a ticker.
        
        Args:
            symbol: Ticker symbol
            enriched_ticker: Enriched ticker information
            market_cap: Market cap
            
        Returns:
            New tier (may be same as old)
        """
        return self.assign_tier(symbol, enriched_ticker, market_cap)
    
    def get_tier_statistics(self) -> Dict[str, Any]:
        """
        Get tier statistics.
        
        Returns:
            Dictionary with statistics
        """
        tier_counts = {}
        for tier in UniverseTier:
            tier_counts[tier.value] = len(self.get_tickers_by_tier(tier))
        
        return {
            "total_tickers": len(self._ticker_tiers),
            "tier_distribution": tier_counts,
            "recent_tier_changes": self._tier_changes[-10:] if self._tier_changes else [],
            "total_tier_changes": len(self._tier_changes)
        }
    
    def get_tier_config(self, tier: UniverseTier) -> TierConfig:
        """
        Get configuration for a tier.
        
        Args:
            tier: Universe tier
            
        Returns:
            TierConfig
        """
        return self._tier_configs[tier]
    
    def clear_tier_changes(self):
        """Clear tier change history"""
        self._tier_changes.clear()
        logger.info("Cleared tier change history")
    
    async def load_tiers_from_database(self, db_session) -> int:
        """
        Load tier assignments from database.
        
        Args:
            db_session: Database session
            
        Returns:
            Number of tiers loaded
        """
        try:
            from sqlalchemy import select
            from app.models.universe import InstrumentIdentity
            # Use the local UniverseTier enum, not the SQLAlchemy model
            from app.models.universe import UniverseTier as UniverseTierModel
            
            # Query all tier assignments from database
            query = (
                select(InstrumentIdentity.current_symbol, UniverseTierModel.tier)
                .join(UniverseTierModel, InstrumentIdentity.internal_id == UniverseTierModel.instrument_id)
                .where(InstrumentIdentity.lifecycle_state == "active")
            )
            
            result = await db_session.execute(query)
            tier_assignments = result.fetchall()
            
            # Create mapping from enum values to enum instances (outside loop for efficiency)
            tier_map = {tier.value: tier for tier in UniverseTier}
            logger.info(f"Created tier mapping: {tier_map}")
            
            # Load into memory
            loaded_count = 0
            for symbol, tier_str in tier_assignments:
                try:
                    # UniverseTier is an Enum, convert string value to enum
                    tier = tier_map.get(tier_str)
                    if tier:
                        self._ticker_tiers[symbol] = tier
                        loaded_count += 1
                    else:
                        logger.warning(f"Invalid tier value for {symbol}: {tier_str}")
                except Exception as e:
                    logger.warning(f"Error loading tier for {symbol}: {e}")
            
            self._loaded_from_db = True
            logger.info(f"Loaded {loaded_count} tier assignments from database")
            return loaded_count
            
        except Exception as e:
            logger.error(f"Failed to load tiers from database: {e}")
            return 0
