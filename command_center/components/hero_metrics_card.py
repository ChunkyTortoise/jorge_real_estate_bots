"""
Hero Metrics Card Component for Jorge Real Estate AI Dashboard.

Displays 4 key performance indicators (KPIs) with delta indicators.
"""
import streamlit as st

from bots.shared.dashboard_models import HeroMetrics


def render_hero_metrics(hero_metrics: HeroMetrics) -> None:
    """
    Render hero metrics cards in 4-column layout.

    Args:
        hero_metrics: HeroMetrics dataclass from DashboardDataService
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Active Conversations",
            value=hero_metrics.active_conversations,
            delta=f"+{hero_metrics.active_conversations_change}" if hero_metrics.active_conversations_change > 0 else str(hero_metrics.active_conversations_change)
        )

    with col2:
        # Qualification rate as percentage
        qual_rate = hero_metrics.qualification_rate * 100
        st.metric(
            label="Qualification Rate",
            value=f"{qual_rate:.1f}%",
            delta=f"{hero_metrics.qualification_rate_change * 100:+.1f}%" if hero_metrics.qualification_rate_change else None
        )

    with col3:
        # Average response time in minutes
        st.metric(
            label="Avg Response Time",
            value=f"{hero_metrics.avg_response_time_minutes:.1f}m",
            delta=f"{hero_metrics.response_time_change:+.1f}m" if hero_metrics.response_time_change else None,
            delta_color="inverse"  # Lower is better
        )

    with col4:
        st.metric(
            label="Hot Leads (24h)",
            value=hero_metrics.hot_leads_count,
            delta=f"+{hero_metrics.hot_leads_change}" if hero_metrics.hot_leads_change > 0 else str(hero_metrics.hot_leads_change)
        )
