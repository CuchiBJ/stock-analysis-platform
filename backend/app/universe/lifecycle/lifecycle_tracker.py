"""
Universe Lifecycle System

Track instrument lifecycle:
- IPOs
- Delistings
- Ticker changes
- Sector migrations
- Exchange changes
- Emerging leaders
- Dormant leaders
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from app.universe.identity.canonical_identity import (
    InstrumentIdentity,
    LifecycleState,
    ListingEvent,
    ListingEventType,
    CanonicalIdentityManager
)
from app.market_data.events.event_bus import MarketEvent, EventPriority

logger = logging.getLogger(__name__)


class UniverseLifecycleTracker:
    """
    Universe Lifecycle Tracker
    
    Track instrument lifecycle:
    - IPOs (new listings)
    - Delistings (removed from exchange)
    - Ticker changes (FB → META)
    - Sector migrations (company changes sector)
    - Exchange changes (NASDAQ → NYSE)
    - Emerging leaders (new institutional leaders)
    - Dormant leaders (leaders that deteriorated)
    """
    
    def __init__(self, identity_manager: CanonicalIdentityManager):
        self.identity_manager = identity_manager
        self._lifecycle_events: List[ListingEvent] = []
    
    def track_ipo(
        self,
        symbol: str,
        company_name: str,
        ipo_date: datetime,
        exchange: str = "",
        asset_type: str = "common_stock"
    ) -> InstrumentIdentity:
        """
        Track new IPO.
        
        Args:
            symbol: IPO symbol
            company_name: Company name
            ipo_date: IPO date
            exchange: Exchange
            asset_type: Asset type
            
        Returns:
            InstrumentIdentity
        """
        identity = self.identity_manager.add_ipo(
            symbol=symbol,
            company_name=company_name,
            ipo_date=ipo_date,
            exchange=exchange,
            asset_type=asset_type
        )
        
        logger.info(f"Tracked IPO: {symbol} on {ipo_date}")
        return identity
    
    def track_delisting(
        self,
        symbol: str,
        delisting_date: datetime,
        reason: str = ""
    ) -> Optional[InstrumentIdentity]:
        """
        Track delisting.
        
        Args:
            symbol: Symbol to delist
            delisting_date: Delisting date
            reason: Reason for delisting
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.identity_manager.delist(
            symbol=symbol,
            delisting_date=delisting_date,
            reason=reason
        )
        
        if identity:
            logger.info(f"Tracked delisting: {symbol} on {delisting_date}")
        
        return identity
    
    def track_symbol_change(
        self,
        old_symbol: str,
        new_symbol: str,
        change_date: datetime
    ) -> Optional[InstrumentIdentity]:
        """
        Track symbol change (e.g., FB → META).
        
        Args:
            old_symbol: Old symbol
            new_symbol: New symbol
            change_date: Date of change
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.identity_manager.change_symbol(
            old_symbol=old_symbol,
            new_symbol=new_symbol,
            change_date=change_date
        )
        
        if identity:
            logger.info(f"Tracked symbol change: {old_symbol} → {new_symbol}")
        
        return identity
    
    def track_sector_migration(
        self,
        symbol: str,
        old_sector: str,
        new_sector: str,
        migration_date: datetime
    ) -> Optional[InstrumentIdentity]:
        """
        Track sector migration.
        
        Args:
            symbol: Symbol
            old_sector: Old sector
            new_sector: New sector
            migration_date: Date of migration
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.identity_manager.get_identity_by_symbol(symbol)
        if not identity:
            logger.warning(f"Identity not found for sector migration: {symbol}")
            return None
        
        # Add sector migration event
        event = ListingEvent(
            instrument_id=identity.internal_id,
            event_type=ListingEventType.SECTOR_MIGRATION,
            event_date=migration_date,
            old_sector=old_sector,
            new_sector=new_sector
        )
        identity.add_listing_event(event)
        
        logger.info(f"Tracked sector migration: {symbol} from {old_sector} to {new_sector}")
        return identity
    
    def track_exchange_change(
        self,
        symbol: str,
        old_exchange: str,
        new_exchange: str,
        change_date: datetime
    ) -> Optional[InstrumentIdentity]:
        """
        Track exchange change.
        
        Args:
            symbol: Symbol
            old_exchange: Old exchange
            new_exchange: New exchange
            change_date: Date of change
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.identity_manager.get_identity_by_symbol(symbol)
        if not identity:
            logger.warning(f"Identity not found for exchange change: {symbol}")
            return None
        
        # Add exchange change event
        event = ListingEvent(
            instrument_id=identity.internal_id,
            event_type=ListingEventType.EXCHANGE_CHANGE,
            event_date=change_date,
            old_exchange=old_exchange,
            new_exchange=new_exchange
        )
        identity.add_listing_event(event)
        
        # Update identity
        identity.primary_exchange = new_exchange
        
        logger.info(f"Tracked exchange change: {symbol} from {old_exchange} to {new_exchange}")
        return identity
    
    def track_emerging_leader(
        self,
        symbol: str,
        detection_date: datetime,
        reason: str = ""
    ) -> Optional[InstrumentIdentity]:
        """
        Track emerging leader.
        
        Args:
            symbol: Symbol
            detection_date: Detection date
            reason: Reason for emerging leader status
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.identity_manager.get_identity_by_symbol(symbol)
        if not identity:
            logger.warning(f"Identity not found for emerging leader: {symbol}")
            return None
        
        # Update lifecycle state
        identity.lifecycle_state = LifecycleState.EMERGING_LEADER
        
        logger.info(f"Tracked emerging leader: {symbol} on {detection_date}")
        return identity
    
    def track_dormant_leader(
        self,
        symbol: str,
        detection_date: datetime,
        reason: str = ""
    ) -> Optional[InstrumentIdentity]:
        """
        Track dormant leader (former leader that deteriorated).
        
        Args:
            symbol: Symbol
            detection_date: Detection date
            reason: Reason for dormant status
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.identity_manager.get_identity_by_symbol(symbol)
        if not identity:
            logger.warning(f"Identity not found for dormant leader: {symbol}")
            return None
        
        # Update lifecycle state
        identity.lifecycle_state = LifecycleState.DORMANT_LEADER
        
        logger.info(f"Tracked dormant leader: {symbol} on {detection_date}")
        return identity
    
    def get_recent_ipos(self, days: int = 30) -> List[InstrumentIdentity]:
        """
        Get recent IPOs.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of recent IPO identities
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        ipos = []
        for identity in self.identity_manager.get_all_identities():
            if identity.lifecycle_state == LifecycleState.IPO:
                # Check if IPO date is within window
                for event in identity.listing_history:
                    if event.event_type == ListingEventType.IPO and event.event_date >= cutoff_date:
                        ipos.append(identity)
                        break
        
        return ipos
    
    def get_recent_delistings(self, days: int = 30) -> List[InstrumentIdentity]:
        """
        Get recent delistings.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of recently delisted identities
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        delistings = []
        for identity in self.identity_manager.get_all_identities():
            if identity.lifecycle_state == LifecycleState.DELISTED:
                # Check if delisting date is within window
                for event in identity.listing_history:
                    if event.event_type == ListingEventType.DELISTING and event.event_date >= cutoff_date:
                        delistings.append(identity)
                        break
        
        return delistings
    
    def get_emerging_leaders(self) -> List[InstrumentIdentity]:
        """
        Get all emerging leaders.
        
        Returns:
            List of emerging leader identities
        """
        return self.identity_manager.get_identities_by_state(LifecycleState.EMERGING_LEADER)
    
    def get_dormant_leaders(self) -> List[InstrumentIdentity]:
        """
        Get all dormant leaders.
        
        Returns:
            List of dormant leader identities
        """
        return self.identity_manager.get_identities_by_state(LifecycleState.DORMANT_LEADER)
    
    def get_lifecycle_statistics(self) -> Dict[str, Any]:
        """
        Get lifecycle statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = self.identity_manager.get_statistics()
        
        # Add lifecycle-specific statistics
        stats["recent_ipos_30d"] = len(self.get_recent_ipos(30))
        stats["recent_delistings_30d"] = len(self.get_recent_delistings(30))
        stats["emerging_leaders"] = len(self.get_emerging_leaders())
        stats["dormant_leaders"] = len(self.get_dormant_leaders())
        
        return stats
    
    def detect_lifecycle_changes(
        self,
        current_data: Dict[str, Any],
        previous_data: Dict[str, Any]
    ) -> List[MarketEvent]:
        """
        Detect lifecycle changes from data comparison.
        
        Args:
            current_data: Current ticker data
            previous_data: Previous ticker data
            
        Returns:
            List of detected lifecycle events
        """
        events = []
        
        # Detect sector changes
        if current_data.get("sector") != previous_data.get("sector"):
            event = MarketEvent(
                event_type="sector_migration",
                symbol=current_data.get("symbol", ""),
                priority=EventPriority.MEDIUM,
                data={
                    "old_sector": previous_data.get("sector"),
                    "new_sector": current_data.get("sector")
                }
            )
            events.append(event)
        
        # Detect exchange changes
        if current_data.get("exchange") != previous_data.get("exchange"):
            event = MarketEvent(
                event_type="exchange_change",
                symbol=current_data.get("symbol", ""),
                priority=EventPriority.MEDIUM,
                data={
                    "old_exchange": previous_data.get("exchange"),
                    "new_exchange": current_data.get("exchange")
                }
            )
            events.append(event)
        
        # Detect delisting (no price data)
        if current_data.get("close") is None and previous_data.get("close") is not None:
            event = MarketEvent(
                event_type="delisting",
                symbol=current_data.get("symbol", ""),
                priority=EventPriority.HIGH,
                data={"reason": "no_price_data"}
            )
            events.append(event)
        
        return events
