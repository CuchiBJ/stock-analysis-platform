"""
DataSource Strategy Abstraction

Provider-agnostic data source strategy for real-time price updates.
Supports WebSocket streaming and smart polling fallback.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncIterator
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """Type of data source"""
    WEBSOCKET = "websocket"
    POLLING = "polling"
    HYBRID = "hybrid"


class DataSourceStatus(Enum):
    """Status of data source"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    FALLBACK = "fallback"


@dataclass
class NormalizedPriceEvent:
    """Normalized price event (provider-agnostic)"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    source_type: DataSourceType = DataSourceType.POLLING
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": self.vwap,
            "source_type": self.source_type.value,
            "metadata": self.metadata or {}
        }


class DataSourceStrategy(ABC):
    """
    Abstract data source strategy.
    
    All data sources must implement this interface to ensure
    provider-agnostic internal event flow.
    """
    
    def __init__(self, name: str, source_type: DataSourceType):
        self.name = name
        self.source_type = source_type
        self._status = DataSourceStatus.DISCONNECTED
        self._error_count = 0
        self._max_errors = 10
    
    @abstractmethod
    async def connect(self, symbols: List[str]) -> bool:
        """
        Connect to data source.
        
        Args:
            symbols: List of symbols to subscribe to
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from data source."""
        pass
    
    @abstractmethod
    async def stream_prices(self, symbols: List[str]) -> AsyncIterator[NormalizedPriceEvent]:
        """
        Stream price updates.
        
        Args:
            symbols: List of symbols to stream
            
        Yields:
            NormalizedPriceEvent objects
        """
        pass
    
    @abstractmethod
    async def get_price_snapshot(self, symbols: List[str]) -> Dict[str, NormalizedPriceEvent]:
        """
        Get current price snapshot.
        
        Args:
            symbols: List of symbols to fetch
            
        Returns:
            Dictionary mapping symbol to NormalizedPriceEvent
        """
        pass
    
    @property
    def status(self) -> DataSourceStatus:
        """Get current status."""
        return self._status
    
    @status.setter
    def status(self, value: DataSourceStatus):
        """Set status."""
        self._status = value
        logger.info(f"{self.name} status changed to {value.value}")
    
    def increment_error(self):
        """Increment error count."""
        self._error_count += 1
        logger.warning(f"{self.name} error count: {self._error_count}/{self._max_errors}")
        
        if self._error_count >= self._max_errors:
            self.status = DataSourceStatus.ERROR
    
    def reset_error_count(self):
        """Reset error count."""
        self._error_count = 0
    
    def is_healthy(self) -> bool:
        """Check if data source is healthy."""
        return self.status in [DataSourceStatus.CONNECTED, DataSourceStatus.FALLBACK] and self._error_count < self._max_errors
    
    async def health_check(self) -> bool:
        """
        Perform health check.
        
        Returns:
            True if healthy, False otherwise
        """
        return self.is_healthy()


class WebSocketDataSource(DataSourceStrategy):
    """
    WebSocket data source for real-time streaming.
    
    High-priority, low-latency data source.
    Falls back to polling on failure.
    """
    
    def __init__(self, provider):
        super().__init__("WebSocketDataSource", DataSourceType.WEBSOCKET)
        self.provider = provider
        self._symbols: List[str] = []
        self._connected = False
    
    async def connect(self, symbols: List[str]) -> bool:
        """Connect to WebSocket provider."""
        try:
            await self.provider.connect()
            await self.provider.subscribe(symbols, "AGGREGATE")
            self._symbols = symbols
            self._connected = True
            self.status = DataSourceStatus.CONNECTED
            return True
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.status = DataSourceStatus.ERROR
            self.increment_error()
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket provider."""
        try:
            await self.provider.disconnect()
            self._connected = False
            self.status = DataSourceStatus.DISCONNECTED
        except Exception as e:
            logger.error(f"WebSocket disconnect failed: {e}")
    
    async def stream_prices(self, symbols: List[str]) -> AsyncIterator[NormalizedPriceEvent]:
        """Stream prices from WebSocket."""
        if not self._connected:
            logger.warning("WebSocket not connected, cannot stream")
            return
        
        try:
            from app.market_data.interfaces import Timespan
            async for aggregate in self.provider.stream_aggregates("*", Timespan.MINUTE):
                if not self._connected:
                    break
                
                yield NormalizedPriceEvent(
                    symbol=aggregate.symbol or "",
                    timestamp=aggregate.timestamp,
                    open=aggregate.open,
                    high=aggregate.high,
                    low=aggregate.low,
                    close=aggregate.close,
                    volume=aggregate.volume,
                    vwap=aggregate.vwap,
                    source_type=DataSourceType.WEBSOCKET,
                    metadata={"source": "polygon_websocket"}
                )
        except Exception as e:
            logger.error(f"WebSocket stream error: {e}")
            self.increment_error()
            raise
    
    async def get_price_snapshot(self, symbols: List[str]) -> Dict[str, NormalizedPriceEvent]:
        """
        Get price snapshot from WebSocket (last known values).
        
        For WebSocket, this returns cached values from the stream.
        """
        # In a real implementation, this would return cached values
        # from the WebSocket stream
        return {}


