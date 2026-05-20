"""
DataSource Manager with Auto Fallback

Manages multiple data sources with automatic fallback and graceful degradation.
Provides provider-agnostic interface for the rest of the system.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, AsyncIterator, Callable
from datetime import datetime
from enum import Enum

from app.market_data.strategies.data_source_strategy import (
    DataSourceStrategy,
    DataSourceType,
    DataSourceStatus,
    NormalizedPriceEvent,
    WebSocketDataSource,
    SmartPollingDataSource
)

logger = logging.getLogger(__name__)


class DataSourceMode(Enum):
    """Operating mode of data source manager"""
    WEBSOCKET = "websocket"
    POLLING = "polling"
    DEGRADED = "degraded"


class DataSourceManager:
    """
    Data Source Manager with Auto Fallback
    
    Manages multiple data sources with automatic fallback:
    - Primary: WebSocket (low latency, real-time)
    - Fallback: Smart Polling (tier-based intervals)
    - Degraded: Extended polling intervals on repeated failures
    
    Features:
    - Automatic fallback on WebSocket failure
    - Graceful degradation
    - Provider-agnostic interface
    - Same normalized event flow
    - Health monitoring
    """
    
    def __init__(
        self,
        websocket_source: Optional[WebSocketDataSource] = None,
        polling_source: Optional[SmartPollingDataSource] = None
    ):
        self.websocket_source = websocket_source
        self.polling_source = polling_source
        
        # Current active source
        self._active_source: Optional[DataSourceStrategy] = None
        self._mode = DataSourceMode.POLLING  # Default to polling (no WebSocket dependency)
        
        # State
        self._running = False
        self._symbols: List[str] = []
        
        # Fallback configuration
        self._fallback_attempts = 0
        self._max_fallback_attempts = 5
        self._fallback_backoff = 30  # seconds
        
        # Health monitoring
        self._last_health_check: Optional[datetime] = None
        self._health_check_interval = 60  # seconds
        
        # Statistics
        self._websocket_success_count = 0
        self._websocket_failure_count = 0
        self._polling_success_count = 0
        self._polling_failure_count = 0
        
        # Event handlers
        self._mode_change_handlers: List[Callable[[DataSourceMode], None]] = []
    
    async def start(self, symbols: List[str]):
        """
        Start data source manager.
        
        Args:
            symbols: List of symbols to track
        """
        if self._running:
            logger.warning("DataSourceManager already running")
            return
        
        self._symbols = symbols
        self._running = True
        
        logger.info(f"Starting DataSourceManager for {len(symbols)} symbols")
        
        # Try WebSocket first if available
        if self.websocket_source:
            websocket_connected = await self.websocket_source.connect(symbols)
            
            if websocket_connected:
                self._active_source = self.websocket_source
                self._mode = DataSourceMode.WEBSOCKET
                logger.info("Using WebSocket as primary data source")
                self._notify_mode_change(DataSourceMode.WEBSOCKET)
            else:
                logger.warning("WebSocket connection failed, falling back to polling")
                await self._fallback_to_polling()
        else:
            # No WebSocket available, use polling
            await self._fallback_to_polling()
    
    async def stop(self):
        """Stop data source manager."""
        if not self._running:
            return
        
        logger.info("Stopping DataSourceManager")
        self._running = False
        
        # Disconnect active source
        if self._active_source:
            await self._active_source.disconnect()
            self._active_source = None
    
    async def stream_prices(self) -> AsyncIterator[NormalizedPriceEvent]:
        """
        Stream price updates from active data source.
        
        Yields:
            NormalizedPriceEvent objects
        """
        if not self._active_source:
            logger.error("No active data source")
            return
        
        logger.info(f"Streaming prices from {self._active_source.name} for {len(self._symbols)} symbols")
        
        try:
            event_count = 0
            logger.info(f"Starting async for loop in stream_prices...")
            async for event in self._active_source.stream_prices(self._symbols):
                if not self._running:
                    logger.info("Stream stopped by _running flag")
                    break
                
                event_count += 1
                if event_count == 1:
                    logger.info(f"First event received from {self._active_source.name}: {event.symbol}")
                
                yield event
        
        except Exception as e:
            logger.error(f"Error streaming prices: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Attempt fallback on error
            if self._mode == DataSourceMode.WEBSOCKET:
                logger.warning("WebSocket stream error, attempting fallback")
                await self._fallback_to_polling()
        
        logger.info(f"Stream ended, total events: {event_count}")
    
    async def get_price_snapshot(self) -> Dict[str, NormalizedPriceEvent]:
        """
        Get current price snapshot.
        
        Returns:
            Dictionary mapping symbol to NormalizedPriceEvent
        """
        if not self._active_source:
            logger.error("No active data source")
            return {}
        
        try:
            snapshot = await self._active_source.get_price_snapshot(self._symbols)
            
            if self._mode == DataSourceMode.WEBSOCKET:
                self._websocket_success_count += 1
            else:
                self._polling_success_count += 1
            
            return snapshot
        
        except Exception as e:
            logger.error(f"Error getting price snapshot: {e}")
            
            if self._mode == DataSourceMode.WEBSOCKET:
                self._websocket_failure_count += 1
            else:
                self._polling_failure_count += 1
            
            # Attempt fallback on error
            if self._mode == DataSourceMode.WEBSOCKET:
                await self._fallback_to_polling()
            
            return {}
    
    async def _fallback_to_polling(self):
        """Fallback to polling data source."""
        if not self.polling_source:
            logger.error("No polling source available for fallback")
            self._mode = DataSourceMode.DEGRADED
            self._notify_mode_change(DataSourceMode.DEGRADED)
            return
        
        logger.info("Falling back to polling data source")
        
        # Disconnect WebSocket if connected
        if self.websocket_source:
            await self.websocket_source.disconnect()
        
        # Connect polling source
        polling_connected = await self.polling_source.connect(self._symbols)
        
        if polling_connected:
            self._active_source = self.polling_source
            self._mode = DataSourceMode.POLLING
            self._notify_mode_change(DataSourceMode.POLLING)
            self._fallback_attempts = 0
            logger.info("Successfully switched to polling data source")
        else:
            logger.error("Polling connection failed, entering degraded mode")
            self._mode = DataSourceMode.DEGRADED
            self._notify_mode_change(DataSourceMode.DEGRADED)
    
    async def _attempt_websocket_recovery(self):
        """Attempt to recover WebSocket connection."""
        if not self.websocket_source:
            return
        
        if self._fallback_attempts >= self._max_fallback_attempts:
            logger.warning("Max fallback attempts reached, not attempting WebSocket recovery")
            return
        
        self._fallback_attempts += 1
        backoff = self._fallback_backoff * (2 ** (self._fallback_attempts - 1))
        
        logger.info(f"Attempting WebSocket recovery (attempt {self._fallback_attempts}/{self._max_fallback_attempts})")
        
        await asyncio.sleep(backoff)
        
        websocket_connected = await self.websocket_source.connect(self._symbols)
        
        if websocket_connected:
            logger.info("WebSocket recovery successful, switching back to WebSocket")
            await self.polling_source.disconnect()
            self._active_source = self.websocket_source
            self._mode = DataSourceMode.WEBSOCKET
            self._notify_mode_change(DataSourceMode.WEBSOCKET)
            self._fallback_attempts = 0
    
    def add_mode_change_handler(self, handler: Callable[[DataSourceMode], None]):
        """Add handler for mode changes."""
        self._mode_change_handlers.append(handler)
    
    def _notify_mode_change(self, mode: DataSourceMode):
        """Notify all mode change handlers."""
        for handler in self._mode_change_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(mode))
                else:
                    handler(mode)
            except Exception as e:
                logger.error(f"Error in mode change handler: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Dictionary with health information
        """
        self._last_health_check = datetime.utcnow()
        
        health = {
            "mode": self._mode.value,
            "running": self._running,
            "active_source": self._active_source.name if self._active_source else None,
            "active_source_status": self._active_source.status.value if self._active_source else None,
            "symbols_count": len(self._symbols),
            "websocket_available": self.websocket_source is not None,
            "polling_available": self.polling_source is not None,
            "websocket_health": self.websocket_source.is_healthy() if self.websocket_source else None,
            "polling_health": self.polling_source.is_healthy() if self.polling_source else None,
            "statistics": {
                "websocket_success_count": self._websocket_success_count,
                "websocket_failure_count": self._websocket_failure_count,
                "polling_success_count": self._polling_success_count,
                "polling_failure_count": self._polling_failure_count,
            },
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None
        }
        
        return health
    
    @property
    def mode(self) -> DataSourceMode:
        """Get current operating mode."""
        return self._mode
    
    @property
    def active_source(self) -> Optional[DataSourceStrategy]:
        """Get active data source."""
        return self._active_source
    
    def is_websocket_mode(self) -> bool:
        """Check if currently in WebSocket mode."""
        return self._mode == DataSourceMode.WEBSOCKET
    
    def is_polling_mode(self) -> bool:
        """Check if currently in polling mode."""
        return self._mode == DataSourceMode.POLLING
    
    def is_degraded_mode(self) -> bool:
        """Check if currently in degraded mode."""
        return self._mode == DataSourceMode.DEGRADED
