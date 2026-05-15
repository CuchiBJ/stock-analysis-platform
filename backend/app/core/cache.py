from functools import lru_cache
from datetime import datetime, timedelta
from typing import Optional, Callable, TypeVar, Any
import hashlib
import json
import asyncio

T = TypeVar('T')


class CacheManager:
    """Simple in-memory cache manager with TTL support"""
    
    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if datetime.utcnow() > entry['expires_at']:
            del self._cache[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Set value in cache with TTL"""
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        self._cache[key] = {
            'value': value,
            'expires_at': expires_at,
        }
    
    def delete(self, key: str) -> None:
        """Delete value from cache"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry['expires_at']
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


# Global cache manager instance
cache_manager = CacheManager()


def cached(ttl_seconds: int = 60):
    """Decorator for caching function results (works with both sync and async)"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs) -> T:
                # Create cache key from function name and arguments
                # Skip 'self' for class methods to avoid serialization issues
                cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
                key_data = {
                    'func': func.__name__,
                    'args': cache_args,
                    'kwargs': kwargs,
                }
                key = hashlib.md5(json.dumps(key_data, sort_keys=True, default=str).encode()).hexdigest()
                
                # Try to get from cache
                cached_value = cache_manager.get(key)
                if cached_value is not None:
                    return cached_value
                
                # Compute and cache result
                result = await func(*args, **kwargs)
                cache_manager.set(key, result, ttl_seconds)
                
                return result
            return async_wrapper
        else:
            def wrapper(*args, **kwargs) -> T:
                # Create cache key from function name and arguments
                # Skip 'self' for class methods to avoid serialization issues
                cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
                key_data = {
                    'func': func.__name__,
                    'args': cache_args,
                    'kwargs': kwargs,
                }
                key = hashlib.md5(json.dumps(key_data, sort_keys=True, default=str).encode()).hexdigest()
                
                # Try to get from cache
                cached_value = cache_manager.get(key)
                if cached_value is not None:
                    return cached_value
                
                # Compute and cache result
                result = func(*args, **kwargs)
                cache_manager.set(key, result, ttl_seconds)
                
                return result
            return wrapper
    return decorator


# Pre-configured cache decorators for common use cases
cache_indices = cached(ttl_seconds=60)  # 1 minute
cache_breadth = cached(ttl_seconds=120)  # 2 minutes
cache_sectors = cached(ttl_seconds=300)  # 5 minutes
cache_themes = cached(ttl_seconds=300)  # 5 minutes
cache_events = cached(ttl_seconds=3600)  # 1 hour
