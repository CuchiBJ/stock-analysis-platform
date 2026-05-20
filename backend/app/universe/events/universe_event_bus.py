"""
Universe Event System

Emit internal events for universe changes:
- NewLeaderDiscoveredEvent
- NewIPOEvent
- SymbolChangedEvent
- LiquidityDeteriorationEvent
- SectorMigrationEvent
- NewHighRSEvent
- UniverseCoverageGapEvent
- TierPromotionEvent
- TierDemotionEvent
- DelistedEvent
"""

import uuid
import logging
from typing import List, Dict, Any, Callable, Set, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.market_data.events.event_bus import EventPriority

logger = logging.getLogger(__name__)


class UniverseEventType(Enum):
    """Universe event types"""
    NEW_LEADER_DISCOVERED = "new_leader_discovered"
    NEW_IPO = "new_ipo"
    SYMBOL_CHANGED = "symbol_changed"
    LIQUIDITY_DETERIORATION = "liquidity_deterioration"
    SECTOR_MIGRATION = "sector_migration"
    NEW_HIGH_RS = "new_high_rs"
    UNIVERSE_COVERAGE_GAP = "universe_coverage_gap"
    TIER_PROMOTION = "tier_promotion"
    TIER_DEMOTION = "tier_demotion"
    DELISTED = "delisted"
    UNIVERSE_REFRESH_COMPLETE = "universe_refresh_complete"


