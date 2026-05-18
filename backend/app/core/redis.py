import redis.asyncio as redis
from app.core.config import settings

class RedisClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_client(self):
        """Get or create Redis client"""
        if not hasattr(self, '_client') or self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                health_check_interval=30
            )
        return self._client
    
    async def close(self):
        """Close Redis connection"""
        if hasattr(self, '_client') and self._client:
            await self._client.close()
            self._client = None

redis_client = RedisClient()
