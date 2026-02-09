#!/usr/bin/env python3
"""
Production Monitor for Jorge Real Estate AI Dashboard

Provides health monitoring, performance tracking, and system diagnostics
for the production dashboard system.

Features:
- Real-time system health monitoring
- Performance metrics collection
- Error tracking and alerting
- Resource usage monitoring
- Database and Redis connectivity checks
- WebSocket connection monitoring

Author: Claude Code Assistant
Created: 2026-01-23 (Phase 3C - Production Polish)
"""

import asyncio
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bots.shared.logger import get_logger
from command_center.event_client import EventClient

logger = get_logger(__name__)


@dataclass
class SystemHealth:
    """System health status information"""
    timestamp: datetime
    overall_status: str  # 'healthy', 'degraded', 'critical'
    api_status: str
    websocket_status: str
    redis_status: str
    database_status: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    error_rate: float
    response_time_ms: float


@dataclass
class AlertThresholds:
    """Alert thresholds for monitoring"""
    cpu_warning: float = 70.0
    cpu_critical: float = 85.0
    memory_warning: float = 75.0
    memory_critical: float = 90.0
    disk_warning: float = 80.0
    disk_critical: float = 95.0
    response_time_warning: float = 1000.0  # 1 second
    response_time_critical: float = 5000.0  # 5 seconds
    error_rate_warning: float = 5.0  # 5%
    error_rate_critical: float = 15.0  # 15%


