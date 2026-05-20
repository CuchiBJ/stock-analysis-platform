"""
Real-time Price Service (Provider-Agnostic with Fallback)

Manages real-time price ingestion using DataSourceStrategy with automatic fallback.
Supports WebSocket (primary) and Smart Polling (fallback).
Provider-agnostic - frontend doesn't know data origin.
"""

import asyncio
import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.market_data.providers.polygon_provider import PolygonProvider
from app.market_data.strategies.data_source_strategy import (
    WebSocketDataSource,
    SmartPollingDataSource,
    DatabasePollingDataSource
)
from app.market_data.strategies.data_source_manager import DataSourceManager, DataSourceMode
from app.market_data.events.normalized_event_bus import (
    get_normalized_event_bus,
    NormalizedEventType
)
from app.services.websocket_manager import websocket_manager
from app.universe.tiers.tier_manager import UniverseTier
from app.market_data.cache.redis_cache import redis_cache

logger = logging.getLogger(__name__)


class RealtimePriceService:
    """
    Real-time Price Service (Provider-Agnostic with Fallback)
    
    Manages:
    - DataSourceManager with WebSocket (primary) and Smart Polling (fallback)
    - NormalizedEventBus for internal events
    - Subscription to TIER 1 symbols from Universe Engine
    - Real-time price updates
    - Broadcasting to frontend clients
    - Graceful degradation
    
    Features:
    - Provider-agnostic (WebSocket or Polling)
    - Automatic fallback on WebSocket failure
    - Tier-based polling intervals
    - Redis caching
    - Request deduplication
    - Stale-while-revalidate
    """
    
    def __init__(self, polygon_api_key: Optional[str] = None):
        """
        Initialize real-time price service.
        
        Args:
            polygon_api_key: Optional Polygon API key for WebSocket
        """
        self._running = False
        self._symbols: List[str] = []
        self._polygon_api_key = polygon_api_key
        
        # Initialize data sources
        self.polygon_provider = PolygonProvider(api_key=polygon_api_key)
        
        # WebSocket source (only if API key available)
        self.websocket_source = WebSocketDataSource(self.polygon_provider) if polygon_api_key else None
        
        # Smart polling source (uses Polygon REST API)
        self.polling_source = SmartPollingDataSource(self.polygon_provider) if polygon_api_key else None
        
        # Database polling source (fallback using historical data)
        self.database_source = DatabasePollingDataSource()
        
        # Event bus for normalized events
        self.event_bus = get_normalized_event_bus()
        
        # Data source manager with fallback architecture
        # Use database source as primary when no API key, otherwise use WebSocket with fallback
        if polygon_api_key:
            self.data_source_manager = DataSourceManager(
                websocket_source=self.websocket_source,
                polling_source=self.polling_source
            )
        else:
            # No API key: use database source directly (no WebSocket dependency)
            self.data_source_manager = DataSourceManager(
                websocket_source=None,
                polling_source=self.database_source
            )
        
        # WebSocket manager for client connections
        self.websocket_manager = websocket_manager
        
        # State
        self._messages_received = 0
        self._messages_broadcast = 0
        self._last_update: Optional[datetime] = None
        self._mode_change_count = 0
    
    async def start(self, symbols: Optional[List[str]] = None):
        """
        Start real-time price service with fallback architecture.
        
        Args:
            symbols: List of symbols to subscribe to (if None, will use TIER 1 from Universe Engine)
        """
        if self._running:
            logger.warning("Real-time price service already running")
            return
        
        logger.info("Starting real-time price service with fallback architecture")
        
        # Connect Redis cache
        if redis_cache:
            await redis_cache.connect()
        
        # Use provided symbols or get TIER 1 from Universe Engine
        if symbols:
            self._symbols = symbols
        else:
            self._symbols = await self._get_tier1_symbols()
        
        if not self._symbols:
            logger.warning("No symbols to subscribe to, service will start but idle")
        
        # Add mode change handler
        self.data_source_manager.add_mode_change_handler(self._handle_mode_change)
        
        # Start DataSource Manager
        try:
            await self.data_source_manager.start(self._symbols)
            self._running = True
            
            # Start price streaming
            logger.info("Creating price streaming task...")
            streaming_task = asyncio.create_task(self._stream_prices())
            logger.info(f"Price streaming task created: {streaming_task}")
            
            logger.info(f"Real-time price service started with {len(self._symbols)} symbols")
            logger.info(f"Data source mode: {self.data_source_manager.mode.value}")
            
            # Broadcast start event
            await websocket_manager.broadcast(
                "realtime_status",
                {
                    "status": "started",
                    "mode": self.data_source_manager.mode.value,
                    "symbols_count": len(self._symbols),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        except Exception as e:
            logger.error(f"Failed to start real-time price service: {e}")
            raise
    
    async def stop(self):
        """Stop real-time price service."""
        if not self._running:
            logger.warning("Real-time price service not running")
            return
        
        logger.info("Stopping real-time price service")
        
        await self.data_source_manager.stop()
        self._running = False
        
        # Disconnect Redis cache
        if redis_cache:
            await redis_cache.disconnect()
        
        # Broadcast stop event
        await websocket_manager.broadcast(
            "realtime_status",
            {
                "status": "stopped",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        logger.info("Real-time price service stopped")
    
    async def _stream_prices(self):
        """Stream prices from DataSource Manager and emit to NormalizedEventBus."""
        try:
            logger.info("Starting price streaming...")
            logger.info(f"Data source manager active source: {self.data_source_manager._active_source.name if self.data_source_manager._active_source else 'None'}")
            
            async for price_event in self.data_source_manager.stream_prices():
                if not self._running:
                    break
                
                self._messages_received += 1
                self._last_update = datetime.utcnow()
                
                logger.debug(f"Received price event for {price_event.symbol}")
                
                # Emit to NormalizedEventBus
                await self.event_bus.emit_price_update(price_event)
                
                # Broadcast to frontend
                await websocket_manager.broadcast(
                    "price_update",
                    {
                        "symbol": price_event.symbol,
                        "timestamp": price_event.timestamp.isoformat(),
                        "open": price_event.open,
                        "high": price_event.high,
                        "low": price_event.low,
                        "close": price_event.close,
                        "volume": price_event.volume,
                        "vwap": price_event.vwap,
                        "source_type": price_event.source_type.value,
                        "metadata": price_event.metadata or {}
                    }
                )
                self._messages_broadcast += 1
        
        except Exception as e:
            logger.error(f"Error streaming prices: {e}")
    
    async def _handle_mode_change(self, mode: DataSourceMode):
        """Handle data source mode changes."""
        self._mode_change_count += 1
        logger.info(f"Data source mode changed to {mode.value} (change #{self._mode_change_count})")
        
        # Emit to NormalizedEventBus
        await self.event_bus.emit_data_source_change(
            mode.value,
            self.data_source_manager.active_source.name if self.data_source_manager.active_source else "none"
        )
        
        # Broadcast to frontend
        await websocket_manager.broadcast(
            "realtime_mode_change",
            {
                "mode": mode.value,
                "source_name": self.data_source_manager.active_source.name if self.data_source_manager.active_source else "none",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    async def _get_tier1_symbols(self) -> List[str]:
        """
        Get TIER 1 symbols directly from database.
        
        Returns:
            List of TIER 1 symbols
        """
        try:
            from sqlalchemy import select, text
            from app.core.deps import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                # Query TIER 1 symbols directly from database
                query = text("""
                    SELECT ii.current_symbol
                    FROM instrument_identities ii
                    JOIN universe_tiers ut ON ii.internal_id = ut.instrument_id
                    WHERE ii.lifecycle_state = 'active'
                    AND ut.tier = 'tier_1'
                """)
                
                result = await db.execute(query)
                tier1_symbols = [row[0] for row in result]
                
                logger.info(f"Retrieved {len(tier1_symbols)} TIER 1 symbols from database")
                return tier1_symbols
        
        except Exception as e:
            logger.error(f"Failed to get TIER 1 symbols: {e}")
            return []
    
    async def add_symbols(self, symbols: List[str]):
        """
        Add symbols to real-time subscription.
        
        Args:
            symbols: List of symbols to add
        """
        if not self._running:
            logger.warning("Real-time price service not running, cannot add symbols")
            return
        
        new_symbols = [s for s in symbols if s not in self._symbols]
        if not new_symbols:
            logger.info("No new symbols to add")
            return
        
        # Add to DataSource Manager
        await self.data_source_manager.active_source.connect(self._symbols + new_symbols)
        self._symbols.extend(new_symbols)
        logger.info(f"Added {len(new_symbols)} symbols to subscription")
    
    async def remove_symbols(self, symbols: List[str]):
        """
        Remove symbols from real-time subscription.
        
        Args:
            symbols: List of symbols to remove
        """
        if not self._running:
            logger.warning("Real-time price service not running, cannot remove symbols")
            return
        
        removed = 0
        for symbol in symbols:
            if symbol in self._symbols:
                self._symbols.remove(symbol)
                removed += 1
        
        if removed > 0:
            # Restart with updated symbol list
            await self.data_source_manager.stop()
            await self.data_source_manager.start(self._symbols)
        
        logger.info(f"Removed {removed} symbols from subscription")
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get current status of real-time price service.
        
        Returns:
            Dictionary with status information
        """
        health = await self.data_source_manager.health_check()
        
        return {
            "running": self._running,
            "mode": self.data_source_manager.mode.value,
            "active_source": self.data_source_manager.active_source.name if self.data_source_manager.active_source else None,
            "symbols_count": len(self._symbols),
            "symbols": self._symbols[:10],  # First 10 for preview
            "messages_received": self._messages_received,
            "messages_broadcast": self._messages_broadcast,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "mode_change_count": self._mode_change_count,
            "data_source_health": health,
            "connected_clients": websocket_manager.get_connection_count()
        }
    
    async def update_symbols(self, symbols: List[str]):
        """
        Update the list of subscribed symbols.
        
        Args:
            symbols: New list of symbols to subscribe to
        """
        if self._running:
            await self.stop()
        
        self._symbols = symbols
        await self.start(symbols)


# Global real-time price service instance
_realtime_price_service: Optional[RealtimePriceService] = None


def get_realtime_price_service(polygon_api_key: Optional[str] = None) -> RealtimePriceService:
    """
    Get global real-time price service instance.
    
    Args:
        polygon_api_key: Polygon API key (optional, will use polling fallback if not provided)
        
    Returns:
        RealtimePriceService instance
    """
    global _realtime_price_service
    
    if _realtime_price_service is None:
        _realtime_price_service = RealtimePriceService(polygon_api_key)
    
    return _realtime_price_service
