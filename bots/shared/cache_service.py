"""
Cache Service for Jorge's Real Estate Bots.

Provides Redis-backed caching with memory fallback for <500ms performance.
Simplified version from EnterpriseHub focused on Jorge's needs.
"""
import time
import pickle
from typing import Any, Optional, Dict
from abc import ABC, abstractmethod

from bots.shared.config import settings
from bots.shared.logger import get_logger
from bots.shared.event_broker import event_broker

logger = get_logger(__name__)


class AbstractCache(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass


class MemoryCache(AbstractCache):
    """In-memory cache fallback."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        logger.info("Initialized MemoryCache")

    async def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None

        if time.time() > self._expiry.get(key, 0):
            await self.delete(key)
            return None

        return self._cache[key]

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        self._cache[key] = value
        self._expiry[key] = time.time() + ttl
        return True

    async def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            del self._expiry[key]
            return True
        return False


class RedisCache(AbstractCache):
    """Redis-based cache for production."""

    def __init__(self, redis_url: str):
        try:
            import redis.asyncio as redis
            self.redis = redis.from_url(
                redis_url,
                max_connections=settings.redis_max_connections,
                socket_timeout=settings.redis_socket_timeout,
                socket_connect_timeout=settings.redis_socket_connect_timeout,
                decode_responses=False
            )
            self.enabled = True
            logger.info(f"Initialized RedisCache: {redis_url}")
        except ImportError:
            logger.error("Redis package not installed. Install with 'pip install redis'")
            self.enabled = False
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.enabled = False

    async def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None

        try:
            data = await self.redis.get(key)
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        if not self.enabled:
            return False

        try:
            data = pickle.dumps(value)
            await self.redis.set(key, data, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        if not self.enabled:
            return False

        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Atomic increment operation with optional TTL."""
        if not self.enabled:
            return 0

        try:
            value = await self.redis.incrby(key, amount)
            if ttl and value == amount:
                await self.redis.expire(key, ttl)
            return value
        except Exception as e:
            logger.error(f"Redis increment error for key {key}: {e}")
            return 0


class CacheService:
    """
    Unified cache service with automatic fallback.

    Features:
    - Redis primary with memory fallback
    - Automatic circuit breaker for resilience
    - <500ms performance for lead analysis
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize cache backends."""
        self.backend: AbstractCache = None
        self.fallback_backend: AbstractCache = MemoryCache()

        # Try Redis first if configured
        if settings.redis_url:
            try:
                self.backend = RedisCache(settings.redis_url)
                if not getattr(self.backend, 'enabled', False):
                    logger.warning("Redis unavailable, using memory cache")
                    self.backend = self.fallback_backend
                else:
                    logger.info("Redis cache initialized with memory fallback")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis: {e}")
                self.backend = self.fallback_backend
        else:
            self.backend = self.fallback_backend
            logger.info("Using MemoryCache (no Redis configured)")

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Checks the primary backend first.  When it returns None (cache miss
        **or** an internally-caught error such as a Redis connection failure)
        the fallback backend is also consulted so that data written through
        ``set()`` — which always saves to both backends — is still reachable.
        """
        try:
            result = await self.backend.get(key)
            if result is not None:
                return result
        except Exception as e:
            logger.error(f"Cache get error: {e}")

        # Fallback: MemoryCache keeps a copy of every value written via set()
        if self.fallback_backend != self.backend:
            return await self.fallback_backend.get(key)
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache."""
        try:
            result = await self.backend.set(key, value, ttl)
            # Also set in fallback if using Redis
            if self.fallback_backend != self.backend:
                await self.fallback_backend.set(key, value, ttl)
            return result
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            if self.fallback_backend != self.backend:
                return await self.fallback_backend.set(key, value, ttl)
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            result = await self.backend.delete(key)
            if self.fallback_backend != self.backend:
                await self.fallback_backend.delete(key)
            return result
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Atomic increment operation."""
        if hasattr(self.backend, 'increment'):
            return await self.backend.increment(key, amount, ttl)
        current = await self.get(key) or 0
        new_value = int(current) + amount
        await self.set(key, new_value, ttl or 300)
        return new_value

    async def cached_computation(
        self,
        key: str,
        computation_func,
        ttl: int = 300,
        *args,
        **kwargs
    ) -> Any:
        """
        Cache the result of a computation.

        Checks cache first, computes if miss, caches result.
        Critical for <500ms lead analysis performance.
        """
        import asyncio

        start_time = time.time()

        # Check cache first
        cached_result = await self.get(key)
        if cached_result is not None:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"Cache HIT for {key} ({elapsed_ms:.1f}ms)")

            # Emit cache hit event
            try:
                await event_broker.publish_cache_event(
                    "cache.hit",
                    cache_key=key[:100],  # Truncate for privacy
                    response_time_ms=elapsed_ms,
                    data_size_bytes=len(str(cached_result)) if cached_result else 0
                )
            except Exception as e:
                logger.warning(f"Failed to publish cache hit event: {e}")

            return cached_result

        # Compute result
        logger.debug(f"Cache MISS for {key}, computing...")

        # Emit cache miss event
        try:
            await event_broker.publish_cache_event(
                "cache.miss",
                cache_key=key[:100]  # Truncate for privacy
            )
        except Exception as e:
            logger.warning(f"Failed to publish cache miss event: {e}")
        compute_start = time.time()

        try:
            if asyncio.iscoroutinefunction(computation_func):
                result = await computation_func(*args, **kwargs)
            else:
                result = computation_func(*args, **kwargs)

            compute_time_ms = (time.time() - compute_start) * 1000

            # Cache the result
            await self.set(key, result, ttl)

            # Emit cache set event
            try:
                await event_broker.publish_cache_event(
                    "cache.set",
                    cache_key=key[:100],  # Truncate for privacy
                    ttl_seconds=ttl,
                    data_size_bytes=len(str(result)) if result else 0
                )
            except Exception as e:
                logger.warning(f"Failed to publish cache set event: {e}")

            total_time_ms = (time.time() - start_time) * 1000
            logger.debug(f"Cached {key} (compute: {compute_time_ms:.1f}ms, total: {total_time_ms:.1f}ms)")

            return result
        except Exception as e:
            logger.error(f"Computation failed for key {key}: {e}")
            raise


# Global cache instance
def get_cache_service() -> CacheService:
    """Get the global cache service instance."""
    return CacheService()


class PerformanceCache:
    """
    High-performance caching for Claude AI lead intelligence responses.

    Specialized wrapper around CacheService for lead analysis with:
    - Message + context-based cache keys (MD5 hashing)
    - TTL-based expiration (default 300s)
    - Optimized for <100ms cache hits
    - Integrated with Redis + Memory backend

    Extracted from jorge_deployment_package/jorge_claude_intelligence.py
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self.cache_service = get_cache_service()
        logger.info(f"Initialized PerformanceCache with {ttl_seconds}s TTL")

    def _get_cache_key(self, message: str, context: Dict = None) -> str:
        """Generate cache key from message and context using MD5 hash"""
        import hashlib
        content = message + str(context or {})
        return f"lead_intel:{hashlib.md5(content.encode()).hexdigest()}"

    async def get(self, message: str, context: Dict = None) -> Optional[Dict]:
        """
        Get cached analysis if available and not expired.

        Returns cached lead intelligence analysis or None if cache miss.
        Optimized for <100ms response time.
        """
        cache_key = self._get_cache_key(message, context)

        try:
            cached_data = await self.cache_service.get(cache_key)
            if cached_data:
                # Return just the analysis portion
                return cached_data.get("analysis")
            return None
        except Exception as e:
            logger.error(f"PerformanceCache get error: {e}")
            return None

    async def set(self, message: str, analysis: Dict, context: Dict = None):
        """
        Cache analysis result with TTL.

        Stores lead intelligence analysis with timestamp for debugging.
        """
        import datetime

        cache_key = self._get_cache_key(message, context)

        cached_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "analysis": analysis,
            "message_hash": cache_key.split(":")[-1][:8]  # For debugging
        }

        try:
            await self.cache_service.set(cache_key, cached_data, self.ttl_seconds)
            logger.debug(f"Cached lead analysis: {cache_key[:20]}... (TTL: {self.ttl_seconds}s)")
        except Exception as e:
            logger.error(f"PerformanceCache set error: {e}")
