"""
Multi-layer caching system
L1: In-memory (fast, per-service)
L2: Redis (shared, distributed)
L3: Vector Store (persistent, semantic)
"""
import asyncio
import hashlib
import json
import time
from typing import Any, Optional, Dict, TypeVar, Generic
from dataclasses import dataclass, field
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata"""
    value: T
    created_at: float
    ttl: float
    hits: int = 0

    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl

    def remaining_ttl(self) -> float:
        return max(0, (self.created_at + self.ttl) - time.time())


class LRUCache:
    """
    In-memory LRU cache (L1)
    Fast access, limited size, per-service
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 300):
        """
        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._hits += 1

            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value in cache"""
        async with self._lock:
            ttl = ttl or self.default_ttl

            # Remove oldest if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl
            )

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self):
        """Clear all entries"""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self):
        """Remove expired entries"""
        async with self._lock:
            expired = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired:
                del self._cache[key]
            return len(expired)

    def stats(self) -> Dict:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2%}"
        }


class RedisCache:
    """
    Redis-based distributed cache (L2)
    Shared across services, larger capacity
    """

    def __init__(self, redis_url: str = "redis://localhost:6379", default_ttl: int = 3600, prefix: str = "atlas"):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.prefix = prefix
        self._redis = None
        self._connected = False

    async def connect(self):
        """Connect to Redis"""
        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
            self._connected = True
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            self._connected = False

    def _key(self, key: str) -> str:
        """Generate prefixed key"""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        if not self._connected:
            return None

        try:
            data = await self._redis.get(self._key(key))
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in Redis"""
        if not self._connected:
            return

        try:
            ttl = ttl or self.default_ttl
            data = json.dumps(value, default=str)
            await self._redis.setex(self._key(key), ttl, data)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self._connected:
            return False

        try:
            result = await self._redis.delete(self._key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    async def get_many(self, keys: list) -> Dict[str, Any]:
        """Get multiple values"""
        if not self._connected:
            return {}

        try:
            prefixed_keys = [self._key(k) for k in keys]
            values = await self._redis.mget(prefixed_keys)

            result = {}
            for key, value in zip(keys, values):
                if value:
                    result[key] = json.loads(value)

            return result
        except Exception as e:
            logger.error(f"Redis mget error: {e}")
            return {}

    async def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None):
        """Set multiple values"""
        if not self._connected:
            return

        try:
            ttl = ttl or self.default_ttl
            pipe = self._redis.pipeline()

            for key, value in items.items():
                data = json.dumps(value, default=str)
                pipe.setex(self._key(key), ttl, data)

            await pipe.execute()
        except Exception as e:
            logger.error(f"Redis mset error: {e}")

    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()


class MultiLayerCache:
    """
    Multi-layer cache combining L1 (memory) and L2 (Redis)
    Automatic promotion/demotion between layers
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        l1_max_size: int = 500,
        l1_ttl: float = 300,
        l2_ttl: int = 3600,
        cache_prefix: str = "atlas"
    ):
        self.l1 = LRUCache(max_size=l1_max_size, default_ttl=l1_ttl)
        self.l2 = RedisCache(redis_url=redis_url, default_ttl=l2_ttl, prefix=cache_prefix)

    async def connect(self):
        """Initialize cache connections"""
        await self.l2.connect()

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value, checking L1 first, then L2
        Promotes L2 hits to L1
        """
        # Try L1 first
        value = await self.l1.get(key)
        if value is not None:
            return value

        # Try L2
        value = await self.l2.get(key)
        if value is not None:
            # Promote to L1
            await self.l1.set(key, value)
            return value

        return None

    async def set(self, key: str, value: Any, l1_ttl: Optional[float] = None, l2_ttl: Optional[int] = None):
        """Set value in both layers"""
        await asyncio.gather(
            self.l1.set(key, value, l1_ttl),
            self.l2.set(key, value, l2_ttl)
        )

    async def delete(self, key: str):
        """Delete from both layers"""
        await asyncio.gather(
            self.l1.delete(key),
            self.l2.delete(key)
        )

    async def close(self):
        """Close connections"""
        await self.l2.close()

    def stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "l1": self.l1.stats(),
            "l2_connected": self.l2._connected
        }


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments"""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl: float = 300, key_prefix: str = ""):
    """
    Decorator for caching async function results

    Usage:
        @cached(ttl=600, key_prefix="github")
        async def fetch_repos(user: str):
            ...
    """
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            # Generate cache key
            key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try to get from cache
            if hasattr(self, 'cache') and self.cache:
                cached_value = await self.cache.get(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {key}")
                    return cached_value

            # Execute function
            result = await func(self, *args, **kwargs)

            # Store in cache
            if hasattr(self, 'cache') and self.cache and result is not None:
                await self.cache.set(key, result, l1_ttl=ttl)

            return result

        return wrapper
    return decorator
