"""
Event Broker for Jorge Real Estate AI Real-Time Dashboard

This module provides centralized event publishing and subscription using Redis pub/sub.
Features:
- Publish events to Redis channels
- Persist events to Redis Streams (60-second buffer)
- Subscribe to event channels
- Circuit breaker for Redis failures
- Health monitoring and metrics
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from bots.shared.config import settings
from bots.shared.logger import get_logger
from bots.shared.event_models import BaseEvent, EventType, create_event, get_event_channel, get_event_stream

logger = get_logger(__name__)


class CircuitBreakerError(Exception):
    """Circuit breaker is open, operations not allowed"""
    pass


class CircuitBreaker:
    """Simple circuit breaker for Redis operations"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open

    def is_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self.state == "closed":
            return False

        if self.state == "open":
            # Check if timeout has passed
            if self.last_failure_time and \
               (datetime.now() - self.last_failure_time).seconds >= self.timeout:
                self.state = "half-open"
                return False
            return True

        # half-open state - allow one request
        return False

    def record_success(self):
        """Record successful operation"""
        self.failure_count = 0
        self.state = "closed"

    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.is_open():
            raise CircuitBreakerError("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e


class EventBroker:
    """
    Centralized event broker for Jorge Real Estate AI system.

    Manages Redis pub/sub for real-time events and Redis Streams for persistence.
    Singleton pattern ensures single connection pool across the application.
    """

    _instance: Optional['EventBroker'] = None
    _initialized = False

    def __new__(cls) -> 'EventBroker':
        if cls._instance is None:
            cls._instance = super(EventBroker, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not EventBroker._initialized:
            # Redis connection configuration
            self.redis_url = settings.redis_url
            self.connection_pool: Optional[ConnectionPool] = None
            self.redis_client: Optional[redis.Redis] = None
            self.pubsub_client: Optional[redis.Redis] = None

            # Circuit breaker for resilience
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                timeout=30
            )

            # Event persistence settings
            self.event_retention_seconds = 60  # Keep events for 60 seconds
            self.max_stream_length = 1000      # Max events per stream

            # Metrics tracking
            self.published_count = 0
            self.failed_count = 0
            self.subscribers: Dict[str, Set[Callable]] = {}

            # Background task management
            self._cleanup_task: Optional[asyncio.Task] = None
            self._running = False

            EventBroker._initialized = True

    async def initialize(self):
        """Initialize Redis connections and start background tasks"""
        if self._running:
            return

        try:
            # Create connection pool
            self.connection_pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=50,
                decode_responses=False,
                socket_timeout=2,
                socket_connect_timeout=2,
                health_check_interval=30
            )

            # Create Redis clients
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            self.pubsub_client = redis.Redis(connection_pool=self.connection_pool)

            # Test connection
            await self.redis_client.ping()
            logger.info("EventBroker initialized with Redis connection")

            # Start background cleanup task
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_events())
            self._running = True

        except Exception as e:
            logger.error(f"Failed to initialize EventBroker: {e}")
            raise

    async def shutdown(self):
        """Shutdown connections and cleanup"""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self.pubsub_client:
            await self.pubsub_client.close()

        if self.redis_client:
            await self.redis_client.close()

        if self.connection_pool:
            await self.connection_pool.disconnect()

        logger.info("EventBroker shutdown complete")

    @asynccontextmanager
    async def lifespan(self):
        """Async context manager for EventBroker lifecycle"""
        await self.initialize()
        try:
            yield self
        finally:
            await self.shutdown()

    async def publish(self, event: BaseEvent) -> bool:
        """
        Publish event to Redis channel and persist to stream.

        Args:
            event: Event to publish

        Returns:
            bool: True if published successfully, False otherwise
        """
        if not self._running:
            await self.initialize()

        try:
            result = await self.circuit_breaker.call(
                self._redis_publish, event
            )
            self.published_count += 1
            return result

        except CircuitBreakerError:
            logger.error("Event broker circuit open - event not published")
            await self._fallback_publish(event)
            return False

        except Exception as e:
            logger.error(f"Failed to publish event {event.event_type}: {e}")
            self.failed_count += 1
            await self._fallback_publish(event)
            return False

    async def _redis_publish(self, event: BaseEvent) -> bool:
        """Publish event to Redis channel and stream"""
        channel = get_event_channel(event)
        stream = get_event_stream(event)

        # Serialize event
        event_data = event.model_dump(mode='json')
        event_json = json.dumps(event_data)

        # Use pipeline for atomic operation
        async with self.redis_client.pipeline() as pipeline:
            # Publish to channel for real-time subscribers
            pipeline.publish(channel, event_json)

            # Add to stream for persistence (with TTL)
            pipeline.xadd(
                stream,
                event_data,
                maxlen=self.max_stream_length,
                approximate=True
            )

            # Set expiration on stream entries (cleanup handled separately)
            results = await pipeline.execute()

        # Check if publish was successful (returns number of subscribers)
        publish_result, stream_result = results

        logger.debug(
            f"Published {event.event_type} to {channel} "
            f"(subscribers: {publish_result}, stream_id: {stream_result})"
        )

        return True

    async def _fallback_publish(self, event: BaseEvent):
        """Fallback when Redis is unavailable - log to file for recovery"""
        fallback_file = "/tmp/jorge_events_fallback.jsonl"

        try:
            event_data = {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "source": event.source,
                "payload": event.payload
            }

            with open(fallback_file, "a") as f:
                f.write(json.dumps(event_data) + "\n")

            logger.warning(f"Event {event.event_type} logged to fallback file")

        except Exception as e:
            logger.error(f"Fallback publish failed: {e}")

    async def subscribe(self, channel: str, callback: Callable[[BaseEvent], None]):
        """
        Subscribe to event channel.

        Args:
            channel: Redis channel name
            callback: Function to call when event received
        """
        if channel not in self.subscribers:
            self.subscribers[channel] = set()

        self.subscribers[channel].add(callback)
        logger.info(f"Subscribed to channel {channel}")

    async def unsubscribe(self, channel: str, callback: Callable[[BaseEvent], None]):
        """Unsubscribe from event channel"""
        if channel in self.subscribers:
            self.subscribers[channel].discard(callback)
            if not self.subscribers[channel]:
                del self.subscribers[channel]

    async def get_recent_events(
        self,
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[BaseEvent]:
        """
        Get recent events from Redis Streams.

        Args:
            since: Get events after this timestamp
            event_types: Filter by event types
            limit: Maximum events to return

        Returns:
            List of events
        """
        if not self._running:
            await self.initialize()

        if since is None:
            since = datetime.now() - timedelta(seconds=self.event_retention_seconds)

        events = []

        try:
            # Get events from all streams
            streams = [
                "jorge:stream:leads",
                "jorge:stream:ghl",
                "jorge:stream:cache",
                "jorge:stream:system"
            ]

            for stream in streams:
                try:
                    # Convert datetime to Redis timestamp
                    since_ms = int(since.timestamp() * 1000)

                    # Read from stream
                    stream_events = await self.redis_client.xrevrange(
                        stream,
                        count=limit,
                        min=f"{since_ms}-0"
                    )

                    for event_id, event_data in stream_events:
                        try:
                            # Reconstruct event
                            event_type = event_data.get(b'event_type', b'').decode()

                            # Filter by event type if specified
                            if event_types and event_type not in event_types:
                                continue

                            # Recreate event object
                            event_dict = {
                                k.decode() if isinstance(k, bytes) else k:
                                v.decode() if isinstance(v, bytes) else v
                                for k, v in event_data.items()
                            }

                            # Convert payload back to dict if it's a JSON string
                            if 'payload' in event_dict:
                                try:
                                    event_dict['payload'] = json.loads(event_dict['payload'])
                                except (json.JSONDecodeError, TypeError):
                                    pass

                            event = create_event(event_type, **event_dict)
                            events.append(event)

                        except Exception as e:
                            logger.warning(f"Failed to parse event {event_id}: {e}")
                            continue

                except redis.ResponseError as e:
                    logger.warning(f"Stream {stream} not found or error: {e}")
                    continue

            # Sort by timestamp (most recent first)
            events.sort(key=lambda x: x.timestamp, reverse=True)

            return events[:limit]

        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return []

    async def _cleanup_expired_events(self):
        """Background task to cleanup expired events from streams"""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute

                if not self._running:
                    break

                # Calculate cutoff timestamp
                cutoff = datetime.now() - timedelta(seconds=self.event_retention_seconds)
                cutoff_ms = int(cutoff.timestamp() * 1000)

                streams = [
                    "jorge:stream:leads",
                    "jorge:stream:ghl",
                    "jorge:stream:cache",
                    "jorge:stream:system"
                ]

                for stream in streams:
                    try:
                        # Remove events older than retention period
                        await self.redis_client.xtrim(
                            stream,
                            minid=f"{cutoff_ms}-0",
                            approximate=True
                        )

                    except redis.ResponseError:
                        # Stream doesn't exist yet
                        continue

                logger.debug("Cleaned up expired events from streams")

            except Exception as e:
                logger.error(f"Error during event cleanup: {e}")
                await asyncio.sleep(30)  # Wait before retry

    async def health_check(self) -> Dict[str, Any]:
        """Check health of event broker and Redis connection"""
        health_data = {
            "redis_connected": False,
            "circuit_breaker_state": self.circuit_breaker.state,
            "published_count": self.published_count,
            "failed_count": self.failed_count,
            "active_subscribers": len(self.subscribers),
            "timestamp": datetime.now().isoformat()
        }

        try:
            if self.redis_client:
                await self.redis_client.ping()
                health_data["redis_connected"] = True

                # Get Redis info
                info = await self.redis_client.info("memory")
                health_data["redis_memory_used"] = info.get("used_memory_human", "unknown")

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_data["error"] = str(e)

        return health_data

    def get_metrics(self) -> Dict[str, Any]:
        """Get event broker metrics"""
        return {
            "published_count": self.published_count,
            "failed_count": self.failed_count,
            "success_rate": (
                self.published_count / (self.published_count + self.failed_count)
                if (self.published_count + self.failed_count) > 0
                else 1.0
            ),
            "circuit_breaker_state": self.circuit_breaker.state,
            "active_subscribers": len(self.subscribers),
            "running": self._running
        }


# Global singleton instance
event_broker = EventBroker()


# Convenience functions for specific event types
async def publish_lead_event(event_type: str, **kwargs) -> bool:
    """Publish lead-related event"""
    event = create_event(event_type, **kwargs)
    return await event_broker.publish(event)


async def publish_ghl_event(event_type: str, **kwargs) -> bool:
    """Publish GHL-related event"""
    event = create_event(event_type, **kwargs)
    return await event_broker.publish(event)


async def publish_cache_event(event_type: str, **kwargs) -> bool:
    """Publish cache-related event"""
    event = create_event(event_type, **kwargs)
    return await event_broker.publish(event)


async def publish_system_event(event_type: str, **kwargs) -> bool:
    """Publish system-related event"""
    event = create_event(event_type, **kwargs)
    return await event_broker.publish(event)