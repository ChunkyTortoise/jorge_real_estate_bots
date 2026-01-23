#!/usr/bin/env python3
"""
Jorge's KPI Dashboard - Real-time Bot Performance & Lead Analytics

Streamlined version adapted for MVP structure.
Full production version: jorge_deployment_package/jorge_kpi_dashboard.py

Features:
- Key performance metrics
- Lead conversion funnel
- Response time analytics
- Temperature distribution
- Hot leads alerts

Author: Claude Code Assistant
Created: 2026-01-23
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure Streamlit page
st.set_page_config(
    page_title="Jorge's Bot KPI Dashboard",
    page_icon="🏠",
    layout="wide"
)


class JorgeKPIDashboard:
    """
    Real-time KPI dashboard for Jorge's lead bot.

    MVP version with mock data - ready for production data integration.
    """

    def __init__(self):
        """Initialize dashboard with mock data."""
        pass

    def render_dashboard(self):
        """Render the complete KPI dashboard."""

        # Header
        st.title("🏠 Jorge's Bot Performance Dashboard")
        st.markdown("**Real-time analytics for lead bot performance**")

        # Refresh control
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("🔄 Refresh Data"):
                st.rerun()

        # Key metrics overview
        self._render_key_metrics()

        st.divider()

        # Performance charts
        col1, col2 = st.columns(2)
        with col1:
            self._render_lead_funnel()
            self._render_response_performance()
        with col2:
            self._render_conversion_trends()
            self._render_temperature_distribution()

        st.divider()

        # Hot leads alerts
        self._render_hot_leads_alerts()

        st.divider()

        # Recent activity
        self._render_recent_activity()

    def _render_key_metrics(self):
        """Render key performance metrics cards."""

        st.subheader("📊 Today's Key Metrics")

        # Mock metrics data
        metrics = {
            "total_conversations": {"value": 47, "delta": "+12", "delta_color": "normal"},
            "hot_leads": {"value": 8, "delta": "+3", "delta_color": "normal"},
            "qualified_leads": {"value": 23, "delta": "+7", "delta_color": "normal"},
            "appointments": {"value": 5, "delta": "+2", "delta_color": "normal"},
            "pipeline_value": {"value": "$125K", "delta": "+$45K", "delta_color": "normal"}
        }

        # Render metric cards
        cols = st.columns(5)

        with cols[0]:
            st.metric(
                label="Total Conversations",
                value=metrics["total_conversations"]["value"],
                delta=metrics["total_conversations"]["delta"]
            )

        with cols[1]:
            st.metric(
                label="🔥 Hot Leads",
                value=metrics["hot_leads"]["value"],
                delta=metrics["hot_leads"]["delta"]
            )

        with cols[2]:
            st.metric(
                label="Qualified Leads",
                value=metrics["qualified_leads"]["value"],
                delta=metrics["qualified_leads"]["delta"]
            )

        with cols[3]:
            st.metric(
                label="Appointments Booked",
                value=metrics["appointments"]["value"],
                delta=metrics["appointments"]["delta"]
            )

        with cols[4]:
            st.metric(
                label="Pipeline Value",
                value=metrics["pipeline_value"]["value"],
                delta=metrics["pipeline_value"]["delta"]
            )

    def _render_lead_funnel(self):
        """Render lead conversion funnel visualization."""

        st.subheader("🎯 Lead Conversion Funnel")

        # Mock funnel data
        funnel_data = pd.DataFrame({
            "Stage": [
                "Total Conversations",
                "Qualified Leads",
                "Hot Leads",
                "Appointments",
                "Deals Closed"
            ],
            "Count": [47, 23, 8, 5, 2],
            "Conversion": ["100%", "49%", "17%", "11%", "4%"]
        })

        fig = go.Figure(go.Funnel(
            y=funnel_data["Stage"],
            x=funnel_data["Count"],
            textinfo="value+percent initial",
            marker=dict(color=["#4CAF50", "#8BC34A", "#FFC107", "#FF9800", "#FF5722"])
        ))

        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=0, b=0)
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_conversion_trends(self):
        """Render 30-day conversion trends."""

        st.subheader("📈 Conversion Trends (30 Days)")

        # Mock trend data
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        trends_data = pd.DataFrame({
            "Date": dates,
            "Leads": [15, 18, 22, 19, 25, 28, 31, 27, 23, 20,
                     24, 26, 29, 32, 28, 30, 33, 35, 31, 29,
                     27, 30, 32, 34, 36, 38, 40, 42, 45, 47],
            "Qualified": [7, 9, 11, 9, 12, 14, 15, 13, 11, 10,
                         12, 13, 14, 16, 14, 15, 16, 17, 15, 14,
                         13, 15, 16, 17, 18, 19, 20, 21, 22, 23],
            "Hot": [2, 3, 4, 3, 5, 5, 6, 5, 4, 3,
                   4, 5, 5, 6, 5, 6, 6, 7, 6, 5,
                   5, 6, 6, 7, 7, 8, 8, 8, 8, 8]
        })

        fig = px.line(
            trends_data,
            x="Date",
            y=["Leads", "Qualified", "Hot"],
            title="",
            labels={"value": "Count", "variable": "Type"}
        )

        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=0, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_response_performance(self):
        """Render bot response performance metrics."""

        st.subheader("⚡ Response Performance")

        # Mock response time data
        perf_data = pd.DataFrame({
            "Bot": ["Lead Bot", "Lead Bot", "Lead Bot"],
            "Metric": ["Avg Response Time", "5-Min Rule", "Success Rate"],
            "Value": ["342ms", "99.8%", "98.5%"]
        })

        # Display as metric cards
        for _, row in perf_data.iterrows():
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**{row['Metric']}**")
            with col2:
                if "ms" in row['Value']:
                    st.success(row['Value'])
                else:
                    st.info(row['Value'])

    def _render_temperature_distribution(self):
        """Render lead temperature distribution pie chart."""

        st.subheader("🌡️ Lead Temperature Distribution")

        # Mock temperature data
        temp_data = pd.DataFrame({
            "Temperature": ["🔥 Hot (80-100)", "☀️ Warm (60-79)", "❄️ Cold (0-59)"],
            "Count": [8, 15, 24]
        })

        fig = px.pie(
            temp_data,
            values="Count",
            names="Temperature",
            color="Temperature",
            color_discrete_map={
                "🔥 Hot (80-100)": "#FF5722",
                "☀️ Warm (60-79)": "#FFC107",
                "❄️ Cold (0-59)": "#2196F3"
            }
        )

        fig.update_layout(
            height=400,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True
        )

        st.plotly_chart(fig, use_container_width=True)

    def _render_hot_leads_alerts(self):
        """Render hot leads alert section."""

        st.subheader("🚨 Hot Leads Alert - Immediate Action Required")

        # Mock hot leads
        hot_leads = [
            {
                "name": "Sarah Johnson",
                "score": 92,
                "budget": "$550K",
                "location": "Dallas",
                "timeline": "30 days",
                "contact": "+1 (555) 123-4567"
            },
            {
                "name": "Michael Chen",
                "score": 88,
                "budget": "$425K",
                "location": "Plano",
                "timeline": "60 days",
                "contact": "+1 (555) 234-5678"
            },
            {
                "name": "Jennifer Martinez",
                "score": 85,
                "budget": "$680K",
                "location": "Frisco",
                "timeline": "45 days",
                "contact": "+1 (555) 345-6789"
            }
        ]

        # Render lead cards
        cols = st.columns(3)
        for idx, lead in enumerate(hot_leads):
            with cols[idx]:
                with st.container():
                    st.markdown(f"### {lead['name']}")
                    st.markdown(f"**Score:** {lead['score']} 🔥")
                    st.markdown(f"**Budget:** {lead['budget']}")
                    st.markdown(f"**Location:** {lead['location']}")
                    st.markdown(f"**Timeline:** {lead['timeline']}")
                    st.markdown(f"**Contact:** {lead['contact']}")

                    if st.button(f"📞 Call {lead['name'].split()[0]}", key=f"call_{idx}"):
                        st.success(f"Calling {lead['name']}...")

    def _render_recent_activity(self):
        """Render recent activity log."""

        st.subheader("📋 Recent Activity")

        # Mock activity data
        activities = [
            {"time": "2 min ago", "bot": "Lead Bot", "action": "Qualified new lead: Sarah Johnson (Score: 92)", "temp": "🔥"},
            {"time": "15 min ago", "bot": "Lead Bot", "action": "Responded to inquiry: Michael Chen", "temp": "🔥"},
            {"time": "32 min ago", "bot": "Lead Bot", "action": "Updated lead score: Jennifer Martinez (85)", "temp": "🔥"},
            {"time": "1 hour ago", "bot": "Lead Bot", "action": "New conversation started: David Lee", "temp": "☀️"},
            {"time": "2 hours ago", "bot": "Lead Bot", "action": "Appointment booked: Sarah Johnson", "temp": "🔥"},
        ]

        # Render activity table
        for activity in activities:
            col1, col2, col3 = st.columns([1, 2, 6])
            with col1:
                st.markdown(f"**{activity['time']}**")
            with col2:
                st.markdown(f"*{activity['bot']}*")
            with col3:
                st.markdown(f"{activity['temp']} {activity['action']}")

        st.divider()


# Main execution
if __name__ == "__main__":
    st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

    dashboard = JorgeKPIDashboard()
    dashboard.render_dashboard()