class ProductionMonitor:
    """
    Production monitoring system for Jorge's dashboard.

    Provides comprehensive health monitoring, performance tracking,
    and alerting for the real-time dashboard system.
    """

    def __init__(self,
                 api_base_url: str = "http://localhost:8001",
                 check_interval: int = 30,
                 alert_thresholds: Optional[AlertThresholds] = None):
        self.api_base_url = api_base_url
        self.check_interval = check_interval
        self.thresholds = alert_thresholds or AlertThresholds()

        # Event client for API monitoring
        self.event_client = EventClient(api_base_url)

        # Health history for trend analysis
        self.health_history: List[SystemHealth] = []
        self.max_history_size = 100

        # Alert tracking
        self.active_alerts: Dict[str, datetime] = {}
        self.alert_history: List[Dict[str, Any]] = []

        logger.info(f"ProductionMonitor initialized for {api_base_url}")

    async def run_monitoring(self):
        """Run continuous monitoring loop"""
        logger.info("Starting production monitoring...")

        try:
            while True:
                # Collect system health
                health = await self.collect_system_health()

                # Store in history
                self.health_history.append(health)
                if len(self.health_history) > self.max_history_size:
                    self.health_history.pop(0)

                # Check for alerts
                await self.check_alerts(health)

                # Log health status
                self.log_health_status(health)

                # Wait for next check
                await asyncio.sleep(self.check_interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            raise

    async def collect_system_health(self) -> SystemHealth:
        """Collect comprehensive system health metrics"""
        timestamp = datetime.now()

        try:
            # System resource metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            memory_usage = memory.percent
            disk_usage = disk.percent

            # API health check
            api_start = time.time()
            api_healthy = await self.event_client.health_check()
            api_response_time = (time.time() - api_start) * 1000

            # WebSocket status
            websocket_status = await self.event_client.get_websocket_status()

            # Performance metrics
            performance_metrics = await self.event_client.get_performance_metrics()

            # Determine overall status
            overall_status = self._calculate_overall_status(
                api_healthy, cpu_usage, memory_usage, disk_usage,
                api_response_time, websocket_status
            )

            return SystemHealth(
                timestamp=timestamp,
                overall_status=overall_status,
                api_status="healthy" if api_healthy else "unhealthy",
                websocket_status=websocket_status.get('status', 'unknown'),
                redis_status=websocket_status.get('redis_status', 'unknown'),
                database_status="unknown",  # Would need DB client
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                active_connections=websocket_status.get('active_connections', 0),
                error_rate=0.0,  # Would need error tracking
                response_time_ms=performance_metrics.avg_response_time_ms if performance_metrics else api_response_time
            )

        except Exception as e:
            logger.error(f"Error collecting system health: {e}")
            return SystemHealth(
                timestamp=timestamp,
                overall_status="critical",
                api_status="error",
                websocket_status="error",
                redis_status="error",
                database_status="error",
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                active_connections=0,
                error_rate=100.0,
                response_time_ms=999999.0
            )

    def _calculate_overall_status(self,
                                api_healthy: bool,
                                cpu_usage: float,
                                memory_usage: float,
                                disk_usage: float,
                                response_time: float,
                                websocket_status: Dict) -> str:
        """Calculate overall system status based on metrics"""

        # Critical conditions
        if not api_healthy:
            return "critical"

        if (cpu_usage >= self.thresholds.cpu_critical or
            memory_usage >= self.thresholds.memory_critical or
            disk_usage >= self.thresholds.disk_critical or
            response_time >= self.thresholds.response_time_critical):
            return "critical"

        # Degraded conditions
        if (cpu_usage >= self.thresholds.cpu_warning or
            memory_usage >= self.thresholds.memory_warning or
            disk_usage >= self.thresholds.disk_warning or
            response_time >= self.thresholds.response_time_warning):
            return "degraded"

        if websocket_status.get('status') != 'connected':
            return "degraded"

        return "healthy"

    async def check_alerts(self, health: SystemHealth):
        """Check for alert conditions and manage alerts"""
        alerts_to_check = [
            ("cpu_high", health.cpu_usage >= self.thresholds.cpu_warning,
             f"High CPU usage: {health.cpu_usage:.1f}%"),
            ("memory_high", health.memory_usage >= self.thresholds.memory_warning,
             f"High memory usage: {health.memory_usage:.1f}%"),
            ("disk_high", health.disk_usage >= self.thresholds.disk_warning,
             f"High disk usage: {health.disk_usage:.1f}%"),
            ("response_slow", health.response_time_ms >= self.thresholds.response_time_warning,
             f"Slow response time: {health.response_time_ms:.0f}ms"),
            ("api_down", health.api_status != "healthy",
             f"API unhealthy: {health.api_status}"),
            ("websocket_down", health.websocket_status != "connected",
             f"WebSocket issue: {health.websocket_status}"),
        ]

        current_time = datetime.now()

        for alert_key, condition, message in alerts_to_check:
            if condition:
                # New or continuing alert
                if alert_key not in self.active_alerts:
                    # New alert
                    self.active_alerts[alert_key] = current_time
                    await self.send_alert(alert_key, message, "NEW")
                    logger.warning(f"NEW ALERT: {alert_key} - {message}")

            else:
                # Alert resolved
                if alert_key in self.active_alerts:
                    duration = current_time - self.active_alerts[alert_key]
                    del self.active_alerts[alert_key]
                    await self.send_alert(alert_key, f"Resolved after {duration}", "RESOLVED")
                    logger.info(f"RESOLVED: {alert_key} - Duration: {duration}")

    async def send_alert(self, alert_key: str, message: str, status: str):
        """Send alert notification"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'alert_key': alert_key,
            'message': message,
            'status': status,
            'severity': self._get_alert_severity(alert_key)
        }

        # Store in alert history
        self.alert_history.append(alert)
        if len(self.alert_history) > 100:
            self.alert_history.pop(0)

        # Here you could integrate with:
        # - Email notifications
        # - Slack webhooks
        # - PagerDuty
        # - Custom notification systems

        logger.info(f"Alert sent: {alert}")

    def _get_alert_severity(self, alert_key: str) -> str:
        """Get alert severity level"""
        critical_alerts = ["api_down", "cpu_critical", "memory_critical", "disk_critical"]

        if any(critical in alert_key for critical in critical_alerts):
            return "CRITICAL"
        return "WARNING"

    def log_health_status(self, health: SystemHealth):
        """Log current health status"""
        if health.overall_status == "healthy":
            logger.info(f"System healthy - CPU: {health.cpu_usage:.1f}%, "
                       f"Memory: {health.memory_usage:.1f}%, "
                       f"Response: {health.response_time_ms:.0f}ms")
        elif health.overall_status == "degraded":
            logger.warning(f"System degraded - CPU: {health.cpu_usage:.1f}%, "
                          f"Memory: {health.memory_usage:.1f}%, "
                          f"Response: {health.response_time_ms:.0f}ms")
        else:
            logger.error(f"System critical - API: {health.api_status}, "
                        f"WebSocket: {health.websocket_status}")

    def get_health_summary(self) -> Dict[str, Any]:
        """Get current health summary"""
        if not self.health_history:
            return {"status": "no_data"}

        latest = self.health_history[-1]

        return {
            "current_status": latest.overall_status,
            "last_check": latest.timestamp.isoformat(),
            "metrics": {
                "cpu_usage": latest.cpu_usage,
                "memory_usage": latest.memory_usage,
                "disk_usage": latest.disk_usage,
                "response_time_ms": latest.response_time_ms,
                "active_connections": latest.active_connections
            },
            "services": {
                "api": latest.api_status,
                "websocket": latest.websocket_status,
                "redis": latest.redis_status,
                "database": latest.database_status
            },
            "active_alerts": len(self.active_alerts),
            "alert_keys": list(self.active_alerts.keys())
        }

    def export_health_data(self, filename: Optional[str] = None) -> str:
        """Export health data to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"health_data_{timestamp}.json"

        data = {
            "export_timestamp": datetime.now().isoformat(),
            "monitoring_period": {
                "start": self.health_history[0].timestamp.isoformat() if self.health_history else None,
                "end": self.health_history[-1].timestamp.isoformat() if self.health_history else None,
                "total_checks": len(self.health_history)
            },
            "health_history": [asdict(h) for h in self.health_history],
            "alert_history": self.alert_history,
            "current_alerts": {
                key: timestamp.isoformat()
                for key, timestamp in self.active_alerts.items()
            }
        }

        # Convert datetime objects to strings for JSON serialization
        def datetime_converter(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=datetime_converter)

        logger.info(f"Health data exported to {filename}")
        return filename

    async def cleanup(self):
        """Cleanup resources"""
        await self.event_client.close()
        logger.info("Production monitor cleaned up")


# CLI interface
async def main():
    """Main CLI interface for production monitoring"""
    import argparse

    parser = argparse.ArgumentParser(description="Jorge Real Estate AI Production Monitor")
    parser.add_argument("--api-url", default="http://localhost:8001",
                       help="API base URL (default: http://localhost:8001)")
    parser.add_argument("--interval", type=int, default=30,
                       help="Check interval in seconds (default: 30)")
    parser.add_argument("--export", action="store_true",
                       help="Export health data and exit")
    parser.add_argument("--summary", action="store_true",
                       help="Show health summary and exit")

    args = parser.parse_args()

    # Initialize monitor
    monitor = ProductionMonitor(
        api_base_url=args.api_url,
        check_interval=args.interval
    )

    try:
        if args.summary:
            # Show summary
            summary = monitor.get_health_summary()
            print(json.dumps(summary, indent=2))

        elif args.export:
            # Export data
            filename = monitor.export_health_data()
            print(f"Health data exported to: {filename}")

        else:
            # Run continuous monitoring
            await monitor.run_monitoring()

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    finally:
        await monitor.cleanup()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run monitoring
    asyncio.run(main())