"""
Event Client for Jorge Real Estate AI Dashboard

HTTP client for fetching recent events and performance metrics.
Provides polling fallback when WebSocket connection is not available.
"""

import httpx
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from bots.shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for dashboard"""
    avg_response_time_ms: float
    cache_hit_rate: float
    five_minute_compliance: bool
    active_connections: int
    events_per_second: float
    timestamp: datetime


class EventClient:
    """
    HTTP client for Jorge Real Estate AI event system.

    Provides:
    - Recent events fetching
    - Performance metrics retrieval
    - Health monitoring
    - Retry logic with exponential backoff
    """

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 5.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

        # HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

        # Retry configuration
        self.max_retries = 3
        self.retry_backoff = [1, 2, 4]  # Exponential backoff in seconds

        logger.info(f"EventClient initialized for {self.base_url}")

    async def get_recent_events(
        self,
        since_minutes: int = 15,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent events from the API.

        Args:
            since_minutes: Get events from last N minutes
            event_types: Filter by specific event types
            limit: Maximum number of events

        Returns:
            List of event dictionaries
        """
        try:
            params = {
                'since_minutes': min(since_minutes, 60),  # Max 1 hour
                'limit': min(limit, 500)  # Max 500 events
            }

            if event_types:
                params['event_types'] = ','.join(event_types)

            response = await self._make_request_with_retry(
                "GET",
                "/api/events/recent",
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                logger.debug(f"Fetched {len(events)} recent events")
                return events
            else:
                logger.warning(f"Failed to fetch events: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error fetching recent events: {e}")
            return []

    async def get_performance_metrics(self) -> Optional[PerformanceMetrics]:
        """
        Get performance metrics from the API.

        Returns:
            PerformanceMetrics object or None if failed
        """
        try:
            response = await self._make_request_with_retry(
                "GET",
                "/performance"
            )

            if response.status_code == 200:
                data = response.json()

                metrics = PerformanceMetrics(
                    avg_response_time_ms=data.get('avg_response_time_ms', 0.0),
                    cache_hit_rate=data.get('cache_hit_rate', 0.0),
                    five_minute_compliance=data.get('five_minute_rule_compliant', True),
                    active_connections=0,  # Will be updated from WebSocket status
                    events_per_second=0,   # Will be calculated from events
                    timestamp=datetime.now()
                )

                logger.debug("Fetched performance metrics")
                return metrics
            else:
                logger.warning(f"Failed to fetch performance metrics: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching performance metrics: {e}")
            return None

    async def get_websocket_status(self) -> Dict[str, Any]:
        """
        Get WebSocket manager status.

        Returns:
            Dictionary with WebSocket status and metrics
        """
        try:
            response = await self._make_request_with_retry(
                "GET",
                "/api/websocket/status"
            )

            if response.status_code == 200:
                data = response.json()
                logger.debug("Fetched WebSocket status")
                return data
            else:
                logger.warning(f"Failed to fetch WebSocket status: {response.status_code}")
                return {"status": "unknown"}

        except Exception as e:
            logger.error(f"Error fetching WebSocket status: {e}")
            return {"status": "error", "error": str(e)}

    async def get_event_system_health(self) -> Dict[str, Any]:
        """
        Get complete event system health.

        Returns:
            Dictionary with health status of all components
        """
        try:
            response = await self._make_request_with_retry(
                "GET",
                "/api/events/health"
            )

            if response.status_code == 200:
                data = response.json()
                logger.debug("Fetched event system health")
                return data
            else:
                logger.warning(f"Failed to fetch event system health: {response.status_code}")
                return {"status": "unknown"}

        except Exception as e:
            logger.error(f"Error fetching event system health: {e}")
            return {"status": "error", "error": str(e)}

    async def health_check(self) -> bool:
        """
        Simple health check for the event API.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            response = await self._make_request_with_retry(
                "GET",
                "/health",
                retries=1  # Quick health check
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def _make_request_with_retry(
        self,
        method: str,
        path: str,
        retries: Optional[int] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method
            path: API path
            retries: Number of retries (uses default if None)
            **kwargs: Additional request parameters

        Returns:
            HTTP response

        Raises:
            httpx.RequestError: If all retries fail
        """
        if retries is None:
            retries = self.max_retries

        last_error = None

        for attempt in range(retries + 1):
            try:
                response = await self.client.request(method, path, **kwargs)

                # Don't retry for client errors (4xx)
                if 400 <= response.status_code < 500:
                    return response

                # Return successful responses
                if response.status_code < 400:
                    return response

                # Log server errors (5xx) and retry
                logger.warning(f"Server error {response.status_code} on attempt {attempt + 1}")

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")

            # Wait before retry (except on last attempt)
            if attempt < retries:
                wait_time = self.retry_backoff[min(attempt, len(self.retry_backoff) - 1)]
                await asyncio.sleep(wait_time)

        # All retries failed
        if last_error:
            raise last_error
        else:
            raise httpx.RequestError(f"Failed after {retries + 1} attempts")

    async def close(self):
        """Close the HTTP client and cleanup connections"""
        await self.client.aclose()
        logger.info("EventClient closed")

    def __del__(self):
        """Cleanup on deletion"""
        try:
            asyncio.create_task(self.close())
        except:
            pass  # Ignore cleanup errors


# Synchronous wrapper for Streamlit compatibility
class SyncEventClient:
    """
    Synchronous wrapper for EventClient to work with Streamlit.

    Streamlit doesn't handle async code well, so this wrapper
    provides synchronous methods that run async operations.
    """

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 5.0):
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[EventClient] = None

    def _get_client(self) -> EventClient:
        """Get or create async client"""
        if self._client is None:
            self._client = EventClient(self.base_url, self.timeout)
        return self._client

    def get_recent_events(
        self,
        since_minutes: int = 15,
        event_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Synchronous version of get_recent_events"""
        try:
            client = self._get_client()
            return asyncio.run(
                client.get_recent_events(since_minutes, event_types, limit)
            )
        except Exception as e:
            logger.error(f"Sync get_recent_events failed: {e}")
            return []

    def get_performance_metrics(self) -> Optional[PerformanceMetrics]:
        """Synchronous version of get_performance_metrics"""
        try:
            client = self._get_client()
            return asyncio.run(client.get_performance_metrics())
        except Exception as e:
            logger.error(f"Sync get_performance_metrics failed: {e}")
            return None

    def get_websocket_status(self) -> Dict[str, Any]:
        """Synchronous version of get_websocket_status"""
        try:
            client = self._get_client()
            return asyncio.run(client.get_websocket_status())
        except Exception as e:
            logger.error(f"Sync get_websocket_status failed: {e}")
            return {"status": "error", "error": str(e)}

    def health_check(self) -> bool:
        """Synchronous version of health_check"""
        try:
            client = self._get_client()
            return asyncio.run(client.health_check())
        except Exception as e:
            logger.error(f"Sync health_check failed: {e}")
            return False

    def close(self):
        """Close the client"""
        if self._client:
            try:
                asyncio.run(self._client.close())
            except Exception as e:
                logger.error(f"Error closing sync client: {e}")
            finally:
                self._client = None