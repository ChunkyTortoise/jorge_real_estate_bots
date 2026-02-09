"""
Tests for Enhanced Hero Metrics Component - Jorge's ROI Command Center

Tests the enhanced hero metrics with:
- Lead Source ROI analysis
- 30-day revenue forecast
- Smart CMA prioritization
- One-click automation triggers

Author: Claude Code Assistant
Created: 2026-01-23
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from command_center.components.enhanced_hero_metrics import (
    CMAAnalyzer,
    EnhancedHeroMetrics,
    HeroMetricData,
    LeadSourceROI,
    RevenueForecaster,
)


class TestHeroMetricData:
    """Test data structure for hero metrics"""

    def test_hero_metric_data_creation(self):
        """Test creating HeroMetricData with all required fields"""
        metric = HeroMetricData(
            label="🔥 Hot Leads Pipeline",
            value="8 leads",
            delta="+3 from yesterday",
            color="red",
            urgency_level="high",
            action_button="View All Hot Leads",
            tooltip="Leads scoring ≥80 requiring immediate action"
        )

        assert metric.label == "🔥 Hot Leads Pipeline"
        assert metric.value == "8 leads"
        assert metric.urgency_level == "high"
        assert metric.action_button is not None


class TestLeadSourceROI:
    """Test lead source ROI analysis"""

    @pytest.fixture
    def mock_lead_data(self):
        """Mock lead data with different sources"""
        return [
            {
                "id": "1", "source": "zillow", "score": 85, "commission": 15000,
                "cost_per_lead": 150, "status": "hot"
            },
            {
                "id": "2", "source": "realtor.com", "score": 78, "commission": 12000,
                "cost_per_lead": 200, "status": "warm"
            },
            {
                "id": "3", "source": "referral", "score": 92, "commission": 18000,
                "cost_per_lead": 0, "status": "hot"
            },
            {
                "id": "4", "source": "zillow", "score": 88, "commission": 16000,
                "cost_per_lead": 150, "status": "hot"
            }
        ]

    def test_calculate_source_roi(self, mock_lead_data):
        """Test ROI calculation by lead source"""
        analyzer = LeadSourceROI()
        source_roi = analyzer.calculate_source_roi(mock_lead_data)

        # Referrals should have highest ROI (infinite since cost=0)
        assert source_roi["referral"]["roi"] == float('inf')

        # Zillow: (15000 + 16000) / (150 + 150) = 103.33
        assert abs(source_roi["zillow"]["roi"] - 103.33) < 0.1

        # Realtor.com: 12000 / 200 = 60
        assert source_roi["realtor.com"]["roi"] == 60

    def test_get_best_performing_source(self, mock_lead_data):
        """Test identifying best performing source"""
        analyzer = LeadSourceROI()
        best_source = analyzer.get_best_performing_source(mock_lead_data)

        # Referrals should be best (highest ROI)
        assert best_source["source"] == "referral"
        assert best_source["hot_leads_count"] == 1
        assert best_source["roi"] == float('inf')

    def test_format_roi_display(self):
        """Test ROI display formatting"""
        analyzer = LeadSourceROI()

        # Infinite ROI
        assert analyzer.format_roi_display(float('inf')) == "∞x ROI"

        # High ROI
        assert analyzer.format_roi_display(103.33) == "103x ROI"

        # Low ROI
        assert analyzer.format_roi_display(1.5) == "1.5x ROI"

        # No ROI
        assert analyzer.format_roi_display(0) == "0x ROI"


class TestRevenueForecaster:
    """Test 30-day revenue forecasting"""

    @pytest.fixture
    def mock_historical_data(self):
        """Mock historical commission data"""
        base_date = datetime.now() - timedelta(days=60)
        return [
            {"date": base_date + timedelta(days=i), "commission": 2000 + (i * 100)}
            for i in range(60)
        ]

    @pytest.fixture
    def mock_pipeline_data(self):
        """Mock current pipeline data"""
        return [
            {"id": "1", "score": 85, "commission": 15000, "probability": 0.8, "close_date": "2026-02-15"},
            {"id": "2", "score": 78, "commission": 12000, "probability": 0.6, "close_date": "2026-02-20"},
            {"id": "3", "score": 92, "commission": 18000, "probability": 0.9, "close_date": "2026-02-10"}
        ]

    def test_calculate_30_day_forecast(self, mock_historical_data, mock_pipeline_data):
        """Test 30-day revenue forecasting"""
        forecaster = RevenueForecaster()
        forecast = forecaster.calculate_30_day_forecast(
            historical_data=mock_historical_data,
            current_pipeline=mock_pipeline_data
        )

        assert "projected_revenue" in forecast
        assert "confidence_range" in forecast
        assert "trend_direction" in forecast
        assert forecast["projected_revenue"] > 0
        assert len(forecast["confidence_range"]) == 2

    def test_calculate_velocity_trend(self, mock_historical_data):
        """Test revenue velocity calculation"""
        forecaster = RevenueForecaster()
        velocity = forecaster.calculate_velocity_trend(mock_historical_data)

        assert velocity > 0  # Should show positive trend based on mock data
        assert isinstance(velocity, float)

    def test_format_forecast_display(self):
        """Test forecast display formatting"""
        forecaster = RevenueForecaster()

        forecast_data = {
            "projected_revenue": 89000,
            "confidence_range": [75000, 103000],
            "trend_direction": "up"
        }

        display = forecaster.format_forecast_display(forecast_data)
        assert "At current pace: $89K" in display
        assert "Range: $75K - $103K" in display
        assert "↗️" in display  # Up trend arrow


class TestCMAAnalyzer:
    """Test CMA prioritization and revenue prediction"""

    @pytest.fixture
    def mock_q4_sellers(self):
        """Mock Q4 qualified sellers needing CMAs"""
        return [
            {
                "id": "s1", "name": "John Smith", "questions_answered": 4,
                "price_expectation": 450000, "condition": "move_in_ready",
                "motivation": "job_relocation", "urgency": "high"
            },
            {
                "id": "s2", "name": "Sarah Johnson", "questions_answered": 4,
                "price_expectation": 650000, "condition": "needs_minor_repairs",
                "motivation": "divorce", "urgency": "medium"
            },
            {
                "id": "s3", "name": "Mike Davis", "questions_answered": 4,
                "price_expectation": 320000, "condition": "needs_major_repairs",
                "motivation": "foreclosure", "urgency": "high"
            }
        ]

    def test_calculate_commission_potential(self, mock_q4_sellers):
        """Test commission calculation for Q4 sellers"""
        analyzer = CMAAnalyzer()

        # Test individual seller
        commission = analyzer.calculate_commission_potential(mock_q4_sellers[0])
        # John Smith: 450K * 0.75 (offer ratio) * 0.06 (commission) = $20,250
        expected = 450000 * 0.75 * 0.06
        assert abs(commission - expected) < 100

    def test_prioritize_by_value(self, mock_q4_sellers):
        """Test CMA prioritization by commission potential"""
        analyzer = CMAAnalyzer()
        prioritized = analyzer.prioritize_by_value(mock_q4_sellers)

        # Sarah Johnson ($650K) should be first
        assert prioritized[0]["name"] == "Sarah Johnson"

        # John Smith ($450K) should be second
        assert prioritized[1]["name"] == "John Smith"

        # Mike Davis ($320K) should be last
        assert prioritized[2]["name"] == "Mike Davis"

    def test_get_cma_summary(self, mock_q4_sellers):
        """Test CMA summary generation"""
        analyzer = CMAAnalyzer()
        summary = analyzer.get_cma_summary(mock_q4_sellers)

        assert summary["total_sellers"] == 3
        assert summary["total_commission_potential"] > 0
        assert summary["high_priority_count"] == 2  # John and Mike have high urgency
        assert "prioritized_list" in summary

    def test_format_cma_display(self, mock_q4_sellers):
        """Test CMA display formatting"""
        analyzer = CMAAnalyzer()
        display = analyzer.format_cma_display(mock_q4_sellers)

        assert "CMAs Ready: 3" in display
        assert "Est. $" in display  # Shows estimated commission
        assert "→" in display  # Shows estimated commission arrow


class TestEnhancedHeroMetrics:
    """Test main enhanced hero metrics component"""

    @pytest.fixture
    def enhanced_metrics(self):
        """Create EnhancedHeroMetrics instance with mocked dependencies"""
        with patch('command_center.components.enhanced_hero_metrics.get_enhanced_lead_intelligence'), \
             patch('command_center.components.enhanced_hero_metrics.create_seller_bot'), \
             patch('command_center.components.enhanced_hero_metrics.GHLClient'):
            return EnhancedHeroMetrics()

    @pytest.mark.asyncio
    async def test_get_hero_metrics_data(self, enhanced_metrics):
        """Test retrieving all hero metrics data"""
        # Mock the data sources
        with patch.object(enhanced_metrics, '_get_hot_leads_data') as mock_hot_leads, \
             patch.object(enhanced_metrics, '_get_seller_pipeline_data') as mock_sellers, \
             patch.object(enhanced_metrics, '_get_ghl_health_data') as mock_ghl, \
             patch.object(enhanced_metrics, '_get_performance_data') as mock_perf:

            mock_hot_leads.return_value = {"count": 8, "best_source": "zillow"}
            mock_sellers.return_value = {"q4_ready": 5, "commission_potential": 47000}
            mock_ghl.return_value = {"healthy": True, "response_time": 142}
            mock_perf.return_value = {"five_min_compliance": 0.95}

            metrics = await enhanced_metrics.get_hero_metrics_data("test_location")

            assert len(metrics) >= 4  # At least 4 hero cards
            assert any("Hot Leads" in m.label for m in metrics)
            assert any("CMA" in m.label for m in metrics)

    def test_format_metric_card(self, enhanced_metrics):
        """Test metric card formatting"""
        metric = HeroMetricData(
            label="Test Metric",
            value="42",
            delta="+5",
            color="blue",
            urgency_level="medium",
            action_button="Test Action",
            tooltip="Test tooltip"
        )

        formatted = enhanced_metrics.format_metric_card(metric)
        assert "Test Metric" in formatted
        assert "42" in formatted
        assert "+5" in formatted

    @pytest.mark.asyncio
    async def test_error_handling(self, enhanced_metrics):
        """Test graceful error handling when data sources fail"""
        with patch.object(enhanced_metrics, '_get_hot_leads_data', side_effect=Exception("API Error")):
            metrics = await enhanced_metrics.get_hero_metrics_data("test_location")

            # Should still return metrics with fallback values
            assert len(metrics) > 0
            fallback_metric = next((m for m in metrics if "Error" in m.value), None)
            assert fallback_metric is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])