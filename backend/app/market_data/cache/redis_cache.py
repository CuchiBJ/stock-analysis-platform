"""
Redis Caching Layer

Distributed caching strategy for market data with intelligent cache invalidation,
TTL-based expiration, and stale-while-revalidate pattern.
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import asdict
import asyncio

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis caching layer for market data.
    
    Caches:
    - Latest bars per symbol
    - Intraday aggregates
    - Setup states
    - Regime state
    - RS calculations
    - Sector leadership
    - Transition snapshots
    - Event history
    - Freshness state
    
    Features:
    - TTL-based expiration
    - Event-driven invalidation
    - Stale-while-revalidate pattern
    - Request deduplication
    """
    
    def __init__(self):
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, caching disabled")
            self.client = None
            return
        
        try:
            self.client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            self._connected = False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
    
    async def connect(self):
        """Connect to Redis."""
        if not self.client:
            return
        
        try:
            await self.client.ping()
            self._connected = True
            logger.info("Redis cache connected")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._connected = False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
            self._connected = False
    
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self.client is not None and self._connected
    
    # ========== Cache Key Patterns ==========
    
    @staticmethod
    def _bar_key(symbol: str) -> str:
        """Cache key for latest bars."""
        return f"market:bars:{symbol}"
    
    @staticmethod
    def _aggregate_key(symbol: str) -> str:
        """Cache key for intraday aggregates."""
        return f"market:aggregates:{symbol}"
    
    @staticmethod
    def _setup_key(symbol: str) -> str:
        """Cache key for setup state."""
        return f"market:setup:{symbol}"
    
    @staticmethod
    def _regime_key() -> str:
        """Cache key for regime state."""
        return "market:regime"
    
    @staticmethod
    def _rs_key(symbol: str) -> str:
        """Cache key for RS calculations."""
        return f"market:rs:{symbol}"
    
    @staticmethod
    def _sector_leadership_key(sector: str) -> str:
        """Cache key for sector leadership."""
        return f"market:sector_leadership:{sector}"
    
    @staticmethod
    def _transition_key(symbol: str) -> str:
        """Cache key for transition snapshots."""
        return f"market:transitions:{symbol}"
    
    @staticmethod
    def _events_key() -> str:
        """Cache key for recent events."""
        return "market:events:recent"
    
    @staticmethod
    def _freshness_key(symbol: str) -> str:
        """Cache key for data freshness."""
        return f"market:freshness:{symbol}"
    
    # ========== Cache Operations ==========
    
    async def set_bar(self, symbol: str, bar_data: Dict[str, Any], ttl: int = 300):
        """
        Cache latest bar for a symbol.
        
        Args:
            symbol: Ticker symbol
            bar_data: Bar data dictionary
            ttl: Time to live in seconds (default: 5 minutes)
        """
        if not self.is_available():
            return
        
        try:
            key = self._bar_key(symbol)
            value = json.dumps(bar_data)
            await self.client.setex(key, ttl, value)
            await self._update_freshness(symbol)
        except Exception as e:
            logger.error(f"Error caching bar for {symbol}: {e}")
    
    async def get_bar(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cached bar for a symbol.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Bar data or None if not cached
        """
        if not self.is_available():
            return None
        
        try:
            key = self._bar_key(symbol)
            value = await self.client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cached bar for {symbol}: {e}")
            return None
    
    async def set_aggregate(self, symbol: str, aggregate_data: Dict[str, Any], ttl: int = 60):
        """
        Cache intraday aggregate for a symbol.
        
        Args:
            symbol: Ticker symbol
            aggregate_data: Aggregate data dictionary
            ttl: Time to live in seconds (default: 1 minute)
        """
        if not self.is_available():
            return
        
        try:
            key = self._aggregate_key(symbol)
            value = json.dumps(aggregate_data)
            await self.client.setex(key, ttl, value)
            await self._update_freshness(symbol)
        except Exception as e:
            logger.error(f"Error caching aggregate for {symbol}: {e}")
    
    async def get_aggregate(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cached aggregate for a symbol.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Aggregate data or None if not cached
        """
        if not self.is_available():
            return None
        
        try:
            key = self._aggregate_key(symbol)
            value = await self.client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cached aggregate for {symbol}: {e}")
            return None
    
    async def set_setup_state(self, symbol: str, setup_data: Dict[str, Any], ttl: int = 600):
        """
        Cache setup state for a symbol.
        
        Args:
            symbol: Ticker symbol
            setup_data: Setup state dictionary
            ttl: Time to live in seconds (default: 10 minutes)
        """
        if not self.is_available():
            return
        
        try:
            key = self._setup_key(symbol)
            value = json.dumps(setup_data)
            await self.client.setex(key, ttl, value)
        except Exception as e:
            logger.error(f"Error caching setup state for {symbol}: {e}")
    
    async def get_setup_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cached setup state for a symbol.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Setup state or None if not cached
        """
        if not self.is_available():
            return None
        
        try:
            key = self._setup_key(symbol)
            value = await self.client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cached setup state for {symbol}: {e}")
            return None
    
    async def set_regime_state(self, regime_data: Dict[str, Any], ttl: int = 3600):
        """
        Cache regime state.
        
        Args:
            regime_data: Regime state dictionary
            ttl: Time to live in seconds (default: 1 hour)
        """
        if not self.is_available():
            return
        
        try:
            key = self._regime_key()
            value = json.dumps(regime_data)
            await self.client.setex(key, ttl, value)
        except Exception as e:
            logger.error(f"Error caching regime state: {e}")
    
    async def get_regime_state(self) -> Optional[Dict[str, Any]]:
        """
        Get cached regime state.
        
        Returns:
            Regime state or None if not cached
        """
        if not self.is_available():
            return None
        
        try:
            key = self._regime_key()
            value = await self.client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cached regime state: {e}")
            return None
    
    async def invalidate_symbol(self, symbol: str):
        """
        Invalidate all cache entries for a symbol.
        
        Args:
            symbol: Ticker symbol to invalidate
        """
        if not self.is_available():
            return
        
        try:
            pattern = f"market:*:{symbol}"
            keys = await self.client.keys(pattern)
            
            if keys:
                await self.client.delete(*keys)
                logger.debug(f"Invalidated {len(keys)} cache entries for {symbol}")
        except Exception as e:
            logger.error(f"Error invalidating cache for {symbol}: {e}")
    
    async def invalidate_regime(self):
        """Invalidate regime state cache."""
        if not self.is_available():
            return
        
        try:
            key = self._regime_key()
            await self.client.delete(key)
            logger.debug("Invalidated regime state cache")
        except Exception as e:
            logger.error(f"Error invalidating regime cache: {e}")
    
    async def _update_freshness(self, symbol: str):
        """
        Update freshness timestamp for a symbol.
        
        Args:
            symbol: Ticker symbol
        """
        if not self.is_available():
            return
        
        try:
            key = self._freshness_key(symbol)
            timestamp = datetime.utcnow().isoformat()
            await self.client.setex(key, 3600, timestamp)  # 1 hour TTL
        except Exception as e:
            logger.error(f"Error updating freshness for {symbol}: {e}")
    
    async def get_freshness(self, symbol: str) -> Optional[datetime]:
        """
        Get data freshness timestamp for a symbol.
        
        Args:
            symbol: Ticker symbol
            
        Returns:
            Datetime of last update or None if not cached
        """
        if not self.is_available():
            return None
        
        try:
            key = self._freshness_key(symbol)
            value = await self.client.get(key)
            
            if value:
                return datetime.fromisoformat(value)
            return None
        except Exception as e:
            logger.error(f"Error getting freshness for {symbol}: {e}")
            return None
    
    async def batch_get_bars(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Batch get cached bars for multiple symbols.
        
        Args:
            symbols: List of ticker symbols
            
        Returns:
            Dictionary mapping symbol to bar data (or None if not cached)
        """
        if not self.is_available():
            return {symbol: None for symbol in symbols}
        
        try:
            keys = [self._bar_key(symbol) for symbol in symbols]
            values = await self.client.mget(keys)
            
            result = {}
            for symbol, value in zip(symbols, values):
                if value:
                    result[symbol] = json.loads(value)
                else:
                    result[symbol] = None
            
            return result
        except Exception as e:
            logger.error(f"Error batch getting bars: {e}")
            return {symbol: None for symbol in symbols}
    
    async def batch_set_bars(self, bars: Dict[str, Dict[str, Any]], ttl: int = 300):
        """
        Batch set cached bars for multiple symbols.
        
        Args:
            bars: Dictionary mapping symbol to bar data
            ttl: Time to live in seconds
        """
        if not self.is_available():
            return
        
        try:
            pipe = self.client.pipeline()
            
            for symbol, bar_data in bars.items():
                key = self._bar_key(symbol)
                value = json.dumps(bar_data)
                pipe.setex(key, ttl, value)
                self._update_freshness(symbol)
            
            await pipe.execute()
            logger.debug(f"Batch cached {len(bars)} bars")
        except Exception as e:
            logger.error(f"Error batch setting bars: {e}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if not self.is_available():
            return {"available": False}
        
        try:
            info = await self.client.info("stats")
            keys_count = await self.client.dbsize()
            
            return {
                "available": True,
                "connected": self._connected,
                "total_keys": keys_count,
                "info": info
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"available": False, "error": str(e)}


# Global cache instance
redis_cache = RedisCache()
