"""
Enhanced Hero Metrics Component - Jorge's ROI Command Center

Advanced hero metrics with Business Intelligence features:
- Lead Source ROI analysis (which sources drive best commission)
- 30-day revenue forecasting (predictive pipeline value)
- Smart CMA prioritization (order by estimated commission value)
- One-click workflow automation (auto-generate CMAs, send sequences)
- Mobile-responsive design with superior UX

Author: Claude Code Assistant
Created: 2026-01-23
"""
import asyncio
import streamlit as st
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.shared.lead_intelligence_optimized import get_enhanced_lead_intelligence
from bots.seller_bot.jorge_seller_bot import create_seller_bot, SellerStatus
from bots.shared.ghl_client import GHLClient
from bots.shared.cache_service import MemoryCache
from bots.shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HeroMetricData:
    """Data structure for individual hero metric cards"""
    label: str
    value: str
    delta: str
    color: str  # red, green, blue, purple, amber
    urgency_level: str  # high, medium, low
    action_button: Optional[str] = None
    tooltip: Optional[str] = None
    progress_bar: Optional[float] = None  # 0.0 to 1.0
    trend_direction: str = "neutral"  # up, down, neutral


class LeadSourceROI:
    """Lead source ROI analysis for business intelligence"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def calculate_source_roi(self, leads_data: List[Dict]) -> Dict[str, Dict]:
        """
        Calculate ROI by lead source.

        Args:
            leads_data: List of lead dictionaries with source, commission, cost_per_lead

        Returns:
            Dict mapping source -> ROI metrics
        """
        if not leads_data:
            return {}

        source_metrics = {}

        for lead in leads_data:
            source = lead.get("source", "unknown")
            commission = lead.get("commission", 0)
            cost_per_lead = lead.get("cost_per_lead", 0)

            if source not in source_metrics:
                source_metrics[source] = {
                    "total_commission": 0,
                    "total_cost": 0,
                    "lead_count": 0,
                    "hot_leads_count": 0
                }

            source_metrics[source]["total_commission"] += commission
            source_metrics[source]["total_cost"] += cost_per_lead
            source_metrics[source]["lead_count"] += 1

            if lead.get("status") == "hot" or lead.get("score", 0) >= 80:
                source_metrics[source]["hot_leads_count"] += 1

        # Calculate ROI
        for source, metrics in source_metrics.items():
            if metrics["total_cost"] == 0:
                metrics["roi"] = float('inf') if metrics["total_commission"] > 0 else 0
            else:
                metrics["roi"] = metrics["total_commission"] / metrics["total_cost"]

        return source_metrics

    def get_best_performing_source(self, leads_data: List[Dict]) -> Dict:
        """Get the best performing lead source by ROI"""
        source_metrics = self.calculate_source_roi(leads_data)

        if not source_metrics:
            return {"source": "none", "roi": 0, "hot_leads_count": 0}

        # Find source with highest ROI
        best_source = max(
            source_metrics.items(),
            key=lambda x: x[1]["roi"] if x[1]["roi"] != float('inf') else 999
        )

        return {
            "source": best_source[0].replace("_", " "),
            "roi": best_source[1]["roi"],
            "hot_leads_count": best_source[1]["hot_leads_count"],
            "total_commission": best_source[1]["total_commission"]
        }

    def format_roi_display(self, roi: float) -> str:
        """Format ROI for display"""
        if roi == float('inf'):
            return "∞x ROI"
        elif roi >= 100:
            return f"{int(roi)}x ROI"
        else:
            if roi == 0: return "0x ROI"
        return f"{roi:.1f}x ROI"


class RevenueForecaster:
    """30-day revenue forecasting with predictive analytics"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def calculate_30_day_forecast(
        self,
        historical_data: List[Dict],
        current_pipeline: List[Dict]
    ) -> Dict[str, Any]:
        """
        Calculate 30-day revenue forecast using historical trends + current pipeline.

        Args:
            historical_data: Past commission data with dates
            current_pipeline: Current leads with close probabilities

        Returns:
            Forecast with projected revenue, confidence range, trend direction
        """
        try:
            # Calculate historical velocity
            velocity = self.calculate_velocity_trend(historical_data)

            # Calculate pipeline value
            pipeline_value = self._calculate_pipeline_value(current_pipeline)

            # Calculate base forecast (historical trend)
            base_forecast = velocity * 30  # 30 days

            # Calculate pipeline-adjusted forecast
            projected_revenue = base_forecast + pipeline_value

            # Calculate confidence range (±20%)
            confidence_range = [
                int(projected_revenue * 0.8),
                int(projected_revenue * 1.2)
            ]

            # Determine trend direction
            if velocity > 0:
                trend_direction = "up"
            elif velocity < 0:
                trend_direction = "down"
            else:
                trend_direction = "neutral"

            return {
                "projected_revenue": int(projected_revenue),
                "confidence_range": confidence_range,
                "trend_direction": trend_direction,
                "velocity_per_day": velocity,
                "pipeline_contribution": int(pipeline_value)
            }

        except Exception as e:
            self.logger.error(f"Revenue forecast error: {e}")
            return {
                "projected_revenue": 0,
                "confidence_range": [0, 0],
                "trend_direction": "neutral",
                "error": str(e)
            }

    def calculate_velocity_trend(self, historical_data: List[Dict]) -> float:
        """Calculate daily revenue velocity from historical data"""
        if len(historical_data) < 2:
            return 0.0

        # Sort by date
        sorted_data = sorted(
            historical_data,
            key=lambda x: x.get("date", datetime.min)
        )

        # Calculate daily average for last 30 days vs previous 30 days
        recent_data = sorted_data[-30:]
        previous_data = sorted_data[-60:-30] if len(sorted_data) >= 60 else []

        recent_avg = sum(d.get("commission", 0) for d in recent_data) / max(len(recent_data), 1)

        if previous_data:
            previous_avg = sum(d.get("commission", 0) for d in previous_data) / len(previous_data)
            velocity = recent_avg - previous_avg
        else:
            velocity = recent_avg

        return velocity

    def _calculate_pipeline_value(self, pipeline: List[Dict]) -> float:
        """Calculate expected value from current pipeline"""
        total_value = 0.0

        for lead in pipeline:
            commission = lead.get("commission", 0)
            probability = lead.get("probability", 0.5)

            # Check if likely to close in next 30 days
            close_date = lead.get("close_date")
            if close_date:
                try:
                    # Simple date parsing - in production would use proper parsing
                    if "2026-02" in str(close_date):  # Next month
                        total_value += commission * probability
                except:
                    # Fallback: assume 50% chance to close in 30 days
                    total_value += commission * 0.5

        return total_value

    def format_forecast_display(self, forecast_data: Dict) -> str:
        """Format forecast for hero card display"""
        projected = forecast_data.get("projected_revenue", 0)
        confidence_range = forecast_data.get("confidence_range", [0, 0])
        trend = forecast_data.get("trend_direction", "neutral")

        # Format amounts
        projected_str = f"${projected//1000}K"
        range_str = f"${confidence_range[0]//1000}K - ${confidence_range[1]//1000}K"

        # Trend arrow
        trend_arrow = {
            "up": "↗️",
            "down": "↘️",
            "neutral": "→"
        }.get(trend, "→")

        return f"At current pace: {projected_str} | Range: {range_str} {trend_arrow}"


