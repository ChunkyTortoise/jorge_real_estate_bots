"""Real-time WebSocket and event polling routes for Lead Bot."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from bots.lead_bot.websocket_manager import websocket_manager
from bots.shared.auth_middleware import get_current_active_user
from bots.shared.auth_service import get_auth_service
from bots.shared.event_broker import event_broker
from bots.shared.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None, description="Optional client identifier"),
    token: Optional[str] = Query(None, description="JWT access token"),
):
    """WebSocket endpoint for real-time dashboard updates."""
    assigned_client_id = None

    try:
        auth_service = get_auth_service()
        if not token or not await auth_service.validate_token(token):
            await websocket.close(code=4401)
            return

        assigned_client_id = await websocket_manager.connect(websocket, client_id)
        logger.info(f"Dashboard WebSocket connected: {assigned_client_id}")

        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
                    continue
                logger.debug(f"Client {assigned_client_id} message: {data}")

        except WebSocketDisconnect:
            logger.info(f"Dashboard WebSocket disconnected: {assigned_client_id}")

    except Exception as e:
        logger.error(f"WebSocket error for client {assigned_client_id}: {e}")

    finally:
        if assigned_client_id:
            await websocket_manager.disconnect(assigned_client_id)


@router.get("/api/events/recent")
async def get_recent_events(
    since_minutes: int = Query(5, description="Get events from last N minutes"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to filter"),
    limit: int = Query(100, description="Maximum number of events to return"),
    user=Depends(get_current_active_user()),
):
    """HTTP polling fallback for WebSocket events."""
    try:
        event_type_list = None
        if event_types:
            event_type_list = [t.strip() for t in event_types.split(",")]

        since_minutes = min(since_minutes, 60)
        limit = min(limit, 500)

        since_time = datetime.now() - timedelta(minutes=since_minutes)
        events = await event_broker.get_recent_events(
            since=since_time,
            event_types=event_type_list,
            limit=limit
        )

        formatted_events = []
        for event in events:
            formatted_events.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "source": event.source,
                "category": event.category.value,
                "payload": event.sanitize_payload()
            })

        return {
            "events": formatted_events,
            "count": len(formatted_events),
            "since": since_time.isoformat(),
            "event_types_filter": event_type_list,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get recent events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve recent events: {str(e)}"
        )


@router.get("/api/websocket/status")
async def websocket_status(user=Depends(get_current_active_user())):
    """Get WebSocket manager status and metrics."""
    try:
        health_data = await websocket_manager.health_check()
        metrics_data = websocket_manager.get_metrics()

        return {
            "status": "healthy" if health_data["websocket_manager_running"] else "unhealthy",
            "health": health_data,
            "metrics": metrics_data,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"WebSocket status check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/api/events/health")
async def event_system_health(user=Depends(get_current_active_user())):
    """Combined health check for event broker + WebSocket manager."""
    try:
        broker_health = await event_broker.health_check()
        broker_metrics = event_broker.get_metrics()

        ws_health = await websocket_manager.health_check()
        ws_metrics = websocket_manager.get_metrics()

        overall_healthy = (
            broker_health.get("redis_connected", False) and
            ws_health.get("websocket_manager_running", False)
        )

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "event_broker": {
                "health": broker_health,
                "metrics": broker_metrics
            },
            "websocket_manager": {
                "health": ws_health,
                "metrics": ws_metrics
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Event system health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
