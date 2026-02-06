"""
WebSocket Manager for Jorge Real Estate AI Dashboard

Manages WebSocket connections for real-time event broadcasting.
Features:
- Connection lifecycle management (connect, disconnect, heartbeat)
- Redis pub/sub subscription for event broadcasting
- Automatic reconnection handling
- Event filtering per client (optional)
- Connection registry with client tracking
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis

from bots.shared.config import settings
from bots.shared.logger import get_logger
from bots.shared.event_broker import event_broker
from bots.shared.event_models import BaseEvent, EventType, create_event

logger = get_logger(__name__)


class WebSocketManager:
    """
    WebSocket connection manager for Jorge Real Estate AI Dashboard.

    Handles:
    - Multiple WebSocket client connections
    - Redis pub/sub event subscription
    - Real-time event broadcasting to clients
    - Connection heartbeat and cleanup
    - Error handling and recovery
    """

    def __init__(self):
        # Connection registry: client_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

        # Client metadata: client_id -> connection info
        self.client_metadata: Dict[str, Dict] = {}

        # Redis connection for pub/sub
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._redis_listener_task: Optional[asyncio.Task] = None
        self._running = False

        # Metrics
        self.total_connections = 0
        self.events_broadcast = 0
        self.heartbeats_sent = 0

        logger.info("WebSocketManager initialized")

    async def initialize(self):
        """Initialize Redis connection and start background tasks"""
        if self._running:
            return

        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(settings.redis_url)
            await self.redis_client.ping()

            # Start background tasks
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._redis_listener_task = asyncio.create_task(self._redis_listener())

            self._running = True
            logger.info("WebSocketManager started with Redis connection")

        except Exception as e:
            logger.error(f"Failed to initialize WebSocketManager: {e}")
            raise

    async def shutdown(self):
        """Shutdown WebSocket manager and cleanup connections"""
        self._running = False

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._redis_listener_task:
            self._redis_listener_task.cancel()

        # Close all WebSocket connections
        for client_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.close(code=1001, reason="Server shutdown")
            except Exception:
                pass

        # Close Redis connection
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()

        self.active_connections.clear()
        self.client_metadata.clear()

        logger.info("WebSocketManager shutdown complete")

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """
        Accept new WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            client_id: Optional client identifier

        Returns:
            Assigned client ID
        """
        if not client_id:
            client_id = f"client_{uuid4().hex[:8]}"

        try:
            # Accept WebSocket connection
            await websocket.accept()

            # Register connection
            self.active_connections[client_id] = websocket
            self.client_metadata[client_id] = {
                "connected_at": datetime.now(),
                "last_heartbeat": datetime.now(),
                "events_received": 0
            }

            self.total_connections += 1

            logger.info(f"WebSocket client {client_id} connected (total: {len(self.active_connections)})")

            # Send recent events to new client (last 60 seconds)
            await self._send_recent_events(websocket, client_id)

            return client_id

        except Exception as e:
            logger.error(f"Failed to connect WebSocket client {client_id}: {e}")
            raise

    async def disconnect(self, client_id: str):
        """
        Disconnect WebSocket client.

        Args:
            client_id: Client identifier
        """
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.close()
            except Exception:
                pass  # Connection might already be closed

            # Remove from registry
            del self.active_connections[client_id]
            del self.client_metadata[client_id]

            logger.info(f"WebSocket client {client_id} disconnected (remaining: {len(self.active_connections)})")

    async def broadcast(self, event: BaseEvent):
        """
        Broadcast event to all connected WebSocket clients.

        Args:
            event: Event to broadcast
        """
        if not self.active_connections:
            return

        # Serialize event
        event_data = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "source": event.source,
            "category": event.category.value,
            "payload": event.sanitize_payload()  # Remove sensitive fields
        }

        disconnected_clients = []

        # Broadcast to all connected clients
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(event_data)

                # Update client metadata
                if client_id in self.client_metadata:
                    self.client_metadata[client_id]["events_received"] += 1

            except WebSocketDisconnect:
                disconnected_clients.append(client_id)
            except Exception as e:
                logger.warning(f"Failed to send event to client {client_id}: {e}")
                disconnected_clients.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)

        if disconnected_clients:
            logger.debug(f"Cleaned up {len(disconnected_clients)} disconnected clients")

        self.events_broadcast += 1

    async def send_to_client(self, client_id: str, event: BaseEvent):
        """
        Send event to specific client.

        Args:
            client_id: Target client ID
            event: Event to send
        """
        if client_id not in self.active_connections:
            logger.warning(f"Client {client_id} not found for targeted event")
            return

        websocket = self.active_connections[client_id]

        try:
            event_data = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "source": event.source,
                "category": event.category.value,
                "payload": event.sanitize_payload()
            }

            await websocket.send_json(event_data)

            # Update client metadata
            if client_id in self.client_metadata:
                self.client_metadata[client_id]["events_received"] += 1

        except WebSocketDisconnect:
            await self.disconnect(client_id)
        except Exception as e:
            logger.error(f"Failed to send targeted event to client {client_id}: {e}")

    async def _send_recent_events(self, websocket: WebSocket, client_id: str):
        """Send recent events to newly connected client"""
        try:
            # Get events from last 60 seconds
            recent_events = await event_broker.get_recent_events(
                since=datetime.now() - timedelta(seconds=60),
                limit=50
            )

            if recent_events:
                logger.info(f"Sending {len(recent_events)} recent events to client {client_id}")

                for event in recent_events:
                    event_data = {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "timestamp": event.timestamp.isoformat(),
                        "source": event.source,
                        "category": event.category.value,
                        "payload": event.sanitize_payload()
                    }

                    await websocket.send_json(event_data)

                # Update client metadata
                if client_id in self.client_metadata:
                    self.client_metadata[client_id]["events_received"] += len(recent_events)

        except Exception as e:
            logger.error(f"Failed to send recent events to client {client_id}: {e}")

    async def _redis_listener(self):
        """Background task to listen for Redis pub/sub events"""
        while self._running:
            try:
                # Subscribe to all event channels
                pubsub = self.redis_client.pubsub()
                await pubsub.subscribe(
                    "jorge:events:leads",
                    "jorge:events:ghl",
                    "jorge:events:cache",
                    "jorge:events:system"
                )

                logger.info("Redis pub/sub listener started")

                async for message in pubsub.listen():
                    if not self._running:
                        break

                    if message["type"] == "message":
                        try:
                            # Parse event data
                            event_data = json.loads(message["data"].decode())

                            # Recreate event object
                            event_type = event_data.get("event_type")
                            if event_type:
                                event = create_event(event_type, **event_data)
                                await self.broadcast(event)

                        except Exception as e:
                            logger.warning(f"Failed to process Redis event: {e}")
                            continue

                await pubsub.close()

            except Exception as e:
                if self._running:  # Only log if we're supposed to be running
                    logger.error(f"Redis listener error: {e}")
                    await asyncio.sleep(5)  # Wait before retry

    async def _heartbeat_loop(self):
        """Background task to send heartbeat pings to connected clients"""
        while self._running:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds

                if not self.active_connections:
                    continue

                heartbeat_data = {
                    "event_type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                    "active_connections": len(self.active_connections)
                }

                disconnected_clients = []

                for client_id, websocket in self.active_connections.items():
                    try:
                        await websocket.send_json(heartbeat_data)

                        # Update last heartbeat time
                        if client_id in self.client_metadata:
                            self.client_metadata[client_id]["last_heartbeat"] = datetime.now()

                    except WebSocketDisconnect:
                        disconnected_clients.append(client_id)
                    except Exception as e:
                        logger.warning(f"Heartbeat failed for client {client_id}: {e}")
                        disconnected_clients.append(client_id)

                # Clean up failed heartbeats
                for client_id in disconnected_clients:
                    await self.disconnect(client_id)

                if disconnected_clients:
                    logger.debug(f"Heartbeat cleanup: {len(disconnected_clients)} clients disconnected")

                self.heartbeats_sent += 1

            except Exception as e:
                if self._running:  # Only log if we're supposed to be running
                    logger.error(f"Heartbeat loop error: {e}")
                    await asyncio.sleep(10)  # Wait before retry

    def get_active_connections(self) -> int:
        """Get number of active WebSocket connections"""
        return len(self.active_connections)

    def get_connection_info(self, client_id: str) -> Optional[Dict]:
        """Get connection information for specific client"""
        return self.client_metadata.get(client_id)

    def get_metrics(self) -> Dict:
        """Get WebSocket manager metrics"""
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self.total_connections,
            "events_broadcast": self.events_broadcast,
            "heartbeats_sent": self.heartbeats_sent,
            "running": self._running,
            "client_metadata": {
                client_id: {
                    "connected_duration_seconds": (
                        datetime.now() - metadata["connected_at"]
                    ).total_seconds(),
                    "events_received": metadata["events_received"],
                    "last_heartbeat_ago_seconds": (
                        datetime.now() - metadata["last_heartbeat"]
                    ).total_seconds()
                }
                for client_id, metadata in self.client_metadata.items()
            }
        }

    async def health_check(self) -> Dict:
        """Health check for WebSocket manager"""
        health_data = {
            "websocket_manager_running": self._running,
            "active_connections": len(self.active_connections),
            "redis_connected": False,
            "timestamp": datetime.now().isoformat()
        }

        try:
            if self.redis_client:
                await self.redis_client.ping()
                health_data["redis_connected"] = True
        except Exception as e:
            health_data["redis_error"] = str(e)

        return health_data


# Global singleton instance
websocket_manager = WebSocketManager()