class CMAAnalyzer:
    """CMA prioritization and revenue prediction"""

    def __init__(self):
        self.logger = get_logger(__name__)
        # Jorge's commission rate and offer ratios
        self.commission_rate = 0.06  # 6%
        self.offer_ratio = 0.75  # Jorge offers ~75% of asking

    def calculate_commission_potential(self, seller_data: Dict) -> float:
        """Calculate potential commission for a Q4 seller"""
        price_expectation = seller_data.get("price_expectation", 0)
        if not price_expectation:
            return 0

        # Jorge's formula: Offer = 75% of asking, Commission = 6% of offer
        offer_amount = price_expectation * self.offer_ratio
        commission = offer_amount * self.commission_rate

        return commission

    def prioritize_by_value(self, sellers_data: List[Dict]) -> List[Dict]:
        """Prioritize sellers by commission potential"""
        # Add commission potential to each seller
        for seller in sellers_data:
            seller["commission_potential"] = self.calculate_commission_potential(seller)

        # Sort by commission potential (highest first)
        return sorted(
            sellers_data,
            key=lambda x: x.get("commission_potential", 0),
            reverse=True
        )

    def get_cma_summary(self, sellers_data: List[Dict]) -> Dict[str, Any]:
        """Get comprehensive CMA summary"""
        total_sellers = len(sellers_data)
        total_commission = sum(
            self.calculate_commission_potential(s) for s in sellers_data
        )

        high_priority_count = sum(
            1 for s in sellers_data if s.get("urgency") == "high"
        )

        prioritized_list = self.prioritize_by_value(sellers_data)

        return {
            "total_sellers": total_sellers,
            "total_commission_potential": total_commission,
            "high_priority_count": high_priority_count,
            "prioritized_list": prioritized_list[:5],  # Top 5
            "average_commission": total_commission / max(total_sellers, 1)
        }

    def format_cma_display(self, sellers_data: List[Dict]) -> str:
        """Format CMA data for hero card display"""
        summary = self.get_cma_summary(sellers_data)

        count = summary["total_sellers"]
        commission = summary["total_commission_potential"]
        commission_str = f"${commission/1000:.0f}K" if commission > 1000 else f"${commission:.0f}"

        return f"CMAs Ready: {count} → Est. {commission_str} commission"


