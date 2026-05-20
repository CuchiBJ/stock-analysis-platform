"""
Canonical Identity System

CRITICAL: Handle symbol changes (FB → META, mergers, relistings)
Maintains instrument identity across symbol changes using internal UUID.
"""

import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class AssetType(Enum):
    """Asset type classification"""
    COMMON_STOCK = "common_stock"
    ETF = "etf"
    ADR = "adr"
    WARRANT = "warrant"
    PREFERRED = "preferred"
    REIT = "reit"
    OTHER = "other"


class LifecycleState(Enum):
    """Instrument lifecycle state"""
    IPO = "ipo"  # Recently listed
    ACTIVE = "active"  # Normal active listing
    DELISTED = "delisted"  # Removed from exchange
    MERGED = "merged"  # Acquired/merged
    SYMBOL_CHANGED = "symbol_changed"  # Symbol changed
    EMERGING_LEADER = "emerging_leader"  # New institutional leader
    DORMANT_LEADER = "dormant_leader"  # Former leader that deteriorated


class ListingEventType(Enum):
    """Types of listing events"""
    IPO = "ipo"
    DELISTING = "delisting"
    SYMBOL_CHANGE = "symbol_change"
    SECTOR_MIGRATION = "sector_migration"
    EXCHANGE_CHANGE = "exchange_change"
    MERGER = "merger"
    ACQUISITION = "acquisition"


