"""
GHL Integration Status Component - Real-Time Monitoring and Automation

Monitors Jorge's GoHighLevel integration health:
- API connection status and rate limits
- Webhook delivery monitoring
- Automation pipeline status
- Error tracking and alerts
- One-click automation triggers
- Performance metrics

Author: Claude Code Assistant
Created: 2026-01-23
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class ConnectionStatus(Enum):
    """GHL connection status types"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"


class AutomationStatus(Enum):
    """Automation pipeline status types"""
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class GHLConnectionMetrics:
    """GHL connection health metrics"""
    status: ConnectionStatus
    last_ping: datetime
    response_time_ms: float
    success_rate: float
    rate_limit_remaining: int
    rate_limit_reset: datetime
    errors_last_hour: int


@dataclass
class WebhookMetrics:
    """Webhook delivery metrics"""
    total_received: int
    successful_processed: int
    failed_processed: int
    avg_processing_time: float
    last_received: datetime
    backlog_count: int


@dataclass
class AutomationMetrics:
    """Automation pipeline metrics"""
    name: str
    status: AutomationStatus
    leads_processed: int
    success_rate: float
    avg_execution_time: float
    last_run: datetime
    next_run: Optional[datetime] = None
    errors_today: int = 0


@dataclass
class GHLIntegrationData:
    """Complete GHL integration status data"""
    connection: GHLConnectionMetrics
    webhooks: WebhookMetrics
    automations: List[AutomationMetrics] = field(default_factory=list)
    daily_stats: Dict[str, Any] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)


