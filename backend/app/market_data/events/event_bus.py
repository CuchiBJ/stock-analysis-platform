"""
Internal Event System

Event bus for internal communication within the market data system.
Handles event publishing, subscribing, filtering, routing, and history.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Callable, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid
import json
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels"""
    HIGH = "high"           # Immediate processing, frontend notification
    MEDIUM = "medium"       # Processed within 1 second
    LOW = "low"             # Batched processing
    BACKGROUND = "background"  # Processed when system idle


class MarketEventType(Enum):
    """Types of market events"""
    PRICE_BREAK = "price_break"
    EMA21_LOST = "ema21_lost"
    RECLAIM_ATTEMPT = "reclaim_attempt"
    RS_IMPROVING = "rs_improving"
    VOLUME_DRY_UP = "volume_dry_up"
    SECTOR_LEADERSHIP_SHIFT = "sector_leadership_shift"
    SETUP_DETERIORATION = "setup_deterioration"
    TRANSITION_STRENGTHENING = "transition_strengthening"
    REGIME_SHIFT = "regime_shift"
    BREADTH_CHANGE = "breadth_change"
    AGGREGATE_UPDATE = "aggregate_update"
    SETUP_STATE_CHANGE = "setup_state_change"
    TRANSITION_DETECTED = "transition_detected"


@dataclass
class MarketEvent:
    """Internal market event"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: EventPriority = EventPriority.MEDIUM
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "data": self.data,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketEvent':
        """Create event from dictionary"""
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            symbol=data["symbol"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=EventPriority(data["priority"]),
            data=data["data"],
            metadata=data["metadata"]
        )


class EventBus:
    """
    Internal event bus for market data system.
    
    Handles:
    - Event publishing
    - Event subscribing
    - Event filtering
    - Event routing
    - Event history tracking
    - Priority-based processing
    """
    
    def __init__(self):
        # Subscribers by event type
        self._subscribers: Dict[str, Set[Callable]] = defaultdict(set)
        
        # Global subscribers (receive all events)
        self._global_subscribers: Set[Callable] = set()
        
        # Event history (in-memory, can be persisted to Redis)
        self._event_history: List[MarketEvent] = []
        self._max_history_size = 10000
        
        # Priority queues
        self._high_priority_queue: asyncio.Queue = asyncio.Queue()
        self._medium_priority_queue: asyncio.Queue = asyncio.Queue()
        self._low_priority_queue: asyncio.Queue = asyncio.Queue()
        self._background_queue: asyncio.Queue = asyncio.Queue()
        
        # Event statistics
        self._event_counts: Dict[str, int] = defaultdict(int)
        self._total_events = 0
        
        # Processing
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the event bus processor."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting event bus")
        
        # Start background processor
        self._processor_task = asyncio.create_task(self._process_events())
    
    async def stop(self):
        """Stop the event bus processor."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping event bus")
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
    
    async def publish(self, event: MarketEvent):
        """
        Publish an event to the bus.
        
        Args:
            event: MarketEvent to publish
        """
        # Add to history
        self._add_to_history(event)
        
        # Update statistics
        self._event_counts[event.event_type] += 1
        self._total_events += 1
        
        # Route to appropriate priority queue
        if event.priority == EventPriority.HIGH:
            await self._high_priority_queue.put(event)
        elif event.priority == EventPriority.MEDIUM:
            await self._medium_priority_queue.put(event)
        elif event.priority == EventPriority.LOW:
            await self._low_priority_queue.put(event)
        else:
            await self._background_queue.put(event)
        
        logger.debug(f"Published event: {event.event_type} for {event.symbol} (priority: {event.priority.value})")
    
    def subscribe(self, event_type: str, handler: Callable[[MarketEvent], None]):
        """
        Subscribe to a specific event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Handler function to call when event is published
        """
        self._subscribers[event_type].add(handler)
        logger.debug(f"Subscribed to {event_type}")
    
    def unsubscribe(self, event_type: str, handler: Callable[[MarketEvent], None]):
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed from {event_type}")
    
    def subscribe_global(self, handler: Callable[[MarketEvent], None]):
        """
        Subscribe to all events.
        
        Args:
            handler: Handler function to call for all events
        """
        self._global_subscribers.add(handler)
        logger.debug("Subscribed to all events")
    
    def unsubscribe_global(self, handler: Callable[[MarketEvent], None]):
        """
        Unsubscribe from all events.
        
        Args:
            handler: Handler function to remove
        """
        if handler in self._global_subscribers:
            self._global_subscribers.remove(handler)
            logger.debug("Unsubscribed from all events")
    
    async def _process_events(self):
        """Process events from priority queues."""
        logger.info("Starting event processor")
        
        while self._running:
            try:
                # Process high priority first
                if not self._high_priority_queue.empty():
                    event = await self._high_priority_queue.get()
                    await self._deliver_event(event)
                    continue
                
                # Process medium priority
                if not self._medium_priority_queue.empty():
                    event = await self._medium_priority_queue.get()
                    await self._deliver_event(event)
                    continue
                
                # Process low priority (batched)
                if not self._low_priority_queue.empty():
                    events = []
                    while not self._low_priority_queue.empty() and len(events) < 10:
                        events.append(await self._low_priority_queue.get())
                    
                    for event in events:
                        await self._deliver_event(event)
                    continue
                
                # Process background when idle
                if not self._background_queue.empty():
                    event = await self._background_queue.get()
                    await self._deliver_event(event)
                    continue
                
                # Small sleep if no events
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error processing events: {e}")
                await asyncio.sleep(0.1)
    
    async def _deliver_event(self, event: MarketEvent):
        """Deliver event to subscribers."""
        # Deliver to type-specific subscribers
        for handler in self._subscribers[event.event_type]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type}: {e}")
        
        # Deliver to global subscribers
        for handler in self._global_subscribers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {e}")
    
    def _add_to_history(self, event: MarketEvent):
        """Add event to history."""
        self._event_history.append(event)
        
        # Maintain max history size
        if len(self._event_history) > self._max_history_size:
            self._event_history = self._event_history[-self._max_history_size:]
    
    def get_event_history(
        self,
        event_type: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[MarketEvent]:
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
        """Get event bus statistics."""
        return {
            "total_events": self._total_events,
            "event_counts": dict(self._event_counts),
            "history_size": len(self._event_history),
            "subscribers": {
                event_type: len(handlers)
                for event_type, handlers in self._subscribers.items()
            },
            "global_subscribers": len(self._global_subscribers),
            "queue_sizes": {
                "high": self._high_priority_queue.qsize(),
                "medium": self._medium_priority_queue.qsize(),
                "low": self._low_priority_queue.qsize(),
                "background": self._background_queue.qsize()
            }
        }


# Global event bus instance
event_bus = EventBus()