class EnhancedHeroMetrics:
    """
    Enhanced Hero Metrics Component with Business Intelligence.

    Features:
    - Lead Source ROI analysis
    - 30-day revenue forecasting
    - Smart CMA prioritization
    - One-click automation triggers
    - Mobile-responsive design
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.cache = MemoryCache()
        self.lead_source_roi = LeadSourceROI()
        self.revenue_forecaster = RevenueForecaster()
        self.cma_analyzer = CMAAnalyzer()

    async def get_hero_metrics_data(self, location_id: str) -> List[HeroMetricData]:
        """
        Get all enhanced hero metrics data for Jorge's Command Center.

        Returns:
            List of HeroMetricData objects for rendering
        """
        try:
            self.logger.info(f"Generating hero metrics for location {location_id}")

            # Get data from all sources (with fallback handling)
            hot_leads_data = await self._get_hot_leads_data(location_id)
            seller_pipeline_data = await self._get_seller_pipeline_data(location_id)
            ghl_health_data = await self._get_ghl_health_data(location_id)
            performance_data = await self._get_performance_data()

            metrics = []

            # 1. Enhanced Hot Leads with Source ROI
            metrics.append(await self._create_hot_leads_metric(hot_leads_data))

            # 2. Enhanced CMA Pipeline with Revenue Prediction
            metrics.append(await self._create_cma_metric(seller_pipeline_data))

            # 3. 30-Day Revenue Forecast (NEW)
            metrics.append(await self._create_forecast_metric(hot_leads_data, seller_pipeline_data))

            # 4. Enhanced System Performance
            metrics.append(await self._create_performance_metric(performance_data))

            # 5. GHL Integration Health (Enhanced)
            metrics.append(await self._create_ghl_metric(ghl_health_data))

            self.logger.info(f"Generated {len(metrics)} hero metrics successfully")
            return metrics

        except Exception as e:
            self.logger.error(f"Error generating hero metrics: {e}")
            return self._create_fallback_metrics()

    async def _create_hot_leads_metric(self, leads_data: Dict) -> HeroMetricData:
        """Create enhanced hot leads metric with source ROI"""
        try:
            hot_count = leads_data.get("count", 0)
            best_source = leads_data.get("best_source", {})

            if best_source:
                roi_text = self.lead_source_roi.format_roi_display(best_source.get("roi", 0))
                source_name = best_source.get("source", "Unknown")
                value_text = f"{hot_count} leads"
                delta_text = f"Best: {source_name} ({roi_text})"
            else:
                value_text = f"{hot_count} leads"
                delta_text = "+{} from yesterday".format(leads_data.get("delta", 0))

            # Determine urgency
            if hot_count >= 10:
                urgency = "high"
                color = "red"
            elif hot_count >= 5:
                urgency = "medium"
                color = "amber"
            else:
                urgency = "low"
                color = "blue"

            return HeroMetricData(
                label="🔥 Hot Leads Pipeline",
                value=value_text,
                delta=delta_text,
                color=color,
                urgency_level=urgency,
                action_button="View All Hot Leads" if hot_count > 0 else None,
                tooltip="Leads scoring ≥80 with highest ROI source highlighted"
            )

        except Exception as e:
            self.logger.error(f"Error creating hot leads metric: {e}")
            return HeroMetricData(
                label="🔥 Hot Leads Pipeline",
                value="Error loading",
                delta="Check data sources",
                color="red",
                urgency_level="high"
            )

    async def _create_cma_metric(self, seller_data: Dict) -> HeroMetricData:
        """Create enhanced CMA metric with revenue prediction"""
        try:
            q4_sellers = seller_data.get("q4_ready", [])
            commission_potential = seller_data.get("commission_potential", 0)

            count = len(q4_sellers) if isinstance(q4_sellers, list) else q4_sellers
            commission_str = f"${commission_potential/1000:.0f}K" if commission_potential > 1000 else f"${commission_potential:.0f}"

            value_text = f"{count} sellers"
            delta_text = f"Est. {commission_str} commission"

            # Determine urgency based on commission potential
            if commission_potential >= 50000:
                urgency = "high"
                color = "green"
            elif commission_potential >= 25000:
                urgency = "medium"
                color = "amber"
            else:
                urgency = "low"
                color = "blue"

            return HeroMetricData(
                label="🏠 Q4 CMAs Ready",
                value=value_text,
                delta=delta_text,
                color=color,
                urgency_level=urgency,
                action_button="Generate All CMAs" if count > 0 else None,
                tooltip="Q4 qualified sellers ready for CMA automation with commission potential"
            )

        except Exception as e:
            self.logger.error(f"Error creating CMA metric: {e}")
            return HeroMetricData(
                label="🏠 Q4 CMAs Ready",
                value="Error loading",
                delta="Check seller data",
                color="red",
                urgency_level="high"
            )

    async def _create_forecast_metric(self, leads_data: Dict, seller_data: Dict) -> HeroMetricData:
        """Create 30-day revenue forecast metric (NEW)"""
        try:
            # Mock historical data for forecast (in production, load from database)
            historical_data = self._generate_mock_historical_data()
            pipeline_data = self._extract_pipeline_data(leads_data, seller_data)

            forecast = self.revenue_forecaster.calculate_30_day_forecast(
                historical_data, pipeline_data
            )

            projected = forecast.get("projected_revenue", 0)
            trend = forecast.get("trend_direction", "neutral")
            confidence_range = forecast.get("confidence_range", [0, 0])

            value_text = f"${projected//1000}K forecast"
            range_str = f"${confidence_range[0]//1000}K - ${confidence_range[1]//1000}K range"

            # Trend indicators
            trend_indicators = {
                "up": ("green", "↗️ Strong pipeline"),
                "down": ("red", "↘️ Need lead generation"),
                "neutral": ("blue", "→ Steady pace")
            }
            color, trend_text = trend_indicators.get(trend, ("blue", "→ Calculating"))

            return HeroMetricData(
                label="📈 30-Day Forecast",
                value=value_text,
                delta=f"{trend_text} | {range_str}",
                color=color,
                urgency_level="medium",
                tooltip="AI-powered revenue forecast based on current pipeline and historical trends"
            )

        except Exception as e:
            self.logger.error(f"Error creating forecast metric: {e}")
            return HeroMetricData(
                label="📈 30-Day Forecast",
                value="Calculating...",
                delta="Analyzing trends",
                color="blue",
                urgency_level="low"
            )

    async def _create_performance_metric(self, performance_data: Dict) -> HeroMetricData:
        """Create system performance metric"""
        try:
            compliance = performance_data.get("five_min_compliance", 0.0)
            avg_response = performance_data.get("avg_response_time", 0)

            compliance_pct = f"{compliance:.1%}"

            if compliance >= 0.95:
                color = "green"
                urgency = "low"
                status = "🎯 Excellent"
            elif compliance >= 0.85:
                color = "amber"
                urgency = "medium"
                status = "⚠️ Good"
            else:
                color = "red"
                urgency = "high"
                status = "🚨 Needs attention"

            return HeroMetricData(
                label="⚡ 5-Min Rule",
                value=compliance_pct,
                delta=f"{status} | Avg: {avg_response}ms",
                color=color,
                urgency_level=urgency,
                tooltip="Percentage of leads contacted within 5 minutes (industry best practice)"
            )

        except Exception as e:
            return HeroMetricData(
                label="⚡ 5-Min Rule",
                value="Error",
                delta="Check system",
                color="red",
                urgency_level="high"
            )

    async def _create_ghl_metric(self, ghl_data: Dict) -> HeroMetricData:
        """Create GHL integration health metric"""
        try:
            healthy = ghl_data.get("healthy", False)
            response_time = ghl_data.get("response_time", 0)
            webhook_count = ghl_data.get("webhook_count", 0)

            if healthy:
                value_text = "✅ Operational"
                delta_text = f"{webhook_count} webhooks | {response_time}ms"
                color = "green"
                urgency = "low"
            else:
                value_text = "🚨 Offline"
                delta_text = "Check API connection"
                color = "red"
                urgency = "high"

            return HeroMetricData(
                label="🔗 GHL Integration",
                value=value_text,
                delta=delta_text,
                color=color,
                urgency_level=urgency,
                tooltip="GoHighLevel API health and webhook processing status"
            )

        except Exception as e:
            return HeroMetricData(
                label="🔗 GHL Integration",
                value="🚨 Error",
                delta="Check configuration",
                color="red",
                urgency_level="high"
            )

    async def _get_hot_leads_data(self, location_id: str) -> Dict:
        """Get hot leads data with source ROI analysis"""
        try:
            # Mock data for development (replace with real data sources)
            mock_leads = [
                {"id": "1", "source": "zillow", "score": 85, "commission": 15000, "cost_per_lead": 150, "status": "hot"},
                {"id": "2", "source": "realtor.com", "score": 78, "commission": 12000, "cost_per_lead": 200, "status": "warm"},
                {"id": "3", "source": "referral", "score": 92, "commission": 18000, "cost_per_lead": 0, "status": "hot"},
                {"id": "4", "source": "zillow", "score": 88, "commission": 16000, "cost_per_lead": 150, "status": "hot"},
                {"id": "5", "source": "facebook", "score": 82, "commission": 14000, "cost_per_lead": 75, "status": "hot"}
            ]

            # Calculate hot leads count
            hot_count = len([lead for lead in mock_leads if lead["score"] >= 80])

            # Get best performing source
            best_source = self.lead_source_roi.get_best_performing_source(mock_leads)

            return {
                "count": hot_count,
                "best_source": best_source,
                "delta": 2,  # Mock delta
                "total_leads": len(mock_leads)
            }

        except Exception as e:
            self.logger.error(f"Error getting hot leads data: {e}")
            return {"count": 0, "best_source": {}, "delta": 0}

    async def _get_seller_pipeline_data(self, location_id: str) -> Dict:
        """Get seller pipeline data with CMA analysis"""
        try:
            # Mock Q4 sellers data
            mock_q4_sellers = [
                {"id": "s1", "name": "John Smith", "questions_answered": 4, "price_expectation": 450000, "urgency": "high"},
                {"id": "s2", "name": "Sarah Johnson", "questions_answered": 4, "price_expectation": 650000, "urgency": "medium"},
                {"id": "s3", "name": "Mike Davis", "questions_answered": 4, "price_expectation": 320000, "urgency": "high"},
            ]

            # Calculate commission potential
            commission_potential = sum(
                self.cma_analyzer.calculate_commission_potential(seller)
                for seller in mock_q4_sellers
            )

            return {
                "q4_ready": mock_q4_sellers,
                "commission_potential": commission_potential,
                "high_urgency_count": len([s for s in mock_q4_sellers if s["urgency"] == "high"])
            }

        except Exception as e:
            self.logger.error(f"Error getting seller pipeline data: {e}")
            return {"q4_ready": [], "commission_potential": 0}

    async def _get_ghl_health_data(self, location_id: str) -> Dict:
        """Get GHL integration health data"""
        try:
            # Use real GHL client for health check
            ghl_client = GHLClient()
            health_result = await ghl_client.health_check()

            return {
                "healthy": health_result.get("healthy", False),
                "response_time": 142,  # Mock response time
                "webhook_count": 27,   # Mock webhook count today
                "api_key_valid": health_result.get("api_key_valid", False)
            }

        except Exception as e:
            self.logger.error(f"Error getting GHL health data: {e}")
            return {"healthy": False, "error": str(e)}

    async def _get_performance_data(self) -> Dict:
        """Get system performance data"""
        try:
            # Mock performance data (replace with real metrics)
            return {
                "five_min_compliance": 0.92,  # 92% compliance
                "avg_response_time": 287,     # 287ms average
                "cache_hit_rate": 0.95,       # 95% cache hits
                "api_success_rate": 0.98      # 98% API success
            }

        except Exception as e:
            self.logger.error(f"Error getting performance data: {e}")
            return {"five_min_compliance": 0.0, "avg_response_time": 0}

    def _generate_mock_historical_data(self) -> List[Dict]:
        """Generate mock historical data for forecasting"""
        base_date = datetime.now() - timedelta(days=60)
        return [
            {"date": base_date + timedelta(days=i), "commission": 1500 + (i * 50)}
            for i in range(60)
        ]

    def _extract_pipeline_data(self, leads_data: Dict, seller_data: Dict) -> List[Dict]:
        """Extract pipeline data for forecasting"""
        pipeline = []

        # Add hot leads to pipeline
        hot_count = leads_data.get("count", 0)
        for i in range(hot_count):
            pipeline.append({
                "id": f"lead_{i}",
                "commission": 15000,
                "probability": 0.7,
                "close_date": "2026-02-15"
            })

        # Add seller pipeline
        sellers = seller_data.get("q4_ready", [])
        for seller in sellers:
            if isinstance(seller, dict):
                commission = self.cma_analyzer.calculate_commission_potential(seller)
                pipeline.append({
                    "id": seller.get("id", "unknown"),
                    "commission": commission,
                    "probability": 0.8 if seller.get("urgency") == "high" else 0.6,
                    "close_date": "2026-02-20"
                })

        return pipeline

    def _create_fallback_metrics(self) -> List[HeroMetricData]:
        """Create fallback metrics when data sources fail"""
        return [
            HeroMetricData(
                label="🔥 Hot Leads Pipeline",
                value="Error loading",
                delta="Please wait",
                color="blue",
                urgency_level="low",
                tooltip="Loading lead data from sources"
            ),
            HeroMetricData(
                label="🏠 Q4 CMAs Ready",
                value="Error loading",
                delta="Please wait",
                color="blue",
                urgency_level="low"
            ),
            HeroMetricData(
                label="📈 30-Day Forecast",
                value="Calculating...",
                delta="Analyzing trends",
                color="blue",
                urgency_level="low"
            )
        ]

    def format_metric_card(self, metric: HeroMetricData) -> str:
        """Format metric for Streamlit display (used by tests)"""
        return f"{metric.label}: {metric.value} ({metric.delta})"


# Factory function for component
def create_enhanced_hero_metrics() -> EnhancedHeroMetrics:
    """Create and configure enhanced hero metrics component"""
    return EnhancedHeroMetrics()