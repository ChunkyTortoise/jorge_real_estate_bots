"""
Tests for GHL Integration Status Component

Tests the core functionality of the GHL integration monitoring system:
- Connection status tracking
- Automation pipeline monitoring
- Webhook health metrics
- Performance analytics
- Alert generation

Author: Claude Code Assistant
Created: 2026-01-23
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from command_center.components.ghl_integration_status import (
    GHLIntegrationStatusComponent,
    GHLIntegrationData,
    GHLConnectionMetrics,
    WebhookMetrics,
    AutomationMetrics,
    ConnectionStatus,
    AutomationStatus,
    create_ghl_integration_status
)


@pytest.fixture
def sample_connection_metrics():
    """Sample connection metrics for testing"""
    return GHLConnectionMetrics(
        status=ConnectionStatus.CONNECTED,
        last_ping=datetime.now() - timedelta(seconds=30),
        response_time_ms=245.6,
        success_rate=99.2,
        rate_limit_remaining=4850,
        rate_limit_reset=datetime.now() + timedelta(minutes=58),
        errors_last_hour=2
    )


@pytest.fixture
def sample_webhook_metrics():
    """Sample webhook metrics for testing"""
    return WebhookMetrics(
        total_received=1247,
        successful_processed=1235,
        failed_processed=12,
        avg_processing_time=1.8,
        last_received=datetime.now() - timedelta(minutes=2),
        backlog_count=3
    )


@pytest.fixture
def sample_automation_metrics():
    """Sample automation metrics for testing"""
    return [
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
            status=AutomationStatus.PAUSED,
            leads_processed=156,
            success_rate=98.7,
            avg_execution_time=2.1,
            last_run=datetime.now() - timedelta(minutes=1),
            next_run=None,
            errors_today=1
        )
    ]


@pytest.fixture
def sample_integration_data(sample_connection_metrics, sample_webhook_metrics, sample_automation_metrics):
    """Sample complete integration data for testing"""
    return GHLIntegrationData(
        connection=sample_connection_metrics,
        webhooks=sample_webhook_metrics,
        automations=sample_automation_metrics,
        daily_stats={
            "leads_processed": 302,
            "automations_triggered": 89,
            "cmas_generated": 12,
            "appointments_booked": 8,
            "commission_potential": 89500,
            "response_time_avg": 245.6,
            "uptime_percentage": 99.8
        },
        alerts=[]
    )


class TestGHLIntegrationStatusComponent:
    """Test cases for GHL Integration Status Component"""

    @pytest.fixture
    def integration_component(self):
        """Create GHL integration status component for testing"""
        return GHLIntegrationStatusComponent()

    @pytest.mark.asyncio
    async def test_create_ghl_integration_status(self):
        """Test factory function creates component correctly"""
        component = await create_ghl_integration_status()
        assert isinstance(component, GHLIntegrationStatusComponent)
        assert component.last_update is None
        assert component._cache_duration == timedelta(minutes=1)

    @pytest.mark.asyncio
    async def test_get_integration_status_success(self, integration_component):
        """Test successful integration status retrieval"""
        location_id = "test_location_123"

        # Mock the _fetch_integration_data method
        with patch.object(integration_component, '_fetch_integration_data') as mock_fetch:
            mock_data = GHLIntegrationData(
                connection=GHLConnectionMetrics(
                    status=ConnectionStatus.CONNECTED,
                    last_ping=datetime.now(),
                    response_time_ms=200.0,
                    success_rate=95.0,
                    rate_limit_remaining=5000,
                    rate_limit_reset=datetime.now() + timedelta(hours=1),
                    errors_last_hour=0
                ),
                webhooks=WebhookMetrics(
                    total_received=100,
                    successful_processed=95,
                    failed_processed=5,
                    avg_processing_time=1.5,
                    last_received=datetime.now(),
                    backlog_count=0
                ),
                automations=[],
                daily_stats={},
                alerts=[]
            )
            mock_fetch.return_value = mock_data

            result = await integration_component.get_integration_status(location_id)

            assert isinstance(result, GHLIntegrationData)
            assert result.connection.status == ConnectionStatus.CONNECTED
            assert result.connection.success_rate == 95.0
            assert result.webhooks.total_received == 100
            mock_fetch.assert_called_once_with(location_id)

    @pytest.mark.asyncio
    async def test_get_integration_status_error_handling(self, integration_component):
        """Test error handling in integration status retrieval"""
        location_id = "test_location_123"

        # Mock an exception in _fetch_integration_data
        with patch.object(integration_component, '_fetch_integration_data') as mock_fetch:
            mock_fetch.side_effect = Exception("API connection failed")

            result = await integration_component.get_integration_status(location_id)

            assert isinstance(result, GHLIntegrationData)
            assert result.connection.status == ConnectionStatus.DISCONNECTED
            assert result.connection.success_rate == 0.0
            assert "Connection Error" in result.alerts[0]

    @pytest.mark.asyncio
    async def test_fetch_integration_data_structure(self, integration_component):
        """Test the structure of fetched integration data"""
        location_id = "test_location_123"

        result = await integration_component._fetch_integration_data(location_id)

        assert isinstance(result, GHLIntegrationData)
        assert isinstance(result.connection, GHLConnectionMetrics)
        assert isinstance(result.webhooks, WebhookMetrics)
        assert isinstance(result.automations, list)
        assert isinstance(result.daily_stats, dict)
        assert isinstance(result.alerts, list)

    def test_connection_metrics_data_class(self, sample_connection_metrics):
        """Test connection metrics data class"""
        metrics = sample_connection_metrics

        assert metrics.status == ConnectionStatus.CONNECTED
        assert metrics.response_time_ms == 245.6
        assert metrics.success_rate == 99.2
        assert metrics.rate_limit_remaining == 4850
        assert metrics.errors_last_hour == 2

    def test_webhook_metrics_data_class(self, sample_webhook_metrics):
        """Test webhook metrics data class"""
        metrics = sample_webhook_metrics

        assert metrics.total_received == 1247
        assert metrics.successful_processed == 1235
        assert metrics.failed_processed == 12
        assert metrics.avg_processing_time == 1.8
        assert metrics.backlog_count == 3

    def test_automation_metrics_data_class(self, sample_automation_metrics):
        """Test automation metrics data class"""
        automation = sample_automation_metrics[0]

        assert automation.name == "Lead Qualification Bot"
        assert automation.status == AutomationStatus.ACTIVE
        assert automation.leads_processed == 89
        assert automation.success_rate == 94.4
        assert automation.avg_execution_time == 12.3
        assert automation.errors_today == 2

    @pytest.mark.asyncio
    async def test_alert_generation_high_errors(self, integration_component):
        """Test alert generation for high error rates"""
        # Mock data with high error count
        with patch.object(integration_component, '_fetch_integration_data') as mock_fetch:
            mock_data = GHLIntegrationData(
                connection=GHLConnectionMetrics(
                    status=ConnectionStatus.CONNECTED,
                    last_ping=datetime.now(),
                    response_time_ms=200.0,
                    success_rate=95.0,
                    rate_limit_remaining=5000,
                    rate_limit_reset=datetime.now() + timedelta(hours=1),
                    errors_last_hour=10  # High error count
                ),
                webhooks=WebhookMetrics(
                    total_received=100,
                    successful_processed=90,
                    failed_processed=10,
                    avg_processing_time=1.5,
                    last_received=datetime.now(),
                    backlog_count=0
                ),
                automations=[],
                daily_stats={},
                alerts=["⚠️ High error rate: 10 errors in last hour"]
            )
            mock_fetch.return_value = mock_data

            result = await integration_component.get_integration_status("test_location")

            assert len(result.alerts) > 0
            assert "High error rate" in result.alerts[0]

    @pytest.mark.asyncio
    async def test_alert_generation_webhook_backlog(self, integration_component):
        """Test alert generation for webhook backlog"""
        # Mock data with high backlog
        with patch.object(integration_component, '_fetch_integration_data') as mock_fetch:
            mock_data = GHLIntegrationData(
                connection=GHLConnectionMetrics(
                    status=ConnectionStatus.CONNECTED,
                    last_ping=datetime.now(),
                    response_time_ms=200.0,
                    success_rate=95.0,
                    rate_limit_remaining=5000,
                    rate_limit_reset=datetime.now() + timedelta(hours=1),
                    errors_last_hour=2
                ),
                webhooks=WebhookMetrics(
                    total_received=100,
                    successful_processed=85,
                    failed_processed=15,
                    avg_processing_time=1.5,
                    last_received=datetime.now(),
                    backlog_count=15  # High backlog
                ),
                automations=[],
                daily_stats={},
                alerts=["⚠️ Webhook backlog: 15 pending"]
            )
            mock_fetch.return_value = mock_data

            result = await integration_component.get_integration_status("test_location")

            assert any("Webhook backlog" in alert for alert in result.alerts)

    @pytest.mark.asyncio
    async def test_alert_generation_rate_limit(self, integration_component):
        """Test alert generation for low rate limit"""
        # Mock data with low rate limit
        with patch.object(integration_component, '_fetch_integration_data') as mock_fetch:
            mock_data = GHLIntegrationData(
                connection=GHLConnectionMetrics(
                    status=ConnectionStatus.RATE_LIMITED,
                    last_ping=datetime.now(),
                    response_time_ms=200.0,
                    success_rate=95.0,
                    rate_limit_remaining=500,  # Low rate limit
                    rate_limit_reset=datetime.now() + timedelta(hours=1),
                    errors_last_hour=2
                ),
                webhooks=WebhookMetrics(
                    total_received=100,
                    successful_processed=95,
                    failed_processed=5,
                    avg_processing_time=1.5,
                    last_received=datetime.now(),
                    backlog_count=0
                ),
                automations=[],
                daily_stats={},
                alerts=["⚠️ Rate limit low: 500 remaining"]
            )
            mock_fetch.return_value = mock_data

            result = await integration_component.get_integration_status("test_location")

            assert any("Rate limit low" in alert for alert in result.alerts)

    def test_create_status_overview_chart(self, integration_component, sample_integration_data):
        """Test status overview chart creation"""
        chart = integration_component.create_status_overview_chart(sample_integration_data)

        assert chart is not None
        assert hasattr(chart, 'data')
        assert len(chart.data) > 0
        assert "GHL Integration Health Overview" in chart.layout.title.text

    def test_create_automation_performance_chart(self, integration_component, sample_integration_data):
        """Test automation performance chart creation"""
        chart = integration_component.create_automation_performance_chart(sample_integration_data)

        assert chart is not None
        assert hasattr(chart, 'data')
        assert "Automation Pipeline Performance" in chart.layout.title.text

    def test_create_automation_performance_chart_no_data(self, integration_component):
        """Test automation performance chart with no data"""
        empty_data = GHLIntegrationData(
            connection=GHLConnectionMetrics(
                status=ConnectionStatus.CONNECTED,
                last_ping=datetime.now(),
                response_time_ms=200.0,
                success_rate=95.0,
                rate_limit_remaining=5000,
                rate_limit_reset=datetime.now() + timedelta(hours=1),
                errors_last_hour=0
            ),
            webhooks=WebhookMetrics(
                total_received=0,
                successful_processed=0,
                failed_processed=0,
                avg_processing_time=0.0,
                last_received=datetime.now(),
                backlog_count=0
            ),
            automations=[],  # No automations
            daily_stats={},
            alerts=[]
        )

        chart = integration_component.create_automation_performance_chart(empty_data)

        assert chart is not None
        assert hasattr(chart, 'data')

    def test_create_webhook_health_chart(self, integration_component, sample_integration_data):
        """Test webhook health chart creation"""
        chart = integration_component.create_webhook_health_chart(sample_integration_data)

        assert chart is not None
        assert hasattr(chart, 'data')
        assert len(chart.data) > 0
        assert "Webhook Health" in chart.layout.title.text

    def test_get_error_status(self, integration_component):
        """Test error status generation"""
        error_msg = "API connection failed"
        error_status = integration_component._get_error_status(error_msg)

        assert error_status.connection.status == ConnectionStatus.DISCONNECTED
        assert error_status.connection.success_rate == 0.0
        assert error_status.connection.rate_limit_remaining == 0
        assert error_status.webhooks.total_received == 0
        assert len(error_status.automations) == 0
        assert len(error_status.alerts) == 1
        assert error_msg in error_status.alerts[0]

    @pytest.mark.asyncio
    async def test_integration_data_alerts_automation_errors(self, integration_component):
        """Test alert generation for automation errors"""
        with patch.object(integration_component, '_fetch_integration_data') as mock_fetch:
            error_automation = AutomationMetrics(
                name="Failed Bot",
                status=AutomationStatus.ERROR,
                leads_processed=0,
                success_rate=0.0,
                avg_execution_time=0.0,
                last_run=datetime.now() - timedelta(hours=1),
                errors_today=10
            )

            mock_data = GHLIntegrationData(
                connection=GHLConnectionMetrics(
                    status=ConnectionStatus.CONNECTED,
                    last_ping=datetime.now(),
                    response_time_ms=200.0,
                    success_rate=95.0,
                    rate_limit_remaining=5000,
                    rate_limit_reset=datetime.now() + timedelta(hours=1),
                    errors_last_hour=0
                ),
                webhooks=WebhookMetrics(
                    total_received=100,
                    successful_processed=95,
                    failed_processed=5,
                    avg_processing_time=1.5,
                    last_received=datetime.now(),
                    backlog_count=0
                ),
                automations=[error_automation],
                daily_stats={},
                alerts=["❌ Failed Bot failed"]
            )
            mock_fetch.return_value = mock_data

            result = await integration_component.get_integration_status("test_location")

            assert any("Failed Bot failed" in alert for alert in result.alerts)

    def test_connection_status_enum_values(self):
        """Test connection status enum values"""
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.DEGRADED.value == "degraded"
        assert ConnectionStatus.RATE_LIMITED.value == "rate_limited"

    def test_automation_status_enum_values(self):
        """Test automation status enum values"""
        assert AutomationStatus.ACTIVE.value == "active"
        assert AutomationStatus.PAUSED.value == "paused"
        assert AutomationStatus.ERROR.value == "error"
        assert AutomationStatus.DISABLED.value == "disabled"


class TestGHLIntegrationDataClasses:
    """Test data classes for GHL integration"""

    def test_ghl_connection_metrics_defaults(self):
        """Test GHL connection metrics with minimal data"""
        metrics = GHLConnectionMetrics(
            status=ConnectionStatus.CONNECTED,
            last_ping=datetime.now(),
            response_time_ms=100.0,
            success_rate=99.0,
            rate_limit_remaining=5000,
            rate_limit_reset=datetime.now() + timedelta(hours=1),
            errors_last_hour=0
        )

        assert metrics.status == ConnectionStatus.CONNECTED
        assert isinstance(metrics.last_ping, datetime)
        assert metrics.response_time_ms == 100.0

    def test_webhook_metrics_calculations(self):
        """Test webhook metrics calculations"""
        metrics = WebhookMetrics(
            total_received=1000,
            successful_processed=950,
            failed_processed=50,
            avg_processing_time=2.5,
            last_received=datetime.now(),
            backlog_count=10
        )

        success_rate = (metrics.successful_processed / metrics.total_received) * 100
        assert success_rate == 95.0
        assert metrics.failed_processed == 50

    def test_automation_metrics_with_optional_fields(self):
        """Test automation metrics with optional next_run field"""
        # With next_run
        automation_with_next = AutomationMetrics(
            name="Test Bot",
            status=AutomationStatus.ACTIVE,
            leads_processed=100,
            success_rate=95.0,
            avg_execution_time=10.0,
            last_run=datetime.now(),
            next_run=datetime.now() + timedelta(hours=1)
        )
        assert automation_with_next.next_run is not None
        assert automation_with_next.errors_today == 0  # Default value

        # Without next_run (paused automation)
        automation_without_next = AutomationMetrics(
            name="Paused Bot",
            status=AutomationStatus.PAUSED,
            leads_processed=50,
            success_rate=90.0,
            avg_execution_time=5.0,
            last_run=datetime.now(),
            next_run=None
        )
        assert automation_without_next.next_run is None

    def test_ghl_integration_data_default_factory_fields(self):
        """Test GHL integration data with default factory fields"""
        connection = GHLConnectionMetrics(
            status=ConnectionStatus.CONNECTED,
            last_ping=datetime.now(),
            response_time_ms=100.0,
            success_rate=99.0,
            rate_limit_remaining=5000,
            rate_limit_reset=datetime.now() + timedelta(hours=1),
            errors_last_hour=0
        )

        webhooks = WebhookMetrics(
            total_received=100,
            successful_processed=95,
            failed_processed=5,
            avg_processing_time=1.0,
            last_received=datetime.now(),
            backlog_count=0
        )

        # Test with default factory fields
        integration_data = GHLIntegrationData(
            connection=connection,
            webhooks=webhooks
        )

        assert integration_data.automations == []
        assert integration_data.daily_stats == {}
        assert integration_data.alerts == []