"""
Normalized Event Bus

Internal event bus for normalized price events.
Provider-agnostic - consumers don't know if data comes from WebSocket or polling.
"""

import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional, Set
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import json

from app.market_data.strategies.data_source_strategy import NormalizedPriceEvent, DataSourceType

logger = logging.getLogger(__name__)


class NormalizedEventType(Enum):
    """Types of normalized events"""
    PRICE_UPDATE = "price_update"
    PRICE_SNAPSHOT = "price_snapshot"
    DATA_SOURCE_CHANGE = "data_source_change"
    HEALTH_UPDATE = "health_update"


@dataclass
class NormalizedEvent:
    """Internal normalized event"""
    event_type: NormalizedEventType
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata or {}
        }


class NormalizedEventBus:
    """
    Normalized Event Bus
    
    Internal event bus for normalized price events.
    Provider-agnostic - consumers don't know if data comes from WebSocket or polling.
    
    Features:
    - Subscription-based event delivery
    - Event filtering
    - Event history
    - Statistics
    - Provider-agnostic interface
    """
    
    def __init__(self):
        # Subscribers: {event_type: Set[handlers]}
        self._subscribers: Dict[NormalizedEventType, Set[Callable]] = {}
        
        # Event history (last 1000 events)
        self._event_history: List[NormalizedEvent] = []
        self._max_history_size = 1000
        
        # Statistics
        self._event_counts: Dict[NormalizedEventType, int] = {}
        self._total_events = 0
        self._start_time: Optional[datetime] = None
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def emit_price_update(self, event: NormalizedPriceEvent):
        """
        Emit price update event.
        
        Args:
            event: Normalized price event
        """
        normalized_event = NormalizedEvent(
            event_type=NormalizedEventType.PRICE_UPDATE,
            timestamp=datetime.utcnow(),
            data=event.to_dict(),
            metadata={"source_type": event.source_type.value}
        )
        
        await self._emit(normalized_event)
    
    async def emit_price_snapshot(self, snapshot: Dict[str, NormalizedPriceEvent]):
        """
        Emit price snapshot event.
        
        Args:
            snapshot: Dictionary mapping symbol to NormalizedPriceEvent
        """
        normalized_event = NormalizedEvent(
            event_type=NormalizedEventType.PRICE_SNAPSHOT,
            timestamp=datetime.utcnow(),
            data={
                symbol: event.to_dict()
                for symbol, event in snapshot.items()
            },
            metadata={"symbol_count": len(snapshot)}
        )
        
        await self._emit(normalized_event)
    
    async def emit_data_source_change(self, mode: str, source_name: str):
        """
        Emit data source change event.
        
        Args:
            mode: New operating mode (websocket/polling/degraded)
            source_name: Name of the data source
        """
        normalized_event = NormalizedEvent(
            event_type=NormalizedEventType.DATA_SOURCE_CHANGE,
            timestamp=datetime.utcnow(),
            data={
                "mode": mode,
                "source_name": source_name
            }
        )
        
        await self._emit(normalized_event)
    
    async def emit_health_update(self, health: Dict[str, Any]):
        """
        Emit health update event.
        
        Args:
            health: Health status dictionary
        """
        normalized_event = NormalizedEvent(
            event_type=NormalizedEventType.HEALTH_UPDATE,
            timestamp=datetime.utcnow(),
            data=health
        )
        
        await self._emit(normalized_event)
    
    async def _emit(self, event: NormalizedEvent):
        """
        Emit event to subscribers.
        
        Args:
            event: Normalized event
        """
        async with self._lock:
            # Update statistics
            if self._start_time is None:
                self._start_time = datetime.utcnow()
            
            self._total_events += 1
            self._event_counts[event.event_type] = self._event_counts.get(event.event_type, 0) + 1
            
            # Add to history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history_size:
                self._event_history.pop(0)
        
        # Deliver to subscribers
        subscribers = self._subscribers.get(event.event_type, set())
        
        for subscriber in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(event)
                else:
                    subscriber(event)
            except Exception as e:
                logger.error(f"Error in event subscriber: {e}")
    
    def subscribe(self, event_type: NormalizedEventType, handler: Callable):
        """
        Subscribe to event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Handler function
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = set()
        
        self._subscribers[event_type].add(handler)
        logger.info(f"Subscribed to {event_type.value}")
    
    def unsubscribe(self, event_type: NormalizedEventType, handler: Callable):
        """
        Unsubscribe from event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function
        """
        if event_type in self._subscribers:
            self._subscribers[event_type].discard(handler)
            logger.info(f"Unsubscribed from {event_type.value}")
    
    def get_history(self, event_type: Optional[NormalizedEventType] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type (optional)
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        events = events[-limit:]
        
        return [event.to_dict() for event in events]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get event statistics.
        
        Returns:
            Dictionary with statistics
        """
        uptime = None
        if self._start_time:
            uptime = (datetime.utcnow() - self._start_time).total_seconds()
        
        return {
            "total_events": self._total_events,
            "event_counts": {
                event_type.value: count
                for event_type, count in self._event_counts.items()
            },
            "subscribers": {
                event_type.value: len(handlers)
                for event_type, handlers in self._subscribers.items()
            },
            "history_size": len(self._event_history),
            "uptime_seconds": uptime,
            "events_per_second": self._total_events / uptime if uptime and uptime > 0 else 0
        }
    
    def clear_history(self):
        """Clear event history."""
        self._event_history.clear()
        logger.info("Event history cleared")
    
    def reset_statistics(self):
        """Reset statistics."""
        self._event_counts.clear()
        self._total_events = 0
        self._start_time = None
        logger.info("Statistics reset")


# Global normalized event bus instance
_normalized_event_bus: Optional[NormalizedEventBus] = None


def get_normalized_event_bus() -> NormalizedEventBus:
    """
    Get global normalized event bus instance.
    
    Returns:
        NormalizedEventBus instance
    """
    global _normalized_event_bus
    
    if _normalized_event_bus is None:
        _normalized_event_bus = NormalizedEventBus()
    
    return _normalized_event_bus
