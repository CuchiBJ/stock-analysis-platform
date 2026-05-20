"""
Event Priority System

Event prioritization with intelligent routing.
HIGH: Immediate processing, frontend notification
MEDIUM: Processed within 1 second
LOW: Batched processing
BACKGROUND: Processed when system idle
"""

import asyncio
import logging
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from dataclasses import dataclass

from app.market_data.events.event_bus import MarketEvent, EventPriority

logger = logging.getLogger(__name__)


@dataclass
class PriorityRoute:
    """Priority routing configuration"""
    priority: EventPriority
    max_latency_ms: int
    batch_size: int
    requires_notification: bool


class EventPriorityRouter:
    """
    Event Priority Router
    
    Routes events based on priority:
    - HIGH: Immediate processing, frontend notification
    - MEDIUM: Processed within 1 second
    - LOW: Batched processing
    - BACKGROUND: Processed when system idle
    """
    
    def __init__(self):
        # Priority configurations
        self._priority_configs: Dict[EventPriority, PriorityRoute] = {
            EventPriority.HIGH: PriorityRoute(
                priority=EventPriority.HIGH,
                max_latency_ms=100,
                batch_size=1,
                requires_notification=True
            ),
            EventPriority.MEDIUM: PriorityRoute(
                priority=EventPriority.MEDIUM,
                max_latency_ms=1000,
                batch_size=10,
                requires_notification=True
            ),
            EventPriority.LOW: PriorityRoute(
                priority=EventPriority.LOW,
                max_latency_ms=5000,
                batch_size=50,
                requires_notification=False
            ),
            EventPriority.BACKGROUND: PriorityRoute(
                priority=EventPriority.BACKGROUND,
                max_latency_ms=30000,
                batch_size=100,
                requires_notification=False
            )
        }
        
        # Priority queues
        self._queues: Dict[EventPriority, asyncio.Queue] = {
            EventPriority.HIGH: asyncio.Queue(),
            EventPriority.MEDIUM: asyncio.Queue(),
            EventPriority.LOW: asyncio.Queue(),
            EventPriority.BACKGROUND: asyncio.Queue()
        }
        
        # Event handlers by priority
        self._handlers: Dict[EventPriority, List[Callable]] = {
            EventPriority.HIGH: [],
            EventPriority.MEDIUM: [],
            EventPriority.LOW: [],
            EventPriority.BACKGROUND: []
        }
        
        # Notification handlers
        self._notification_handlers: List[Callable] = []
        
        # Statistics
        self._event_counts: Dict[EventPriority, int] = {
            EventPriority.HIGH: 0,
            EventPriority.MEDIUM: 0,
            EventPriority.LOW: 0,
            EventPriority.BACKGROUND: 0
        }
        
        # Processing
        self._running = False
        self._processor_tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Start the priority router."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting event priority router")
        
        # Start processor for each priority level
        self._processor_tasks = [
            asyncio.create_task(self._process_priority(EventPriority.HIGH)),
            asyncio.create_task(self._process_priority(EventPriority.MEDIUM)),
            asyncio.create_task(self._process_priority(EventPriority.LOW)),
            asyncio.create_task(self._process_priority(EventPriority.BACKGROUND))
        ]
    
    async def stop(self):
        """Stop the priority router."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping event priority router")
        
        for task in self._processor_tasks:
            task.cancel()
        
        await asyncio.gather(*self._processor_tasks, return_exceptions=True)
        self._processor_tasks.clear()
    
    async def route_event(self, event: MarketEvent):
        """
        Route event to appropriate priority queue.
        
        Args:
            event: Market event to route
        """
        priority = event.priority
        config = self._priority_configs[priority]
        
        # Add to appropriate queue
        await self._queues[priority].put(event)
        
        # Update statistics
        self._event_counts[priority] += 1
        
        # Log if high priority
        if priority == EventPriority.HIGH:
            logger.info(f"Routing HIGH priority event: {event.event_type} for {event.symbol}")
    
    def add_handler(self, priority: EventPriority, handler: Callable):
        """
        Add handler for specific priority level.
        
        Args:
            priority: Priority level
            handler: Handler function
        """
        self._handlers[priority].append(handler)
    
    def add_notification_handler(self, handler: Callable):
        """
        Add notification handler for events that require notification.
        
        Args:
            handler: Notification handler function
        """
        self._notification_handlers.append(handler)
    
    async def _process_priority(self, priority: EventPriority):
        """
        Process events for a specific priority level.
        
        Args:
            priority: Priority level to process
        """
        config = self._priority_configs[priority]
        queue = self._queues[priority]
        
        logger.info(f"Starting processor for {priority.value} priority")
        
        while self._running:
            try:
                # Get event with timeout
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=config.max_latency_ms / 1000.0
                    )
                except asyncio.TimeoutError:
                    # No events within latency window
                    continue
                
                # Process event
                await self._process_event(event, config)
                
            except Exception as e:
                logger.error(f"Error processing {priority.value} priority event: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_event(self, event: MarketEvent, config: PriorityRoute):
        """
        Process a single event.
        
        Args:
            event: Market event
            config: Priority configuration
        """
        # Call priority-specific handlers
        for handler in self._handlers[event.priority]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in {event.priority.value} priority handler: {e}")
        
        # Send notification if required
        if config.requires_notification:
            await self._send_notification(event)
    
    async def _send_notification(self, event: MarketEvent):
        """
        Send notification for event.
        
        Args:
            event: Market event
        """
        for handler in self._notification_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get priority router statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "running": self._running,
            "event_counts": {p.value: count for p, count in self._event_counts.items()},
            "queue_sizes": {p.value: q.qsize() for p, q in self._queues.items()},
            "handlers": {p.value: len(h) for p, h in self._handlers.items()},
            "notification_handlers": len(self._notification_handlers)
        }
    
    def get_priority_config(self, event_type: str) -> EventPriority:
        """
        Get priority for a specific event type.
        
        Args:
            event_type: Event type string
            
        Returns:
            Event priority
        """
        # HIGH priority events
        high_priority_events = [
            "reclaim_strengthening",
            "leadership_deterioration",
            "regime_shift",
            "failed_continuation",
            "sector_rotation"
        ]
        
        # MEDIUM priority events
        medium_priority_events = [
            "rs_improving",
            "volume_dry_up",
            "setup_state_change"
        ]
        
        # LOW priority events
        low_priority_events = [
            "aggregate_update"
        ]
        
        # BACKGROUND priority events
        background_priority_events = [
            "data_refresh",
            "cache_update"
        ]
        
        if event_type in high_priority_events:
            return EventPriority.HIGH
        elif event_type in medium_priority_events:
            return EventPriority.MEDIUM
        elif event_type in low_priority_events:
            return EventPriority.LOW
        elif event_type in background_priority_events:
            return EventPriority.BACKGROUND
        else:
            return EventPriority.MEDIUM  # Default


# Global priority router instance
priority_router = EventPriorityRouter()
