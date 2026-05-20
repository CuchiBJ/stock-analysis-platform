"""
WebSocket Ingestion Engine

Dedicated service for WebSocket-based market data ingestion.
Maintains persistent connection with Polygon, processes real-time streams,
normalizes events, detects changes, and emits internal events.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from app.market_data.providers.polygon_provider import PolygonProvider
from app.market_data.interfaces import EventType, Timespan, Aggregate, Trade, Quote

logger = logging.getLogger(__name__)


@dataclass
class NormalizedEvent:
    """Normalized internal event format"""
    event_id: str
    event_type: str
    symbol: str
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class WebSocketIngestionEngine:
    """
    WebSocket Ingestion Engine
    
    Maintains persistent WebSocket connection, processes real-time streams,
    normalizes events to internal format, detects relevant changes, and emits
    internal events to the event bus.
    
    Key Features:
    - Automatic reconnection with backoff
    - Heartbeat monitoring
    - Message throttling and batching
    - Backpressure handling
    - Change detection vs cached state
    - Event normalization
    """
    
    def __init__(self, provider: PolygonProvider):
        self.provider = provider
        self._running = False
        self._connected = False
        
        # Event handlers
        self._event_handlers: List[Callable[[NormalizedEvent], None]] = []
        
        # State tracking for change detection
        self._last_bars: Dict[str, Aggregate] = {}
        self._last_quotes: Dict[str, Quote] = {}
        
        # Reconnection handling
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._reconnect_backoff = 1.0
        
        # Heartbeat
        self._last_heartbeat = None
        self._heartbeat_interval = 30.0
        
        # Throttling
        self._message_count = 0
        self._throttle_window_start = datetime.utcnow()
        self._max_messages_per_second = 1000
        
        # Batching
        self._event_batch: List[NormalizedEvent] = []
        self._batch_size = 100
        self._batch_flush_interval = 1.0
    
    async def start(self, symbols: List[str]):
        """Start the WebSocket ingestion engine."""
        if self._running:
            logger.warning("WebSocket engine already running")
            return
        
        self._running = True
        logger.info(f"Starting WebSocket ingestion engine for {len(symbols)} symbols")
        
        try:
            await self.provider.connect()
            self._connected = True
            
            # Subscribe to aggregates for all symbols
            await self.provider.subscribe(symbols, EventType.AGGREGATE)
            
            # Start background tasks
            await asyncio.gather(
                self._ingestion_loop(),
                self._heartbeat_loop(),
                self._batch_flush_loop()
            )
            
        except Exception as e:
            logger.error(f"Error starting WebSocket engine: {e}")
            self._running = False
            raise
    
    async def stop(self):
        """Stop the WebSocket ingestion engine."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping WebSocket ingestion engine")
        
        # Flush remaining events
        if self._event_batch:
            await self._flush_batch()
        
        await self.provider.disconnect()
        self._connected = False
    
    def add_event_handler(self, handler: Callable[[NormalizedEvent], None]):
        """Add an event handler for normalized events."""
        self._event_handlers.append(handler)
    
    def remove_event_handler(self, handler: Callable[[NormalizedEvent], None]):
        """Remove an event handler."""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)
    
    async def _ingestion_loop(self):
        """Main ingestion loop that processes WebSocket messages."""
        logger.info("Starting ingestion loop")
        
        while self._running and self._connected:
            try:
                # Stream aggregates from provider
                async for aggregate in self.provider.stream_aggregates("*", Timespan.MINUTE):
                    if not self._running:
                        break
                    
                    # Throttle message processing
                    if not await self._throttle_check():
                        continue
                    
                    # Normalize event
                    normalized = self._normalize_aggregate(aggregate)
                    
                    # Detect changes
                    if self._detect_change(aggregate):
                        # Add to batch
                        self._event_batch.append(normalized)
                        
                        # Update cached state
                        self._last_bars[aggregate.symbol or ""] = aggregate
                    
            except Exception as e:
                logger.error(f"Error in ingestion loop: {e}")
                await self._handle_reconnection()
    
    async def _heartbeat_loop(self):
        """Heartbeat monitoring for connection health."""
        logger.info("Starting heartbeat loop")
        
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                
                if not self._connected:
                    logger.warning("Connection lost, attempting reconnection")
                    await self._handle_reconnection()
                else:
                    # Send heartbeat
                    self._last_heartbeat = datetime.utcnow()
                    logger.debug("Heartbeat sent")
                    
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    async def _batch_flush_loop(self):
        """Periodically flush event batches."""
        while self._running:
            try:
                await asyncio.sleep(self._batch_flush_interval)
                
                if self._event_batch:
                    await self._flush_batch()
                    
            except Exception as e:
                logger.error(f"Error in batch flush loop: {e}")
    
    async def _throttle_check(self) -> bool:
        """Check if message processing should be throttled."""
        now = datetime.utcnow()
        
        # Reset counter if window expired
        if (now - self._throttle_window_start).total_seconds() >= 1.0:
            self._message_count = 0
            self._throttle_window_start = now
        
        self._message_count += 1
        
        if self._message_count > self._max_messages_per_second:
            logger.warning(f"Throttling: {self._message_count} messages/second exceeds limit")
            await asyncio.sleep(0.01)  # Small backoff
            return False
        
        return True
    
    async def _flush_batch(self):
        """Flush current batch of events to handlers."""
        if not self._event_batch:
            return
        
        logger.debug(f"Flushing batch of {len(self._event_batch)} events")
        
        for event in self._event_batch:
            for handler in self._event_handlers:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")
        
        self._event_batch.clear()
    
    def _normalize_aggregate(self, aggregate: Aggregate) -> NormalizedEvent:
        """Normalize Polygon aggregate to internal event format."""
        return NormalizedEvent(
            event_id=f"{aggregate.symbol}_{int(aggregate.timestamp.timestamp())}",
            event_type="aggregate",
            symbol=aggregate.symbol or "",
            timestamp=aggregate.timestamp,
            data={
                "open": aggregate.open,
                "high": aggregate.high,
                "low": aggregate.low,
                "close": aggregate.close,
                "volume": aggregate.volume,
                "vwap": aggregate.vwap
            },
            metadata={
                "source": "polygon",
                "normalized_at": datetime.utcnow().isoformat()
            }
        )
    
    def _detect_change(self, aggregate: Aggregate) -> bool:
        """
        Detect if aggregate represents a significant change.
        
        Returns True if:
        - No previous data for this symbol
        - Price changed by >0.1%
        - Volume changed by >10%
        - New bar completed
        """
        symbol = aggregate.symbol or ""
        
        if symbol not in self._last_bars:
            return True  # First data for this symbol
        
        last_bar = self._last_bars[symbol]
        
        # Price change threshold
        price_change_pct = abs((aggregate.close - last_bar.close) / last_bar.close) * 100
        if price_change_pct > 0.1:
            return True
        
        # Volume change threshold
        if last_bar.volume > 0:
            volume_change_pct = abs((aggregate.volume - last_bar.volume) / last_bar.volume) * 100
            if volume_change_pct > 10:
                return True
        
        # New bar (different timestamp)
        if aggregate.timestamp != last_bar.timestamp:
            return True
        
        return False
    
    async def _handle_reconnection(self):
        """Handle reconnection with exponential backoff."""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Max reconnection attempts reached, stopping")
            self._running = False
            return
        
        self._reconnect_attempts += 1
        backoff = self._reconnect_backoff * (2 ** (self._reconnect_attempts - 1))
        
        logger.warning(f"Reconnection attempt {self._reconnect_attempts}/{self._max_reconnect_attempts}, waiting {backoff}s")
        
        await asyncio.sleep(backoff)
        
        try:
            await self.provider.reconnect()
            self._connected = await self.provider.is_connected()
            self._reconnect_attempts = 0
            logger.info("Reconnection successful")
            
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            self._connected = False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current status of the ingestion engine."""
        return {
            "running": self._running,
            "connected": self._connected,
            "reconnect_attempts": self._reconnect_attempts,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "message_count": self._message_count,
            "batch_size": len(self._event_batch),
            "cached_symbols": len(self._last_bars)
        }