@dataclass
class UniverseEvent:
    """Internal universe event"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: UniverseEventType = UniverseEventType.NEW_LEADER_DISCOVERED
    instrument_id: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: EventPriority = EventPriority.MEDIUM
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "instrument_id": self.instrument_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "data": self.data,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UniverseEvent':
        """Create event from dictionary"""
        return cls(
            event_id=data["event_id"],
            event_type=UniverseEventType(data["event_type"]),
            instrument_id=data["instrument_id"],
            symbol=data["symbol"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=EventPriority(data["priority"]),
            data=data["data"],
            metadata=data["metadata"]
        )


class UniverseEventBus:
    """
    Universe Event Bus
    
    Emit internal events for universe changes:
    - NewLeaderDiscoveredEvent
    - NewIPOEvent
    - SymbolChangedEvent
    - LiquidityDeteriorationEvent
    - SectorMigrationEvent
    - NewHighRSEvent
    - UniverseCoverageGapEvent
    - TierPromotionEvent
    - TierDemotionEvent
    - DelistedEvent
    """
    
    def __init__(self):
        # Subscribers by event type
        self._subscribers: Dict[UniverseEventType, Set[Callable]] = {}
        # Global subscribers (receive all events)
        self._global_subscribers: Set[Callable] = set()
        # Event history
        self._event_history: List[UniverseEvent] = []
        self._max_history_size = 10000
        # Event statistics
        self._event_counts: Dict[UniverseEventType, int] = {}
    
    def subscribe(self, event_type: UniverseEventType, handler: Callable[[UniverseEvent], None]):
        """
        Subscribe to a specific event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Handler function to call when event is published
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        self._subscribers[event_type].add(handler)
        logger.debug(f"Subscribed to {event_type.value}")
    
    def unsubscribe(self, event_type: UniverseEventType, handler: Callable[[UniverseEvent], None]):
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed from {event_type.value}")
    
    def subscribe_global(self, handler: Callable[[UniverseEvent], None]):
        """
        Subscribe to all universe events.
        
        Args:
            handler: Handler function to call for all events
        """
        self._global_subscribers.add(handler)
        logger.debug("Subscribed to all universe events")
    
    def unsubscribe_global(self, handler: Callable[[UniverseEvent], None]):
        """
        Unsubscribe from all universe events.
        
        Args:
            handler: Handler function to remove
        """
        if handler in self._global_subscribers:
            self._global_subscribers.remove(handler)
            logger.debug("Unsubscribed from all universe events")
    
    def publish(self, event: UniverseEvent):
        """
        Publish a universe event.
        
        Args:
            event: UniverseEvent to publish
        """
        # Add to history
        self._add_to_history(event)
        
        # Update statistics
        self._event_counts[event.event_type] = self._event_counts.get(event.event_type, 0) + 1
        
        # Deliver to type-specific subscribers
        for handler in self._subscribers.get(event.event_type, set()):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in universe event handler for {event.event_type.value}: {e}")
        
        # Deliver to global subscribers
        for handler in self._global_subscribers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in global universe event handler: {e}")
        
        logger.debug(f"Published universe event: {event.event_type.value} for {event.symbol}")
    
    def _add_to_history(self, event: UniverseEvent):
        """Add event to history"""
        self._event_history.append(event)
        
        # Maintain max history size
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]
    
    def get_event_history(
        self,
        event_type: Optional[UniverseEventType] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[UniverseEvent]:
        """
        Get event history with optional filtering.
        
        Args:
            event_type: Filter by event type
            symbol: Filter by symbol
            limit: Maximum number of events to return
            
        Returns:
            List of events matching filters
        """
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if symbol:
            events = [e for e in events if e.symbol == symbol]
        
        # Return most recent first
        return events[-limit:][::-1]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get event bus statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "total_events": sum(self._event_counts.values()),
            "event_counts": {k.value: v for k, v in self._event_counts.items()},
            "history_size": len(self._event_history),
            "subscribers": {
                event_type.value: len(handlers)
                for event_type, handlers in self._subscribers.items()
            },
            "global_subscribers": len(self._global_subscribers)
        }
    
    # ========== Convenience Event Emitters ==========
    
    def emit_new_leader_discovered(
        self,
        symbol: str,
        trigger: str,
        confidence: float,
        discovery_data: Dict[str, Any]
    ):
        """Emit NewLeaderDiscoveredEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.NEW_LEADER_DISCOVERED,
            symbol=symbol,
            priority=EventPriority.HIGH,
            data={
                "trigger": trigger,
                "confidence": confidence,
                "discovery_data": discovery_data
            }
        )
        self.publish(event)
    
    def emit_new_ipo(self, symbol: str, ipo_date: datetime, exchange: str):
        """Emit NewIPOEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.NEW_IPO,
            symbol=symbol,
            priority=EventPriority.HIGH,
            data={
                "ipo_date": ipo_date.isoformat(),
                "exchange": exchange
            }
        )
        self.publish(event)
    
    def emit_symbol_changed(self, symbol: str, old_symbol: str, new_symbol: str):
        """Emit SymbolChangedEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.SYMBOL_CHANGED,
            symbol=new_symbol,
            priority=EventPriority.HIGH,
            data={
                "old_symbol": old_symbol,
                "new_symbol": new_symbol
            }
        )
        self.publish(event)
    
    def emit_liquidity_deterioration(self, symbol: str, current_volume: int, avg_volume: int):
        """Emit LiquidityDeteriorationEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.LIQUIDITY_DETERIORATION,
            symbol=symbol,
            priority=EventPriority.MEDIUM,
            data={
                "current_volume": current_volume,
                "avg_volume": avg_volume,
                "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 0
            }
        )
        self.publish(event)
    
    def emit_sector_migration(self, symbol: str, old_sector: str, new_sector: str):
        """Emit SectorMigrationEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.SECTOR_MIGRATION,
            symbol=symbol,
            priority=EventPriority.MEDIUM,
            data={
                "old_sector": old_sector,
                "new_sector": new_sector
            }
        )
        self.publish(event)
    
    def emit_new_high_rs(self, symbol: str, rs_value: float, benchmark: str):
        """Emit NewHighRSEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.NEW_HIGH_RS,
            symbol=symbol,
            priority=EventPriority.HIGH,
            data={
                "rs_value": rs_value,
                "benchmark": benchmark
            }
        )
        self.publish(event)
    
    def emit_universe_coverage_gap(self, missing_sectors: List[str]):
        """Emit UniverseCoverageGapEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.UNIVERSE_COVERAGE_GAP,
            symbol="",
            priority=EventPriority.HIGH,
            data={
                "missing_sectors": missing_sectors
            }
        )
        self.publish(event)
    
    def emit_tier_promotion(self, symbol: str, old_tier: str, new_tier: str):
        """Emit TierPromotionEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.TIER_PROMOTION,
            symbol=symbol,
            priority=EventPriority.MEDIUM,
            data={
                "old_tier": old_tier,
                "new_tier": new_tier
            }
        )
        self.publish(event)
    
    def emit_tier_demotion(self, symbol: str, old_tier: str, new_tier: str):
        """Emit TierDemotionEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.TIER_DEMOTION,
            symbol=symbol,
            priority=EventPriority.MEDIUM,
            data={
                "old_tier": old_tier,
                "new_tier": new_tier
            }
        )
        self.publish(event)
    
    def emit_delisted(self, symbol: str, reason: str):
        """Emit DelistedEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.DELISTED,
            symbol=symbol,
            priority=EventPriority.HIGH,
            data={
                "reason": reason
            }
        )
        self.publish(event)
    
    def emit_universe_refresh_complete(self, total_tickers: int, new_tickers: int):
        """Emit UniverseRefreshCompleteEvent"""
        event = UniverseEvent(
            event_type=UniverseEventType.UNIVERSE_REFRESH_COMPLETE,
            symbol="",
            priority=EventPriority.LOW,
            data={
                "total_tickers": total_tickers,
                "new_tickers": new_tickers
            }
        )
        self.publish(event)


# Global universe event bus instance
universe_event_bus = UniverseEventBus()
