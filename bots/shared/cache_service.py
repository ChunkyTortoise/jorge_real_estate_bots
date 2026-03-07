"""
Cache Service for Jorge's Real Estate Bots.

Provides Redis-backed caching with memory fallback for <500ms performance.
Simplified version from EnterpriseHub focused on Jorge's needs.
"""
from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Any, Dict, Optional

from bots.shared.config import settings
from bots.shared.event_broker import event_broker
from bots.shared.logger import get_logger

logger = get_logger(__name__)


def _json_default(obj: Any) -> Any:
    """JSON serialiser for types not handled by the stdlib encoder."""
    if isinstance(obj, (datetime, date)):
        return {"__type__": "datetime", "value": obj.isoformat()}
    if isinstance(obj, set):
        return {"__type__": "set", "value": list(obj)}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


def _json_hook(d: dict) -> Any:
    """JSON object hook to reconstruct special types."""
    if d.get("__type__") == "datetime":
        return datetime.fromisoformat(d["value"])
    if d.get("__type__") == "set":
        return set(d["value"])
    return d


def _cache_dumps(value: Any) -> bytes:
    return json.dumps(value, default=_json_default).encode()


def _cache_loads(data: bytes) -> Any:
    return json.loads(data, object_hook=_json_hook)


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

    @abstractmethod
    async def sadd(self, key: str, *values: str, ttl: Optional[int] = None) -> int:
        """Add one or more values to a set."""
        pass

    @abstractmethod
    async def smembers(self, key: str) -> set[str]:
        """Get all members from a set."""
        pass

    @abstractmethod
    async def srem(self, key: str, *values: str) -> int:
        """Remove one or more values from a set."""
        pass

    @abstractmethod
    async def setnx(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value only if key does not exist. Returns True if set, False if already exists."""
        pass

    @abstractmethod
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Atomic increment operation with optional TTL. Returns new value."""
        pass


class MemoryCache(AbstractCache):
    """In-memory cache fallback."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
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

    async def sadd(self, key: str, *values: str, ttl: Optional[int] = None) -> int:
        if not values:
            return 0

        current = self._cache.get(key)
        if not isinstance(current, set):
            current = set()

        before_count = len(current)
        current.update(values)
        self._cache[key] = current
        if ttl:
            self._expiry[key] = time.time() + ttl
        elif key not in self._expiry:
            self._expiry[key] = time.time() + 86400
        return len(current) - before_count

    async def smembers(self, key: str) -> set[str]:
        if time.time() > self._expiry.get(key, 0):
            await self.delete(key)
            return set()

        value = self._cache.get(key)
        if isinstance(value, set):
            return set(value)
        return set()

    async def srem(self, key: str, *values: str) -> int:
        if not values:
            return 0

        current = self._cache.get(key)
        if not isinstance(current, set):
            return 0

        removed = 0
        for value in values:
            if value in current:
                current.remove(value)
                removed += 1

        if current:
            self._cache[key] = current
        else:
            await self.delete(key)

        return removed

    async def setnx(self, key: str, value: Any, ttl: int = 300) -> bool:
        async with self._lock:
            existing = await self.get(key)
            if existing is not None:
                return False
            await self.set(key, value, ttl)
            return True

    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        async with self._lock:
            current = await self.get(key)
            new_value = (int(current) if current is not None else 0) + amount
            await self.set(key, new_value, ttl or 300)
            return new_value


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

    async def validate_connection(self) -> bool:
        """Ping Redis to confirm connectivity. Disables cache on failure."""
        try:
            await self.redis.ping()  # type: ignore[misc]
            logger.info("Redis connected successfully")
            return True
        except Exception as e:
            logger.critical(f"Redis connection failed, falling back to MemoryCache: {e}")
            self.enabled = False
            return False

    async def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None

        try:
            data = await self.redis.get(key)
            if not data:
                return None
            try:
                return _cache_loads(data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.warning(f"Non-JSON cache value for key {key}, discarding")
                return None
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        if not self.enabled:
            return False

        try:
            data = _cache_dumps(value)
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

    async def setnx(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value only if key does not exist (atomic). Returns True if set, False if already exists."""
        if not self.enabled:
            return False

        try:
            data = _cache_dumps(value)
            result = await self.redis.set(key, data, nx=True, ex=ttl)
            return result is not None
        except Exception as e:
            logger.error(f"Redis setnx error for key {key}: {e}")
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

    async def sadd(self, key: str, *values: str, ttl: Optional[int] = None) -> int:
        if not self.enabled or not values:
            return 0
        try:
            added = await self.redis.sadd(key, *values)
            if ttl:
                await self.redis.expire(key, ttl)
            return int(added)
        except Exception as e:
            logger.error(f"Redis sadd error for key {key}: {e}")
            return 0

    async def smembers(self, key: str) -> set[str]:
        if not self.enabled:
            return set()
        try:
            members = await self.redis.smembers(key)
            return {
                m.decode("utf-8") if isinstance(m, bytes) else str(m)
                for m in members
            }
        except Exception as e:
            logger.error(f"Redis smembers error for key {key}: {e}")
            return set()

    async def srem(self, key: str, *values: str) -> int:
        if not self.enabled or not values:
            return 0
        try:
            removed = await self.redis.srem(key, *values)
            return int(removed)
        except Exception as e:
            logger.error(f"Redis srem error for key {key}: {e}")
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
                    logger.warning("Redis unavailable, falling back to MemoryCache")
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

    async def setnx(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value only if key does not exist (atomic)."""
        try:
            return await self.backend.setnx(key, value, ttl)
        except Exception as e:
            logger.error(f"Cache setnx error: {e}")
            if self.fallback_backend != self.backend:
                return await self.fallback_backend.setnx(key, value, ttl)
            return False

    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        """Atomic increment operation."""
        try:
            return await self.backend.increment(key, amount, ttl)
        except Exception as e:
            logger.error(f"Cache increment error: {e}")
            if self.fallback_backend != self.backend:
                return await self.fallback_backend.increment(key, amount, ttl)
            return 0

    async def sadd(self, key: str, *values: str, ttl: Optional[int] = None) -> int:
        """Add one or more values to a set in cache backends."""
        added = await self.backend.sadd(key, *values, ttl=ttl)
        if self.fallback_backend != self.backend:
            await self.fallback_backend.sadd(key, *values, ttl=ttl)
        return added

    async def smembers(self, key: str) -> set[str]:
        """Get all members from a set in cache backends."""
        members = await self.backend.smembers(key)
        if members:
            return members
        if self.fallback_backend != self.backend:
            return await self.fallback_backend.smembers(key)
        return set()

    async def srem(self, key: str, *values: str) -> int:
        """Remove one or more values from a set in cache backends."""
        removed = await self.backend.srem(key, *values)
        if self.fallback_backend != self.backend:
            await self.fallback_backend.srem(key, *values)
        return removed

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
        from datetime import timezone as _tz

        cache_key = self._get_cache_key(message, context)

        cached_data = {
            "timestamp": datetime.now(_tz.utc).isoformat(),
            "analysis": analysis,
            "message_hash": cache_key.split(":")[-1][:8]  # For debugging
        }

        try:
            await self.cache_service.set(cache_key, cached_data, self.ttl_seconds)
            logger.debug(f"Cached lead analysis: {cache_key[:20]}... (TTL: {self.ttl_seconds}s)")
        except Exception as e:
            logger.error(f"PerformanceCache set error: {e}")
