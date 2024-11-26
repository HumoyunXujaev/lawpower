from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
import json
import logging
from redis.asyncio import Redis
from redis.exceptions import RedisError
import hashlib
from functools import wraps
import asyncio
from telegram_bot.core.config import settings
from telegram_bot.core.monitoring import metrics_manager

logger = logging.getLogger(__name__)

class CacheService:
    """Enhanced Redis cache service"""
    
    def __init__(self):
        self.redis = Redis.from_url(
            settings.REDIS_URL,
            encoding='utf-8',
            decode_responses=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT,
            retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )
        self.default_timeout = 3600  # 1 hour
        
    async def get(self, key: str, default: Any = None) -> Optional[Any]:
        """Get cached value"""
        try:
            value = await self.redis.get(key)
            
            # Track metrics
            metrics_manager.track_cache(
                'get',
                hit=bool(value)
            )
            
            if value is None:
                return default
                
            return json.loads(value)
            
        except RedisError as e:
            logger.error(f"Redis GET error: {e}")
            return default
            
    async def set(
        self,
        key: str,
        value: Any,
        timeout: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set cached value"""
        try:
            pipe = self.redis.pipeline()
            
            # Set main value
            pipe.set(
                key,
                json.dumps(value),
                ex=timeout or self.default_timeout
            )
            
            # Add tags
            if tags:
                for tag in tags:
                    pipe.sadd(f"tag:{tag}", key)
                    pipe.expire(f"tag:{tag}", timeout or self.default_timeout)
            
            results = await pipe.execute()
            return all(results)
            
        except RedisError as e:
            logger.error(f"Redis SET error: {e}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """Delete cached values"""
        try:
            # Get tags for keys
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.smembers(f"key_tags:{key}")
            tag_results = await pipe.execute()
            
            # Delete keys and tag references
            pipe = self.redis.pipeline()
            
            # Delete main keys
            pipe.delete(*keys)
            
            # Remove keys from tag sets
            all_tags = set()
            for tags in tag_results:
                all_tags.update(tags)
                
            for tag in all_tags:
                pipe.srem(f"tag:{tag}", *keys)
                
            results = await pipe.execute()
            return results[0]  # Number of deleted keys
            
        except RedisError as e:
            logger.error(f"Redis DELETE error: {e}")
            return 0
            
    async def clear_by_tag(self, tag: str) -> int:
        """Clear all keys with given tag"""
        try:
            # Get tagged keys
            keys = await self.redis.smembers(f"tag:{tag}")
            if not keys:
                return 0
                
            # Delete keys and tag
            pipe = self.redis.pipeline()
            pipe.delete(*keys)
            pipe.delete(f"tag:{tag}")
            
            results = await pipe.execute()
            return results[0]
            
        except RedisError as e:
            logger.error(f"Redis tag clear error: {e}")
            return 0
            
    async def get_by_pattern(self, pattern: str) -> Dict[str, Any]:
        """Get all keys matching pattern"""
        try:
            # Get matching keys
            keys = []
            async for key in self.redis.scan_iter(pattern):
                keys.append(key)
                
            if not keys:
                return {}
                
            # Get values
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
                
            values = await pipe.execute()
            
            return {
                key: json.loads(value)
                for key, value in zip(keys, values)
                if value is not None
            }
            
        except RedisError as e:
            logger.error(f"Redis pattern get error: {e}")
            return {}
            
    async def increment(
        self,
        key: str,
        amount: int = 1,
        timeout: Optional[int] = None
    ) -> Optional[int]:
        """Increment counter"""
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key, amount)
            
            if timeout:
                pipe.expire(key, timeout)
                
            results = await pipe.execute()
            return results[0]
            
        except RedisError as e:
            logger.error(f"Redis INCREMENT error: {e}")
            return None
            
    async def get_or_set(
        self,
        key: str,
        factory: callable,
        timeout: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> Any:
        """Get cached value or generate and cache new one"""
        try:
            # Try get from cache
            value = await self.get(key)
            if value is not None:
                return value
                
            # Generate new value
            value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
            
            # Cache new value
            await self.set(
                key,
                value,
                timeout=timeout,
                tags=tags
            )
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get_or_set error: {e}")
            # Return generated value even if caching fails
            return await factory() if asyncio.iscoroutinefunction(factory) else factory()
            
    async def health_check(self) -> bool:
        """Check Redis connection"""
        try:
            return await self.redis.ping()
        except RedisError:
            return False

def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(
        f"{k}:{v}" for k, v in sorted(kwargs.items())
    )
    return hashlib.md5(":".join(key_parts).encode()).hexdigest()

def cached(
    timeout: Optional[int] = None,
    prefix: Optional[str] = None,
    tags: Optional[List[str]] = None
):
    """Caching decorator"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(*args, **kwargs)
            if prefix:
                key = f"{prefix}:{key}"
                
            return await cache_service.get_or_set(
                key,
                lambda: func(*args, **kwargs),
                timeout=timeout,
                tags=tags
            )
        return wrapper
    return decorator

# Create cache service instance
cache_service = CacheService()

__all__ = [
    'CacheService',
    'cache_service',
    'cache_key',
    'cached'
]