"""
Performance Chart Component for Jorge Real Estate AI Dashboard.

Displays time-series chart of qualification metrics.
"""
from datetime import datetime, timedelta

import plotly.graph_objects as go
import streamlit as st

from bots.shared.dashboard_models import PerformanceMetrics


def render_performance_chart(performance: PerformanceMetrics) -> None:
    """
    Render performance analytics chart.

    Args:
        performance: PerformanceMetrics dataclass from DashboardDataService
    """
    st.subheader("Performance Analytics (24h)")

    # Generate hourly time series for last 24 hours
    now = datetime.now()
    hours = [now - timedelta(hours=i) for i in range(24, 0, -1)]
    hour_labels = [h.strftime("%H:%M") for h in hours]

    # Mock time-series data (in production, this comes from PerformanceTracker)
    # For now, use current metrics as baseline
    qual_rates = [performance.qualification_rate + (i - 12) * 0.02 for i in range(24)]
    response_times = [performance.avg_response_time + (i - 12) * 0.5 for i in range(24)]

    # Create dual-axis chart
    fig = go.Figure()

    # Qualification rate (left y-axis)
    fig.add_trace(go.Scatter(
        x=hour_labels,
        y=[r * 100 for r in qual_rates],  # Convert to percentage
        name="Qualification Rate",
        mode='lines+markers',
        line=dict(color='#2E7D32', width=2),
        yaxis='y1'
    ))

    # Response time (right y-axis)
    fig.add_trace(go.Scatter(
        x=hour_labels,
        y=response_times,
        name="Avg Response Time",
        mode='lines+markers',
        line=dict(color='#D32F2F', width=2),
        yaxis='y2'
    ))

    # Update layout
    fig.update_layout(
        title="24-Hour Performance Trends",
        xaxis=dict(title="Time"),
        yaxis=dict(
            title=dict(text="Qualification Rate (%)", font=dict(color='#2E7D32')),
            tickfont=dict(color='#2E7D32')
        ),
        yaxis2=dict(
            title=dict(text="Response Time (min)", font=dict(color='#D32F2F')),
            tickfont=dict(color='#D32F2F'),
            overlaying='y',
            side='right'
        ),
        hovermode='x unified',
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary metrics below chart
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Budget Performance",
            f"{performance.budget_performance * 100:.1f}%",
            delta=f"{(performance.budget_performance - 1) * 100:+.1f}%"
        )

    with col2:
        st.metric(
            "Timeline Performance",
            f"{performance.timeline_performance * 100:.1f}%",
            delta=f"{(performance.timeline_performance - 1) * 100:+.1f}%"
        )

    with col3:
        st.metric(
            "Commission Performance",
            f"{performance.commission_performance * 100:.1f}%",
            delta=f"{(performance.commission_performance - 1) * 100:+.1f}%"
        )