class DatabasePollingDataSource(DataSourceStrategy):
    """
    Database polling data source (fallback for historical data).
    
    Uses existing price data from database as fallback when Polygon is unavailable.
    Provides tier-based updates without external API dependencies.
    """
    
    def __init__(self):
        super().__init__("DatabasePollingDataSource", DataSourceType.POLLING)
        self._symbols: List[str] = []
        self._running = False
        self._polling_task: Optional[asyncio.Task] = None
        
        # In-memory cache for latest prices (simple implementation)
        self._price_cache: Dict[str, NormalizedPriceEvent] = {}
        
        # Event queue for streaming
        self._event_queue: asyncio.Queue = asyncio.Queue()
        
        # Tier-based polling intervals (in seconds)
        self._polling_intervals = {
            "tier_1": 15,
            "tier_2": 60,
            "tier_3": 300,
            "tier_4": 86400  # daily
        }
    
    async def connect(self, symbols: List[str]) -> bool:
        """Connect to database data source."""
        self._symbols = symbols
        self.status = DataSourceStatus.CONNECTED
        
        # Fetch initial data immediately
        tier_groups = await self._group_symbols_by_tier(symbols)
        for tier, tier_symbols in tier_groups.items():
            if tier_symbols:
                await self._batch_fetch_prices(tier_symbols)
        
        logger.info(f"DatabasePollingDataSource connected for {len(symbols)} symbols")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from database data source."""
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        self.status = DataSourceStatus.DISCONNECTED
    
    async def stream_prices(self, symbols: List[str]) -> AsyncIterator[NormalizedPriceEvent]:
        """Stream prices from database using queue."""
        self._running = True
        self._polling_task = asyncio.create_task(self._polling_loop(symbols))
        
        # Wait a moment for initial data to be fetched
        logger.info(f"Waiting for initial data fetch for {len(symbols)} symbols...")
        await asyncio.sleep(2)
        logger.info(f"Cache size after initial fetch: {len(self._price_cache)}")
        
        # Put initial cached events into queue
        for symbol in symbols:
            event = await self._get_latest_price(symbol)
            if event:
                await self._event_queue.put(event)
        
        logger.info(f"Put {self._event_queue.qsize()} initial events into queue")
        
        try:
            while self._running:
                event = await self._event_queue.get()
                yield event
        except Exception as e:
            logger.error(f"Database polling stream error: {e}")
            self.increment_error()
            raise
    
    async def _polling_loop(self, symbols: List[str]):
        """Background polling loop with tier-based intervals."""
        tier_groups = await self._group_symbols_by_tier(symbols)
        
        while self._running:
            for tier, tier_symbols in tier_groups.items():
                if not tier_symbols:
                    continue
                    
                interval = self._polling_intervals.get(tier, 60)
                logger.info(f"Polling {tier}: {len(tier_symbols)} symbols at {interval}s interval")
                
                # Batch query for tier (efficient)
                await self._batch_fetch_prices(tier_symbols)
                
                await asyncio.sleep(interval)
    
    async def _batch_fetch_prices(self, symbols: List[str]):
        """Batch fetch prices from database (1 query per tier, not per symbol)."""
        try:
            from app.core.deps import AsyncSessionLocal
            from sqlalchemy import select, text
            
            async with AsyncSessionLocal() as db:
                # Single query for all symbols in this tier
                symbols_str = ",".join(f"'{s}'" for s in symbols)
                query = text(f"""
                    SELECT sp.symbol, sp.date, sp.open, sp.high, sp.low, sp.close, sp.volume
                    FROM stock_prices sp
                    WHERE sp.symbol IN ({symbols_str})
                    ORDER BY sp.symbol, sp.date DESC
                """)
                
                result = await db.execute(query)
                rows = result.fetchall()
                
                # Process and cache results
                for row in rows:
                    # Ensure timestamp is a datetime object
                    timestamp = row[1]
                    if isinstance(timestamp, str):
                        from datetime import datetime as dt
                        timestamp = dt.fromisoformat(timestamp)
                    
                    event = NormalizedPriceEvent(
                        symbol=row[0],
                        timestamp=timestamp,
                        open=float(row[2]),
                        high=float(row[3]),
                        low=float(row[4]),
                        close=float(row[5]),
                        volume=int(row[6]),
                        source_type=DataSourceType.POLLING,
                        metadata={"source": "database_historical"}
                    )
                    # Cache the event (keep latest per symbol)
                    self._price_cache[event.symbol] = event
                    # Put event into queue for streaming
                    await self._event_queue.put(event)
                
                logger.info(f"Batch fetched, cached, and queued prices for {len(symbols)} symbols")
                
        except Exception as e:
            logger.error(f"Batch fetch error: {e}")
    
    async def _get_latest_price(self, symbol: str) -> Optional[NormalizedPriceEvent]:
        """Get latest price from cache."""
        return self._price_cache.get(symbol)
    
    async def get_price_snapshot(self, symbols: List[str]) -> Dict[str, NormalizedPriceEvent]:
        """Get current price snapshot from database."""
        try:
            from app.core.deps import AsyncSessionLocal
            from sqlalchemy import select, text
            
            async with AsyncSessionLocal() as db:
                symbols_str = ",".join(f"'{s}'" for s in symbols)
                query = text(f"""
                    SELECT DISTINCT ON (sp.symbol) sp.symbol, sp.date, sp.open, sp.high, sp.low, sp.close, sp.volume
                    FROM stock_prices sp
                    WHERE sp.symbol IN ({symbols_str})
                    ORDER BY sp.symbol, sp.date DESC
                """)
                
                result = await db.execute(query)
                rows = result.fetchall()
                
                snapshot = {}
                for row in rows:
                    snapshot[row[0]] = NormalizedPriceEvent(
                        symbol=row[0],
                        timestamp=row[1],
                        open=float(row[2]),
                        high=float(row[3]),
                        low=float(row[4]),
                        close=float(row[5]),
                        volume=int(row[6]),
                        source_type=DataSourceType.POLLING,
                        metadata={"source": "database_historical"}
                    )
                
                return snapshot
        
        except Exception as e:
            logger.error(f"Database snapshot error: {e}")
            return {}
    
    async def _group_symbols_by_tier(self, symbols: List[str]) -> Dict[str, List[str]]:
        """Group symbols by tier using direct database query (no in-memory TierManager)."""
        try:
            from app.core.deps import AsyncSessionLocal
            from sqlalchemy import text
            
            async with AsyncSessionLocal() as db:
                # Direct database query for tier assignments
                symbols_str = ",".join(f"'{s}'" for s in symbols)
                query = text(f"""
                    SELECT ii.current_symbol, ut.tier
                    FROM instrument_identities ii
                    JOIN universe_tiers ut ON ii.internal_id = ut.instrument_id
                    WHERE ii.current_symbol IN ({symbols_str})
                    AND ii.lifecycle_state = 'active'
                """)
                
                result = await db.execute(query)
                rows = result.fetchall()
                
                tier_groups = {
                    "tier_1": [],
                    "tier_2": [],
                    "tier_3": [],
                    "tier_4": []
                }
                
                symbol_tier_map = {row[0]: row[1] for row in rows}
                
                for symbol in symbols:
                    tier = symbol_tier_map.get(symbol)
                    if tier and tier in tier_groups:
                        tier_groups[tier].append(symbol)
                    else:
                        # Default to tier_3 if not found
                        tier_groups["tier_3"].append(symbol)
                
                return tier_groups
        
        except Exception as e:
            logger.error(f"Error grouping symbols by tier: {e}")
            # Fallback: put all symbols in tier_3
            return {"tier_1": [], "tier_2": [], "tier_3": symbols, "tier_4": []}


class SmartPollingDataSource(DataSourceStrategy):
    """
    Smart polling data source.
    
    Fallback data source with tier-based polling intervals:
    - Tier 1: 15 seconds
    - Tier 2: 1 minute
    - Tier 3: 5 minutes
    
    Uses Redis caching and request deduplication.
    """
    
    def __init__(self, provider, redis_client=None):
        super().__init__("SmartPollingDataSource", DataSourceType.POLLING)
        self.provider = provider
        self.redis_client = redis_client
        self._symbols: List[str] = []
        self._running = False
        self._polling_task: Optional[asyncio.Task] = None
        
        # Tier-based polling intervals (in seconds)
        self._polling_intervals = {
            "TIER_1": 15,
            "TIER_2": 60,
            "TIER_3": 300
        }
        
        # Cache TTL (in seconds)
        self._cache_ttl = {
            "TIER_1": 10,
            "TIER_2": 45,
            "TIER_3": 240
        }
        
        # Request deduplication
        self._pending_requests: Dict[str, asyncio.Task] = {}
    
    async def connect(self, symbols: List[str]) -> bool:
        """Connect to polling provider."""
        self._symbols = symbols
        self.status = DataSourceStatus.CONNECTED
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from polling provider."""
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        self.status = DataSourceStatus.DISCONNECTED
    
    async def stream_prices(self, symbols: List[str]) -> AsyncIterator[NormalizedPriceEvent]:
        """Stream prices via smart polling."""
        self._running = True
        self._polling_task = asyncio.create_task(self._polling_loop(symbols))
        
        try:
            while self._running:
                # Yield events from cache
                for symbol in symbols:
                    cached = await self._get_from_cache(symbol)
                    if cached:
                        yield cached
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Polling stream error: {e}")
            self.increment_error()
            raise
    
    async def _polling_loop(self, symbols: List[str]):
        """Background polling loop with tier-based intervals."""
        tier_groups = await self._group_symbols_by_tier(symbols)
        
        while self._running:
            for tier, tier_symbols in tier_groups.items():
                interval = self._polling_intervals.get(tier, 60)
                
                for symbol in tier_symbols:
                    try:
                        # Check if request is already pending
                        if symbol in self._pending_requests:
                            continue
                        
                        # Create polling task
                        task = asyncio.create_task(self._poll_symbol(symbol))
                        self._pending_requests[symbol] = task
                        
                        # Clean up completed tasks
                        task.add_done_callback(lambda t: self._pending_requests.pop(symbol, None))
                    
                    except Exception as e:
                        logger.error(f"Polling error for {symbol}: {e}")
                
                await asyncio.sleep(interval)
    
    async def _poll_symbol(self, symbol: str) -> Optional[NormalizedPriceEvent]:
        """Poll a single symbol."""
        try:
            from datetime import timedelta
            
            # Fetch latest bar from provider
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=1)
            
            bars = await self.provider.get_aggregates(
                symbol=symbol,
                timespan="minute",
                multiplier=1,
                start_date=start_date,
                end_date=end_date,
                limit=1
            )
            
            if bars:
                latest = bars[0]
                event = NormalizedPriceEvent(
                    symbol=symbol,
                    timestamp=latest.timestamp,
                    open=latest.open,
                    high=latest.high,
                    low=latest.low,
                    close=latest.close,
                    volume=latest.volume,
                    vwap=latest.vwap,
                    source_type=DataSourceType.POLLING,
                    metadata={"source": "polygon_rest", "polled_at": datetime.utcnow().isoformat()}
                )
                
                # Cache the event
                await self._cache_event(event)
                
                return event
        
        except Exception as e:
            logger.error(f"Failed to poll {symbol}: {e}")
            return None
    
    async def _group_symbols_by_tier(self, symbols: List[str]) -> Dict[str, List[str]]:
        """Group symbols by their tier using Universe Engine."""
        try:
            from app.universe.universe_engine import get_universe_engine
            from app.universe.tiers.tier_manager import UniverseTier
            
            universe_engine = get_universe_engine()
            
            tier_groups = {
                "TIER_1": [],
                "TIER_2": [],
                "TIER_3": [],
                "TIER_4": []
            }
            
            for symbol in symbols:
                # Get tier for symbol from Universe Engine
                tier = universe_engine.tier_manager.get_tier_for_symbol(symbol)
                if tier:
                    tier_groups[tier.value].append(symbol)
                else:
                    # Default to TIER_2 if not found
                    tier_groups["TIER_2"].append(symbol)
            
            return {k: v for k, v in tier_groups.items() if v}
        
        except Exception as e:
            logger.error(f"Failed to group symbols by tier: {e}")
            # Fallback to default TIER_2
            return {"TIER_2": symbols}
    
    async def _cache_event(self, event: NormalizedPriceEvent):
        """Cache event in Redis."""
        if self.redis_client:
            try:
                cache_key = f"price:{event.symbol}"
                ttl = self._cache_ttl.get("TIER_2", 45)
                await self.redis_client.setex(
                    cache_key,
                    ttl,
                    event.to_dict()
                )
            except Exception as e:
                logger.error(f"Failed to cache event: {e}")
    
    async def _get_from_cache(self, symbol: str) -> Optional[NormalizedPriceEvent]:
        """Get event from cache."""
        if self.redis_client:
            try:
                cache_key = f"price:{symbol}"
                data = await self.redis_client.get(cache_key)
                if data:
                    import json
                    return NormalizedPriceEvent(**json.loads(data))
            except Exception as e:
                logger.error(f"Failed to get from cache: {e}")
        return None
    
    async def get_price_snapshot(self, symbols: List[str]) -> Dict[str, NormalizedPriceEvent]:
        """Get price snapshot from cache or poll."""
        snapshot = {}
        
        for symbol in symbols:
            # Try cache first
            cached = await self._get_from_cache(symbol)
            if cached:
                snapshot[symbol] = cached
                continue
            
            # Poll if not in cache
            event = await self._poll_symbol(symbol)
            if event:
                snapshot[symbol] = event
        
        return snapshot