@dataclass
class ListingEvent:
    """Listing event for tracking lifecycle"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    instrument_id: str = ""
    event_type: ListingEventType = ListingEventType.SYMBOL_CHANGE
    event_date: datetime = field(default_factory=datetime.utcnow)
    old_symbol: Optional[str] = None
    new_symbol: Optional[str] = None
    old_exchange: Optional[str] = None
    new_exchange: Optional[str] = None
    old_sector: Optional[str] = None
    new_sector: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "event_id": self.event_id,
            "instrument_id": self.instrument_id,
            "event_type": self.event_type.value,
            "event_date": self.event_date.isoformat(),
            "old_symbol": self.old_symbol,
            "new_symbol": self.new_symbol,
            "old_exchange": self.old_exchange,
            "new_exchange": self.new_exchange,
            "old_sector": self.old_sector,
            "new_sector": self.new_sector,
            "metadata": self.metadata
        }


@dataclass
class InstrumentIdentity:
    """Canonical instrument identity"""
    internal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_symbol: str = ""
    historical_symbols: List[str] = field(default_factory=list)
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE
    company_name: str = ""
    primary_exchange: str = ""
    asset_type: AssetType = AssetType.COMMON_STOCK
    listing_history: List[ListingEvent] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "internal_id": self.internal_id,
            "current_symbol": self.current_symbol,
            "historical_symbols": self.historical_symbols,
            "lifecycle_state": self.lifecycle_state.value,
            "company_name": self.company_name,
            "primary_exchange": self.primary_exchange,
            "asset_type": self.asset_type.value,
            "listing_history": [event.to_dict() for event in self.listing_history],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    def add_historical_symbol(self, symbol: str):
        """Add symbol to historical symbols"""
        if symbol not in self.historical_symbols:
            self.historical_symbols.append(symbol)
    
    def add_listing_event(self, event: ListingEvent):
        """Add listing event to history"""
        self.listing_history.append(event)
        self.updated_at = datetime.utcnow()


class CanonicalIdentityManager:
    """
    Canonical Identity Manager
    
    CRITICAL: Handles symbol changes and maintains instrument identity.
    
    Key Features:
    - Internal UUID never changes (handles FB → META)
    - Track all historical symbols
    - Map historical symbols to current symbol
    - Track company identity across symbol changes
    - Resolve duplicate listings
    """
    
    def __init__(self):
        self._identities: Dict[str, InstrumentIdentity] = {}  # internal_id -> identity
        self._symbol_to_id: Dict[str, str] = {}  # symbol -> internal_id
        self._company_to_id: Dict[str, str] = {}  # company_name -> internal_id
    
    def create_identity(
        self,
        symbol: str,
        company_name: str = "",
        primary_exchange: str = "",
        asset_type: AssetType = AssetType.COMMON_STOCK
    ) -> InstrumentIdentity:
        """
        Create a new instrument identity.
        
        Args:
            symbol: Current symbol
            company_name: Company name
            primary_exchange: Primary exchange
            asset_type: Asset type
            
        Returns:
            InstrumentIdentity
        """
        identity = InstrumentIdentity(
            current_symbol=symbol.upper(),
            company_name=company_name,
            primary_exchange=primary_exchange,
            asset_type=asset_type
        )
        
        identity.add_historical_symbol(symbol.upper())
        
        # Store mappings
        self._identities[identity.internal_id] = identity
        self._symbol_to_id[symbol.upper()] = identity.internal_id
        
        if company_name:
            self._company_to_id[company_name] = identity.internal_id
        
        logger.info(f"Created identity for {symbol} (ID: {identity.internal_id})")
        return identity
    
    def get_identity_by_symbol(self, symbol: str) -> Optional[InstrumentIdentity]:
        """
        Get identity by current symbol.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            InstrumentIdentity or None if not found
        """
        internal_id = self._symbol_to_id.get(symbol.upper())
        if internal_id:
            return self._identities.get(internal_id)
        return None
    
    def get_identity_by_internal_id(self, internal_id: str) -> Optional[InstrumentIdentity]:
        """
        Get identity by internal ID.
        
        Args:
            internal_id: Internal UUID
            
        Returns:
            InstrumentIdentity or None if not found
        """
        return self._identities.get(internal_id)
    
    def get_identity_by_company(self, company_name: str) -> Optional[InstrumentIdentity]:
        """
        Get identity by company name.
        
        Args:
            company_name: Company name
            
        Returns:
            InstrumentIdentity or None if not found
        """
        internal_id = self._company_to_id.get(company_name)
        if internal_id:
            return self._identities.get(internal_id)
        return None
    
    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """
        Resolve symbol to current symbol (handles historical symbols).
        
        Args:
            symbol: Ticker symbol (may be historical)
            
        Returns:
            Current symbol or None if not found
        """
        # Check if it's a current symbol
        identity = self.get_identity_by_symbol(symbol)
        if identity:
            return identity.current_symbol
        
        # Check if it's a historical symbol
        for identity in self._identities.values():
            if symbol.upper() in identity.historical_symbols:
                return identity.current_symbol
        
        return None
    
    def change_symbol(
        self,
        old_symbol: str,
        new_symbol: str,
        change_date: Optional[datetime] = None
    ) -> Optional[InstrumentIdentity]:
        """
        Handle symbol change (e.g., FB → META).
        
        Args:
            old_symbol: Old symbol
            new_symbol: New symbol
            change_date: Date of change
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.get_identity_by_symbol(old_symbol)
        if not identity:
            logger.warning(f"Identity not found for symbol change: {old_symbol} → {new_symbol}")
            return None
        
        # Update mappings
        del self._symbol_to_id[old_symbol.upper()]
        self._symbol_to_id[new_symbol.upper()] = identity.internal_id
        
        # Update identity
        identity.add_historical_symbol(old_symbol.upper())
        identity.current_symbol = new_symbol.upper()
        identity.lifecycle_state = LifecycleState.SYMBOL_CHANGED
        
        # Add listing event
        event = ListingEvent(
            instrument_id=identity.internal_id,
            event_type=ListingEventType.SYMBOL_CHANGE,
            event_date=change_date or datetime.utcnow(),
            old_symbol=old_symbol.upper(),
            new_symbol=new_symbol.upper()
        )
        identity.add_listing_event(event)
        
        logger.info(f"Symbol changed: {old_symbol} → {new_symbol} (ID: {identity.internal_id})")
        return identity
    
    def add_ipo(
        self,
        symbol: str,
        company_name: str,
        ipo_date: Optional[datetime] = None,
        exchange: str = "",
        asset_type: AssetType = AssetType.COMMON_STOCK
    ) -> InstrumentIdentity:
        """
        Add new IPO to universe.
        
        Args:
            symbol: IPO symbol
            company_name: Company name
            ipo_date: IPO date
            exchange: Exchange
            asset_type: Asset type
            
        Returns:
            InstrumentIdentity
        """
        identity = self.create_identity(
            symbol=symbol,
            company_name=company_name,
            primary_exchange=exchange,
            asset_type=asset_type
        )
        
        identity.lifecycle_state = LifecycleState.IPO
        
        # Add IPO event
        event = ListingEvent(
            instrument_id=identity.internal_id,
            event_type=ListingEventType.IPO,
            event_date=ipo_date or datetime.utcnow(),
            new_symbol=symbol.upper(),
            new_exchange=exchange
        )
        identity.add_listing_event(event)
        
        logger.info(f"IPO added: {symbol} (ID: {identity.internal_id})")
        return identity
    
    def delist(
        self,
        symbol: str,
        delisting_date: Optional[datetime] = None,
        reason: str = ""
    ) -> Optional[InstrumentIdentity]:
        """
        Delist instrument from universe.
        
        Args:
            symbol: Symbol to delist
            delisting_date: Delisting date
            reason: Reason for delisting
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.get_identity_by_symbol(symbol)
        if not identity:
            logger.warning(f"Identity not found for delisting: {symbol}")
            return None
        
        identity.lifecycle_state = LifecycleState.DELISTED
        
        # Add delisting event
        event = ListingEvent(
            instrument_id=identity.internal_id,
            event_type=ListingEventType.DELISTING,
            event_date=delisting_date or datetime.utcnow(),
            old_symbol=symbol.upper(),
            metadata={"reason": reason}
        )
        identity.add_listing_event(event)
        
        logger.info(f"Delisted: {symbol} (ID: {identity.internal_id})")
        return identity
    
    def merge(
        self,
        acquired_symbol: str,
        acquiring_symbol: str,
        merger_date: Optional[datetime] = None
    ) -> Optional[InstrumentIdentity]:
        """
        Handle merger/acquisition.
        
        Args:
            acquired_symbol: Symbol of acquired company
            acquiring_symbol: Symbol of acquiring company
            merger_date: Merger date
            
        Returns:
            Updated InstrumentIdentity or None if not found
        """
        identity = self.get_identity_by_symbol(acquired_symbol)
        if not identity:
            logger.warning(f"Identity not found for merger: {acquired_symbol}")
            return None
        
        identity.lifecycle_state = LifecycleState.MERGED
        
        # Add merger event
        event = ListingEvent(
            instrument_id=identity.internal_id,
            event_type=ListingEventType.MERGER,
            event_date=merger_date or datetime.utcnow(),
            old_symbol=acquired_symbol.upper(),
            metadata={"acquiring_symbol": acquiring_symbol.upper()}
        )
        identity.add_listing_event(event)
        
        logger.info(f"Merged: {acquired_symbol} → {acquiring_symbol} (ID: {identity.internal_id})")
        return identity
    
    def get_all_symbols(self) -> List[str]:
        """
        Get all current symbols.
        
        Returns:
            List of current symbols
        """
        return list(self._symbol_to_id.keys())
    
    def get_all_identities(self) -> List[InstrumentIdentity]:
        """
        Get all identities.
        
        Returns:
            List of all InstrumentIdentity objects
        """
        return list(self._identities.values())
    
    def get_identities_by_state(self, state: LifecycleState) -> List[InstrumentIdentity]:
        """
        Get identities by lifecycle state.
        
        Args:
            state: Lifecycle state
            
        Returns:
            List of InstrumentIdentity objects
        """
        return [identity for identity in self._identities.values() if identity.lifecycle_state == state]
    
    def get_identities_by_asset_type(self, asset_type: AssetType) -> List[InstrumentIdentity]:
        """
        Get identities by asset type.
        
        Args:
            asset_type: Asset type
            
        Returns:
            List of InstrumentIdentity objects
        """
        return [identity for identity in self._identities.values() if identity.asset_type == asset_type]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get identity system statistics.
        
        Returns:
            Dictionary with statistics
        """
        state_counts = {}
        for state in LifecycleState:
            state_counts[state.value] = len(self.get_identities_by_state(state))
        
        asset_type_counts = {}
        for asset_type in AssetType:
            asset_type_counts[asset_type.value] = len(self.get_identities_by_asset_type(asset_type))
        
        return {
            "total_identities": len(self._identities),
            "total_symbols": len(self._symbol_to_id),
            "total_companies": len(self._company_to_id),
            "state_distribution": state_counts,
            "asset_type_distribution": asset_type_counts
        }


# Global canonical identity manager instance
canonical_identity_manager = CanonicalIdentityManager()
