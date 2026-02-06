"""
Commission Tracking Component for Jorge Real Estate AI Dashboard.

Displays commission tracking and forecasting including:
- Total commission pipeline
- Qualified lead commission potential
- Monthly/quarterly forecasts
- Commission trend analysis
- Deal conversion tracking

Features real-time updates and business rule integration.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio

from bots.shared.logger import get_logger
from bots.shared.metrics_service import get_metrics_service
from bots.shared.dashboard_models import CommissionMetrics

logger = get_logger(__name__)


class CommissionTrackingComponent:
    """
    Commission tracking component for dashboard display.

    Features:
    - Commission pipeline tracking
    - Deal forecasting and projections
    - Commission trend analysis
    - Lead quality metrics
    - Performance benchmarking
    """

    def __init__(self):
        """Initialize commission tracking component."""
        self.metrics_service = get_metrics_service()
        logger.info("CommissionTrackingComponent initialized")

    def render(self) -> None:
        """
        Render the complete commission tracking component.

        Displays:
        - Commission overview metrics
        - Pipeline visualization
        - Forecast analysis
        - Commission trends
        """
        st.header("💰 Commission Tracking")

        # Fetch commission data
        commission_data = self._fetch_commission_data()

        if commission_data:
            # Display overview metrics
            self._render_overview_metrics(commission_data)

            # Create tabs for different commission views
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Pipeline", "📈 Forecasts", "📉 Trends", "🎯 Performance"])

            with tab1:
                self._render_commission_pipeline(commission_data)

            with tab2:
                self._render_commission_forecasts(commission_data)

            with tab3:
                self._render_commission_trends(commission_data)

            with tab4:
                self._render_performance_analysis(commission_data)

        else:
            self._render_error_state()

    def _fetch_commission_data(self) -> Optional[Dict[str, Any]]:
        """Fetch commission tracking data."""
        try:
            # Fetch data asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            commission_data = loop.run_until_complete(
                self.metrics_service.get_commission_metrics()
            )

            loop.close()
            return commission_data.__dict__ if commission_data else None

        except Exception as e:
            logger.exception(f"Error fetching commission data: {e}")
            return None

    def _render_overview_metrics(self, commission_data: Dict[str, Any]) -> None:
        """Render high-level commission metrics."""
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "💰 Total Pipeline",
                f"${commission_data['total_commission_potential']:,.0f}",
                help="Total commission potential from all qualified leads"
            )

        with col2:
            st.metric(
                "🔥 Hot Leads",
                commission_data['hot_leads_count'],
                help="Number of high-priority qualified leads"
            )

        with col3:
            st.metric(
                "📊 Avg Deal Size",
                f"${commission_data['avg_commission_per_deal']:,.0f}",
                help="Average commission per completed deal"
            )

        with col4:
            monthly_projection = commission_data['projected_monthly_commission']
            st.metric(
                "📈 Monthly Forecast",
                f"${monthly_projection:,.0f}",
                delta=f"${monthly_projection - commission_data['avg_commission_per_deal'] * commission_data['projected_deals']:.0f}",
                help="Projected commission for next 30 days"
            )

    def _render_commission_pipeline(self, commission_data: Dict[str, Any]) -> None:
        """Render commission pipeline visualization."""
        st.subheader("💼 Commission Pipeline")

        col1, col2 = st.columns([2, 1])

        with col1:
            # Pipeline funnel chart
            self._render_pipeline_funnel(commission_data)

        with col2:
            # Pipeline summary stats
            self._render_pipeline_stats(commission_data)

        # Lead quality breakdown
        self._render_lead_quality_breakdown(commission_data)

    def _render_commission_forecasts(self, commission_data: Dict[str, Any]) -> None:
        """Render commission forecasting."""
        st.subheader("🔮 Commission Forecasts")

        # Forecast overview
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "📅 30-Day Forecast",
                f"${commission_data['projected_monthly_commission']:,.0f}",
                help="Projected commission for next 30 days"
            )

        with col2:
            quarterly_forecast = commission_data['projected_monthly_commission'] * 3
            st.metric(
                "📅 90-Day Forecast",
                f"${quarterly_forecast:,.0f}",
                help="Projected commission for next 90 days"
            )

        with col3:
            st.metric(
                "🎯 Projected Deals",
                commission_data['projected_deals'],
                help="Expected number of deals to close"
            )

        # Forecast confidence and scenarios
        self._render_forecast_scenarios(commission_data)

        # Monthly forecast chart
        self._render_monthly_forecast_chart(commission_data)

    def _render_commission_trends(self, commission_data: Dict[str, Any]) -> None:
        """Render commission trend analysis."""
        st.subheader("📈 Commission Trends")

        # Historical trend chart
        if commission_data.get('commission_trend'):
            self._render_commission_trend_chart(commission_data['commission_trend'])

        col1, col2 = st.columns(2)

        with col1:
            # Month-over-month analysis
            self._render_monthly_analysis(commission_data['commission_trend'])

        with col2:
            # Deal velocity tracking
            self._render_deal_velocity(commission_data)

    def _render_performance_analysis(self, commission_data: Dict[str, Any]) -> None:
        """Render performance analysis."""
        st.subheader("🎯 Performance Analysis")

        # Performance metrics
        col1, col2 = st.columns(2)

        with col1:
            st.write("**Lead Quality Metrics**")
            quality_df = pd.DataFrame([
                {"Metric": "Budget Validation Pass Rate", "Value": f"{commission_data['budget_validation_pass_rate']:.1f}%", "Target": ">85%"},
                {"Metric": "Service Area Match Rate", "Value": f"{commission_data['service_area_match_rate']:.1f}%", "Target": ">90%"},
                {"Metric": "Hot Leads Ratio", "Value": f"{(commission_data['hot_leads_count'] / max(commission_data['total_qualified_leads'], 1)) * 100:.1f}%", "Target": ">30%"},
            ])
            st.dataframe(quality_df, hide_index=True, use_container_width=True)

        with col2:
            st.write("**Conversion Metrics**")
            # Calculate conversion rates (mock data for demonstration)
            lead_conversion = 15.2
            deal_conversion = 8.7
            avg_deal_time = 45

            conversion_df = pd.DataFrame([
                {"Metric": "Lead to Qualified", "Value": f"{lead_conversion:.1f}%", "Target": ">10%"},
                {"Metric": "Qualified to Deal", "Value": f"{deal_conversion:.1f}%", "Target": ">5%"},
                {"Metric": "Avg Days to Close", "Value": f"{avg_deal_time} days", "Target": "<60 days"},
            ])
            st.dataframe(conversion_df, hide_index=True, use_container_width=True)

        # Performance recommendations
        self._render_performance_recommendations(commission_data)

    def _render_pipeline_funnel(self, commission_data: Dict[str, Any]) -> None:
        """Render commission pipeline funnel chart."""
        # Mock pipeline data (in production, this would come from actual lead data)
        funnel_data = [
            {"Stage": "Total Leads", "Count": 247, "Commission": 0},
            {"Stage": "Qualified Leads", "Count": commission_data['total_qualified_leads'], "Commission": commission_data['total_commission_potential'] * 0.3},
            {"Stage": "Hot Leads", "Count": commission_data['hot_leads_count'], "Commission": commission_data['total_commission_potential'] * 0.7},
            {"Stage": "Projected Closes", "Count": commission_data['projected_deals'], "Commission": commission_data['projected_monthly_commission']},
        ]

        df = pd.DataFrame(funnel_data)

        fig = go.Figure()

        # Add funnel for lead count
        fig.add_trace(go.Funnel(
            y=df['Stage'],
            x=df['Count'],
            name="Lead Count",
            textinfo="value+percent initial",
            textposition="inside",
            marker_color="lightblue"
        ))

        fig.update_layout(
            title="Commission Pipeline Funnel",
            height=400,
            template="plotly_white"
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_pipeline_stats(self, commission_data: Dict[str, Any]) -> None:
        """Render pipeline statistics."""
        st.write("**Pipeline Health**")

        # Calculate pipeline health metrics
        total_leads = 247  # Mock data
        qualified_rate = (commission_data['total_qualified_leads'] / total_leads) * 100
        hot_lead_rate = (commission_data['hot_leads_count'] / commission_data['total_qualified_leads']) * 100

        stats_df = pd.DataFrame([
            {"Metric": "Qualification Rate", "Value": f"{qualified_rate:.1f}%"},
            {"Metric": "Hot Lead Rate", "Value": f"{hot_lead_rate:.1f}%"},
            {"Metric": "Avg Commission/Lead", "Value": f"${commission_data['total_commission_potential'] / commission_data['total_qualified_leads']:,.0f}"},
            {"Metric": "Pipeline Velocity", "Value": "12.5 days"},
        ])

        st.dataframe(stats_df, hide_index=True, use_container_width=True)

    def _render_lead_quality_breakdown(self, commission_data: Dict[str, Any]) -> None:
        """Render lead quality breakdown."""
        st.write("**Lead Quality Analysis**")

        # Mock lead quality data
        quality_data = pd.DataFrame([
            {"Quality Tier": "Premium (>$500K)", "Count": 18, "Avg Commission": 22500, "Conversion": "12%"},
            {"Quality Tier": "Standard ($300-500K)", "Count": 45, "Avg Commission": 15000, "Conversion": "8%"},
            {"Quality Tier": "Budget (<$300K)", "Count": 26, "Avg Commission": 9000, "Conversion": "5%"},
        ])

        fig = px.bar(
            quality_data,
            x='Quality Tier',
            y='Count',
            color='Avg Commission',
            title='Lead Distribution by Quality Tier',
            text='Count',
            color_continuous_scale='viridis'
        )

        fig.update_traces(textposition='outside')
        fig.update_layout(height=300, template="plotly_white")

        st.plotly_chart(fig, use_container_width=True)

    def _render_forecast_scenarios(self, commission_data: Dict[str, Any]) -> None:
        """Render forecast scenarios (conservative, expected, optimistic)."""
        st.write("**📊 Forecast Scenarios**")

        base_forecast = commission_data['projected_monthly_commission']

        scenarios = pd.DataFrame([
            {"Scenario": "Conservative", "Probability": "70%", "Commission": base_forecast * 0.8, "Deals": commission_data['projected_deals'] - 1},
            {"Scenario": "Expected", "Probability": "50%", "Commission": base_forecast, "Deals": commission_data['projected_deals']},
            {"Scenario": "Optimistic", "Probability": "20%", "Commission": base_forecast * 1.3, "Deals": commission_data['projected_deals'] + 2},
        ])

        # Format commission as currency
        scenarios['Commission Display'] = scenarios['Commission'].apply(lambda x: f"${x:,.0f}")

        st.dataframe(
            scenarios[['Scenario', 'Probability', 'Commission Display', 'Deals']],
            hide_index=True,
            use_container_width=True,
            column_config={
                'Commission Display': 'Commission',
                'Deals': 'Deal Count'
            }
        )

    def _render_monthly_forecast_chart(self, commission_data: Dict[str, Any]) -> None:
        """Render monthly forecast chart."""
        # Generate forecast data for next 6 months
        base_monthly = commission_data['projected_monthly_commission']
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']

        # Apply growth trend and seasonality (mock calculation)
        import random
        forecast_data = []
        for i, month in enumerate(months):
            # Simulate some growth trend with seasonal variation
            growth_factor = 1 + (i * 0.05)  # 5% monthly growth
            seasonal_factor = 0.9 + (random.random() * 0.2)  # ±10% seasonal variation
            projected = base_monthly * growth_factor * seasonal_factor

            forecast_data.append({
                'Month': month,
                'Projected Commission': projected,
                'Conservative': projected * 0.8,
                'Optimistic': projected * 1.2
            })

        df = pd.DataFrame(forecast_data)

        fig = go.Figure()

        # Add projected commission line
        fig.add_trace(go.Scatter(
            x=df['Month'],
            y=df['Projected Commission'],
            mode='lines+markers',
            name='Expected',
            line=dict(color='blue', width=3)
        ))

        # Add confidence band
        fig.add_trace(go.Scatter(
            x=df['Month'],
            y=df['Conservative'],
            mode='lines',
            name='Conservative',
            line=dict(color='red', dash='dash'),
            fill=None
        ))

        fig.add_trace(go.Scatter(
            x=df['Month'],
            y=df['Optimistic'],
            mode='lines',
            name='Optimistic',
            line=dict(color='green', dash='dash'),
            fill='tonexty',
            fillcolor='rgba(0,100,80,0.1)'
        ))

        fig.update_layout(
            title="6-Month Commission Forecast",
            xaxis_title="Month",
            yaxis_title="Commission ($)",
            height=400,
            template="plotly_white"
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_commission_trend_chart(self, commission_trend: List[Dict[str, Any]]) -> None:
        """Render historical commission trend chart."""
        if not commission_trend:
            st.info("Historical commission data not available yet.")
            return

        df = pd.DataFrame(commission_trend)

        fig = go.Figure()

        # Add commission line
        fig.add_trace(go.Scatter(
            x=df['month'],
            y=df['amount'],
            mode='lines+markers',
            name='Commission',
            line=dict(color='green', width=3),
            marker=dict(size=8)
        ))

        # Add deals count on secondary axis
        fig.add_trace(go.Scatter(
            x=df['month'],
            y=df['deals'],
            mode='lines+markers',
            name='Deals',
            yaxis='y2',
            line=dict(color='blue', width=2),
            marker=dict(size=6)
        ))

        fig.update_layout(
            title="Historical Commission & Deal Trends",
            xaxis_title="Month",
            yaxis=dict(title="Commission ($)", side="left"),
            yaxis2=dict(title="Deal Count", side="right", overlaying="y"),
            height=400,
            template="plotly_white"
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_monthly_analysis(self, commission_trend: List[Dict[str, Any]]) -> None:
        """Render month-over-month analysis."""
        if not commission_trend or len(commission_trend) < 2:
            st.info("Insufficient data for trend analysis")
            return

        st.write("**Month-over-Month Growth**")

        # Calculate growth rates
        latest = commission_trend[-1]
        previous = commission_trend[-2]

        commission_growth = ((latest['amount'] - previous['amount']) / previous['amount']) * 100
        deal_growth = ((latest['deals'] - previous['deals']) / previous['deals']) * 100

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Commission Growth",
                f"{commission_growth:+.1f}%",
                delta=f"${latest['amount'] - previous['amount']:,.0f}"
            )

        with col2:
            st.metric(
                "Deal Count Growth",
                f"{deal_growth:+.1f}%",
                delta=f"{latest['deals'] - previous['deals']:+d} deals"
            )

    def _render_deal_velocity(self, commission_data: Dict[str, Any]) -> None:
        """Render deal velocity metrics."""
        st.write("**Deal Velocity Tracking**")

        # Mock velocity data
        velocity_metrics = pd.DataFrame([
            {"Metric": "Avg Lead to Qualified", "Time": "8 days", "Target": "<10 days"},
            {"Metric": "Avg Qualified to Contract", "Time": "18 days", "Target": "<20 days"},
            {"Metric": "Avg Contract to Close", "Time": "35 days", "Target": "<45 days"},
            {"Metric": "Total Cycle Time", "Time": "61 days", "Target": "<75 days"},
        ])

        st.dataframe(velocity_metrics, hide_index=True, use_container_width=True)

    def _render_performance_recommendations(self, commission_data: Dict[str, Any]) -> None:
        """Render performance recommendations."""
        st.write("**🎯 Recommendations**")

        recommendations = []

        # Analyze performance and generate recommendations
        budget_pass_rate = commission_data['budget_validation_pass_rate']
        service_area_match = commission_data['service_area_match_rate']
        hot_lead_ratio = (commission_data['hot_leads_count'] / max(commission_data['total_qualified_leads'], 1)) * 100

        if budget_pass_rate < 85:
            recommendations.append("🎯 Improve budget validation process - currently below 85% target")

        if service_area_match < 90:
            recommendations.append("📍 Focus on leads within service area - improve targeting")

        if hot_lead_ratio < 30:
            recommendations.append("🔥 Increase hot lead conversion - work on lead nurturing")

        if commission_data['projected_deals'] < 5:
            recommendations.append("📈 Scale up lead generation - projected deals below target")

        if not recommendations:
            recommendations.append("✅ Performance is on track - continue current strategies")

        for rec in recommendations:
            st.write(f"• {rec}")

    def _render_error_state(self) -> None:
        """Render error state when data cannot be loaded."""
        st.error("❌ Unable to load commission tracking data")
        st.write("This could be due to:")
        st.write("• Temporary service unavailability")
        st.write("• Network connectivity issues")
        st.write("• Insufficient commission data")

        if st.button("🔄 Retry", key="retry_commission_tracking"):
            st.rerun()


def render_commission_tracking() -> None:
    """
    Render the commission tracking component.

    Entry point for use in dashboard pages.
    """
    try:
        component = CommissionTrackingComponent()
        component.render()

    except Exception as e:
        logger.exception(f"Error rendering commission tracking: {e}")
        st.error("Failed to load commission tracking. Please refresh the page.")


# Component entry point
if __name__ == "__main__":
    # For testing the component standalone
    st.set_page_config(
        page_title="Commission Tracking",
        page_icon="💰",
        layout="wide"
    )
    render_commission_tracking()