class GHLIntegrationStatusComponent:
    """GHL Integration Status monitoring and automation component"""

    def __init__(self):
        self.last_update = None
        self._cache_duration = timedelta(minutes=1)

    async def get_integration_status(self, location_id: str) -> GHLIntegrationData:
        """
        Get comprehensive GHL integration status

        Args:
            location_id: GHL location ID

        Returns:
            GHLIntegrationData with current status
        """
        try:
            # In production, this would fetch real data from GHL API
            return await self._fetch_integration_data(location_id)
        except Exception as e:
            # Return degraded status on error
            return self._get_error_status(str(e))

    async def _fetch_integration_data(self, location_id: str) -> GHLIntegrationData:
        """Fetch real integration data (production implementation)"""

        # Simulate API call delay
        await asyncio.sleep(0.1)

        # Mock data for demo - replace with real GHL API calls
        connection = GHLConnectionMetrics(
            status=ConnectionStatus.CONNECTED,
            last_ping=datetime.now() - timedelta(seconds=30),
            response_time_ms=245.6,
            success_rate=99.2,
            rate_limit_remaining=4850,
            rate_limit_reset=datetime.now() + timedelta(minutes=58),
            errors_last_hour=2
        )

        webhooks = WebhookMetrics(
            total_received=1247,
            successful_processed=1235,
            failed_processed=12,
            avg_processing_time=1.8,
            last_received=datetime.now() - timedelta(minutes=2),
            backlog_count=3
        )

        automations = [
            AutomationMetrics(
                name="Lead Qualification Bot",
                status=AutomationStatus.ACTIVE,
                leads_processed=89,
                success_rate=94.4,
                avg_execution_time=12.3,
                last_run=datetime.now() - timedelta(minutes=5),
                next_run=datetime.now() + timedelta(minutes=10),
                errors_today=2
            ),
            AutomationMetrics(
                name="CMA Generation Pipeline",
                status=AutomationStatus.ACTIVE,
                leads_processed=23,
                success_rate=100.0,
                avg_execution_time=45.2,
                last_run=datetime.now() - timedelta(hours=1),
                next_run=datetime.now() + timedelta(hours=2),
                errors_today=0
            ),
            AutomationMetrics(
                name="Follow-up Sequence",
                status=AutomationStatus.ACTIVE,
                leads_processed=156,
                success_rate=98.7,
                avg_execution_time=2.1,
                last_run=datetime.now() - timedelta(minutes=1),
                next_run=datetime.now() + timedelta(minutes=5),
                errors_today=1
            ),
            AutomationMetrics(
                name="Appointment Booking",
                status=AutomationStatus.PAUSED,
                leads_processed=34,
                success_rate=91.2,
                avg_execution_time=8.7,
                last_run=datetime.now() - timedelta(hours=3),
                next_run=None,
                errors_today=3
            )
        ]

        daily_stats = {
            "leads_processed": 302,
            "automations_triggered": 89,
            "cmas_generated": 12,
            "appointments_booked": 8,
            "commission_potential": 89500,
            "response_time_avg": 245.6,
            "uptime_percentage": 99.8
        }

        alerts = []

        # Generate alerts based on conditions
        if connection.errors_last_hour > 5:
            alerts.append(f"⚠️ High error rate: {connection.errors_last_hour} errors in last hour")

        if webhooks.backlog_count > 10:
            alerts.append(f"⚠️ Webhook backlog: {webhooks.backlog_count} pending")

        for automation in automations:
            if automation.status == AutomationStatus.ERROR:
                alerts.append(f"❌ {automation.name} failed")
            elif automation.status == AutomationStatus.PAUSED:
                alerts.append(f"⏸️ {automation.name} is paused")
            elif automation.errors_today > 5:
                alerts.append(f"⚠️ {automation.name}: {automation.errors_today} errors today")

        if connection.rate_limit_remaining < 1000:
            alerts.append(f"⚠️ Rate limit low: {connection.rate_limit_remaining} remaining")

        return GHLIntegrationData(
            connection=connection,
            webhooks=webhooks,
            automations=automations,
            daily_stats=daily_stats,
            alerts=alerts
        )

    def _get_error_status(self, error_msg: str) -> GHLIntegrationData:
        """Return error status when API calls fail"""
        connection = GHLConnectionMetrics(
            status=ConnectionStatus.DISCONNECTED,
            last_ping=datetime.now() - timedelta(minutes=10),
            response_time_ms=0.0,
            success_rate=0.0,
            rate_limit_remaining=0,
            rate_limit_reset=datetime.now(),
            errors_last_hour=999
        )

        webhooks = WebhookMetrics(
            total_received=0,
            successful_processed=0,
            failed_processed=0,
            avg_processing_time=0.0,
            last_received=datetime.now() - timedelta(hours=1),
            backlog_count=0
        )

        return GHLIntegrationData(
            connection=connection,
            webhooks=webhooks,
            automations=[],
            daily_stats={},
            alerts=[f"🚨 Connection Error: {error_msg}"]
        )

    def create_status_overview_chart(self, data: GHLIntegrationData) -> go.Figure:
        """Create status overview chart with key metrics"""

        # Create subplots for different metrics
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Connection Health", "Automation Status",
                          "Daily Performance", "Rate Limits"),
            specs=[[{"type": "indicator"}, {"type": "pie"}],
                   [{"type": "bar"}, {"type": "indicator"}]]
        )

        # Connection Health Gauge
        fig.add_trace(
            go.Indicator(
                mode="gauge+number+delta",
                value=data.connection.success_rate,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Success Rate %"},
                delta={'reference': 95},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 85], 'color': "lightgray"},
                        {'range': [85, 95], 'color': "yellow"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75, 'value': 90
                    }
                }
            ),
            row=1, col=1
        )

        # Automation Status Pie
        automation_statuses = {}
        for automation in data.automations:
            status = automation.status.value
            automation_statuses[status] = automation_statuses.get(status, 0) + 1

        if automation_statuses:
            colors = {
                'active': '#10B981',
                'paused': '#F59E0B',
                'error': '#EF4444',
                'disabled': '#6B7280'
            }

            fig.add_trace(
                go.Pie(
                    labels=list(automation_statuses.keys()),
                    values=list(automation_statuses.values()),
                    marker=dict(colors=[colors.get(k, '#6B7280') for k in automation_statuses.keys()])
                ),
                row=1, col=2
            )

        # Daily Performance Bar
        if data.daily_stats:
            metrics = ['leads_processed', 'automations_triggered', 'cmas_generated', 'appointments_booked']
            values = [data.daily_stats.get(m, 0) for m in metrics]
            labels = ['Leads', 'Automations', 'CMAs', 'Appointments']

            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=values,
                    marker_color=['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B']
                ),
                row=2, col=1
            )

        # Rate Limit Indicator
        fig.add_trace(
            go.Indicator(
                mode="number+gauge",
                value=data.connection.rate_limit_remaining,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "API Calls Remaining"},
                gauge={
                    'axis': {'range': [None, 5000]},
                    'bar': {'color': "darkgreen"},
                    'steps': [
                        {'range': [0, 1000], 'color': "lightcoral"},
                        {'range': [1000, 2500], 'color': "yellow"}
                    ]
                }
            ),
            row=2, col=2
        )

        # Update layout
        fig.update_layout(
            title="🔗 GHL Integration Health Overview",
            height=600,
            showlegend=False,
            margin=dict(l=50, r=50, t=80, b=50)
        )

        return fig

    def create_automation_performance_chart(self, data: GHLIntegrationData) -> go.Figure:
        """Create automation performance timeline chart"""

        if not data.automations:
            # Return empty chart if no data
            fig = go.Figure()
            fig.add_annotation(
                text="No automation data available",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=16)
            )
            return fig

        # Create timeline chart showing automation performance
        fig = go.Figure()

        for i, automation in enumerate(data.automations):
            # Performance bar
            color = {
                AutomationStatus.ACTIVE: '#10B981',
                AutomationStatus.PAUSED: '#F59E0B',
                AutomationStatus.ERROR: '#EF4444',
                AutomationStatus.DISABLED: '#6B7280'
            }.get(automation.status, '#6B7280')

            fig.add_trace(
                go.Bar(
                    name=automation.name,
                    x=[automation.success_rate],
                    y=[automation.name],
                    orientation='h',
                    marker_color=color,
                    text=[f"{automation.success_rate:.1f}% ({automation.leads_processed} leads)"],
                    textposition='inside',
                    hovertemplate=(
                        f"<b>{automation.name}</b><br>"
                        f"Success Rate: {automation.success_rate:.1f}%<br>"
                        f"Leads Processed: {automation.leads_processed}<br>"
                        f"Avg Time: {automation.avg_execution_time:.1f}s<br>"
                        f"Errors Today: {automation.errors_today}<br>"
                        f"Status: {automation.status.value.title()}"
                        "<extra></extra>"
                    )
                )
            )

        fig.update_layout(
            title="🤖 Automation Pipeline Performance",
            xaxis_title="Success Rate (%)",
            yaxis_title="",
            height=300 + len(data.automations) * 40,
            showlegend=False,
            margin=dict(l=150, r=50, t=60, b=50)
        )

        return fig

    def create_webhook_health_chart(self, data: GHLIntegrationData) -> go.Figure:
        """Create webhook delivery health chart"""

        # Create webhook performance metrics
        webhook_data = {
            'Metric': ['Successful', 'Failed', 'Processing Time', 'Backlog'],
            'Value': [
                data.webhooks.successful_processed,
                data.webhooks.failed_processed,
                data.webhooks.avg_processing_time,
                data.webhooks.backlog_count
            ],
            'Color': ['#10B981', '#EF4444', '#3B82F6', '#F59E0B']
        }

        fig = go.Figure()

        # Success/Fail pie chart
        fig.add_trace(
            go.Pie(
                labels=['Successful', 'Failed'],
                values=[data.webhooks.successful_processed, data.webhooks.failed_processed],
                hole=.3,
                marker=dict(colors=['#10B981', '#EF4444']),
                textinfo='label+percent+value',
                hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>"
            )
        )

        fig.update_layout(
            title=f"📡 Webhook Health - {data.webhooks.total_received} Total Received",
            height=400,
            annotations=[dict(text=f"Total<br>{data.webhooks.total_received}", x=0.5, y=0.5,
                            font_size=16, showarrow=False)]
        )

        return fig


async def create_ghl_integration_status() -> GHLIntegrationStatusComponent:
    """Factory function to create GHL integration status component"""
    return GHLIntegrationStatusComponent()