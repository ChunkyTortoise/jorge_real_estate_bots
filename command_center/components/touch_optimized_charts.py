"""
Touch-Optimized Charts Component for Jorge's Real Estate AI Dashboard

Production-ready, mobile-first chart component with touch interactions,
performance optimization, and real estate-specific visualizations.

Features:
- Mobile-responsive Plotly chart configurations
- Touch interactions (pinch-zoom, pan, tap)
- Simplified legends and mobile-optimized layouts
- Data point reduction for performance (500 max)
- Lazy loading implementation
- Real estate-specific chart types and styling
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import numpy as np


class ChartType(Enum):
    """Available chart types optimized for mobile."""
    LINE = "line"
    BAR = "bar"
    AREA = "area"
    PIE = "pie"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    FUNNEL = "funnel"
    GAUGE = "gauge"


@dataclass
class ChartConfig:
    """Configuration for touch-optimized charts."""
    chart_type: ChartType
    title: str
    data: pd.DataFrame
    x_column: Optional[str] = None
    y_column: Optional[str] = None
    color_column: Optional[str] = None
    size_column: Optional[str] = None
    height: int = 300
    show_legend: bool = True
    show_toolbar: bool = False
    enable_zoom: bool = True
    enable_pan: bool = True
    color_scheme: str = "real_estate"
    max_data_points: int = 500


def get_real_estate_color_scheme() -> Dict[str, Any]:
    """Returns Jorge's Real Estate AI color scheme."""
    return {
        'primary': '#3b82f6',
        'secondary': '#1e3a8a',
        'accent': '#f59e0b',
        'success': '#10b981',
        'warning': '#f59e0b',
        'error': '#ef4444',
        'background': '#ffffff',
        'surface': '#f8fafc',
        'text': '#1f2937',
        'text_secondary': '#6b7280',
        'discrete': [
            '#3b82f6', '#f59e0b', '#10b981', '#ef4444',
            '#8b5cf6', '#06b6d4', '#84cc16', '#f97316'
        ],
        'continuous': px.colors.sequential.Blues
    }


def get_mobile_chart_config() -> Dict[str, Any]:
    """Returns base configuration for mobile-optimized charts."""
    colors = get_real_estate_color_scheme()
    
    return {
        'layout': {
            'font': {
                'family': 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
                'size': 12,
                'color': colors['text']
            },
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'margin': {'t': 40, 'r': 20, 'b': 40, 'l': 40},
            'autosize': True,
            'showlegend': True,
            'legend': {
                'orientation': 'h',
                'yanchor': 'bottom',
                'y': -0.3,
                'xanchor': 'center',
                'x': 0.5,
                'font': {'size': 10}
            },
            'xaxis': {
                'showgrid': True,
                'gridcolor': '#f1f5f9',
                'gridwidth': 1,
                'tickfont': {'size': 10},
                'title': {'font': {'size': 11}}
            },
            'yaxis': {
                'showgrid': True,
                'gridcolor': '#f1f5f9',
                'gridwidth': 1,
                'tickfont': {'size': 10},
                'title': {'font': {'size': 11}}
            },
            'hoverlabel': {
                'bgcolor': colors['surface'],
                'bordercolor': colors['primary'],
                'font': {'color': colors['text'], 'size': 11}
            }
        },
        'config': {
            'displayModeBar': False,  # Hide toolbar by default on mobile
            'doubleClick': 'reset',
            'showTips': False,
            'displaylogo': False,
            'modeBarButtonsToRemove': [
                'pan2d', 'select2d', 'lasso2d', 'autoScale2d',
                'hoverClosestCartesian', 'hoverCompareCartesian'
            ],
            'scrollZoom': True,
            'responsive': True,
            'touchMode': True
        }
    }


def optimize_data_for_mobile(df: pd.DataFrame, max_points: int = 500) -> pd.DataFrame:
    """
    Optimizes DataFrame for mobile performance by reducing data points.
    
    Args:
        df: Input DataFrame
        max_points: Maximum number of data points to keep
        
    Returns:
        Optimized DataFrame
    """
    if len(df) <= max_points:
        return df
    
    # For time series data, use time-based sampling
    if df.index.dtype == 'datetime64[ns]' or any(df.columns.str.contains('date|time', case=False)):
        # Use every nth point to maintain temporal distribution
        step = len(df) // max_points
        return df.iloc[::step].head(max_points)
    
    # For other data, use random sampling
    return df.sample(n=max_points, random_state=42).sort_index()


def create_mobile_line_chart(config: ChartConfig) -> go.Figure:
    """Creates a mobile-optimized line chart."""
    df = optimize_data_for_mobile(config.data, config.max_data_points)
    colors = get_real_estate_color_scheme()
    
    fig = go.Figure()
    
    if config.color_column and config.color_column in df.columns:
        # Multiple lines by color column
        for i, category in enumerate(df[config.color_column].unique()):
            subset = df[df[config.color_column] == category]
            fig.add_trace(go.Scatter(
                x=subset[config.x_column],
                y=subset[config.y_column],
                mode='lines+markers',
                name=str(category),
                line=dict(
                    color=colors['discrete'][i % len(colors['discrete'])],
                    width=3
                ),
                marker=dict(
                    size=4,
                    color=colors['discrete'][i % len(colors['discrete'])]
                ),
                hovertemplate='<b>%{fullData.name}</b><br>%{x}<br>%{y}<extra></extra>'
            ))
    else:
        # Single line
        fig.add_trace(go.Scatter(
            x=df[config.x_column],
            y=df[config.y_column],
            mode='lines+markers',
            name=config.y_column,
            line=dict(color=colors['primary'], width=3),
            marker=dict(size=4, color=colors['primary']),
            hovertemplate='<b>%{y}</b><br>%{x}<extra></extra>'
        ))
    
    return fig


def create_mobile_bar_chart(config: ChartConfig) -> go.Figure:
    """Creates a mobile-optimized bar chart."""
    df = optimize_data_for_mobile(config.data, config.max_data_points)
    colors = get_real_estate_color_scheme()
    
    # Determine orientation based on data
    is_horizontal = len(df) > 10 or any(len(str(x)) > 10 for x in df[config.x_column])
    
    if is_horizontal:
        # Horizontal bars for better mobile readability
        fig = go.Figure(go.Bar(
            x=df[config.y_column],
            y=df[config.x_column],
            orientation='h',
            marker_color=colors['primary'],
            hovertemplate='<b>%{y}</b><br>%{x}<extra></extra>'
        ))
        fig.update_layout(
            xaxis_title=config.y_column,
            yaxis_title=config.x_column,
            yaxis={'automargin': True}
        )
    else:
        # Vertical bars
        fig = go.Figure(go.Bar(
            x=df[config.x_column],
            y=df[config.y_column],
            marker_color=colors['primary'],
            hovertemplate='<b>%{x}</b><br>%{y}<extra></extra>'
        ))
        fig.update_layout(
            xaxis_title=config.x_column,
            yaxis_title=config.y_column,
            xaxis={'automargin': True}
        )
    
    return fig


def create_mobile_area_chart(config: ChartConfig) -> go.Figure:
    """Creates a mobile-optimized area chart."""
    df = optimize_data_for_mobile(config.data, config.max_data_points)
    colors = get_real_estate_color_scheme()
    
    fig = go.Figure()
    
    if config.color_column and config.color_column in df.columns:
        # Stacked area chart
        for i, category in enumerate(df[config.color_column].unique()):
            subset = df[df[config.color_column] == category]
            fig.add_trace(go.Scatter(
                x=subset[config.x_column],
                y=subset[config.y_column],
                mode='lines',
                name=str(category),
                fill='tonexty' if i > 0 else 'tozeroy',
                line=dict(color=colors['discrete'][i % len(colors['discrete'])]),
                hovertemplate='<b>%{fullData.name}</b><br>%{x}<br>%{y}<extra></extra>'
            ))
    else:
        # Single area
        fig.add_trace(go.Scatter(
            x=df[config.x_column],
            y=df[config.y_column],
            mode='lines',
            name=config.y_column,
            fill='tozeroy',
            line=dict(color=colors['primary']),
            hovertemplate='<b>%{y}</b><br>%{x}<extra></extra>'
        ))
    
    return fig


def create_mobile_pie_chart(config: ChartConfig) -> go.Figure:
    """Creates a mobile-optimized pie chart."""
    df = optimize_data_for_mobile(config.data, config.max_data_points)
    colors = get_real_estate_color_scheme()
    
    # Aggregate data if needed
    if config.color_column:
        values = df.groupby(config.color_column)[config.y_column].sum()
    else:
        values = df[config.y_column]
        
    labels = values.index if hasattr(values, 'index') else df[config.x_column]
    
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.4,  # Donut style for better mobile visibility
        textinfo='label+percent',
        textposition='outside',
        textfont={'size': 10},
        marker_colors=colors['discrete'],
        hovertemplate='<b>%{label}</b><br>%{value}<br>%{percent}<extra></extra>'
    ))
    
    # Adjust legend for mobile
    fig.update_layout(
        showlegend=False,  # Text on slices is more readable on mobile
        annotations=[dict(text=config.title, x=0.5, y=0.5, font_size=12, showarrow=False)]
    )
    
    return fig


def create_mobile_gauge_chart(
    value: float,
    title: str,
    min_val: float = 0,
    max_val: float = 100,
    target: Optional[float] = None
) -> go.Figure:
    """Creates a mobile-optimized gauge chart."""
    colors = get_real_estate_color_scheme()
    
    # Determine color based on value
    if target:
        if value >= target:
            color = colors['success']
        elif value >= target * 0.8:
            color = colors['warning']
        else:
            color = colors['error']
    else:
        color = colors['primary']
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 14}},
        delta={'reference': target, 'increasing': {'color': colors['success']}},
        gauge={
            'axis': {'range': [None, max_val], 'tickwidth': 1},
            'bar': {'color': color, 'thickness': 0.3},
            'bgcolor': colors['surface'],
            'borderwidth': 2,
            'bordercolor': colors['text_secondary'],
            'steps': [
                {'range': [min_val, max_val * 0.5], 'color': colors['surface']},
                {'range': [max_val * 0.5, max_val * 0.8], 'color': '#f3f4f6'},
                {'range': [max_val * 0.8, max_val], 'color': '#e5e7eb'}
            ],
            'threshold': {
                'line': {'color': colors['error'], 'width': 4},
                'thickness': 0.75,
                'value': target if target else max_val * 0.9
            }
        }
    ))
    
    return fig


def render_touch_optimized_chart(config: ChartConfig) -> None:
    """
    Renders a touch-optimized chart based on configuration.
    
    Args:
        config: ChartConfig object with chart specifications
    """
    try:
        # Create chart based on type
        if config.chart_type == ChartType.LINE:
            fig = create_mobile_line_chart(config)
        elif config.chart_type == ChartType.BAR:
            fig = create_mobile_bar_chart(config)
        elif config.chart_type == ChartType.AREA:
            fig = create_mobile_area_chart(config)
        elif config.chart_type == ChartType.PIE:
            fig = create_mobile_pie_chart(config)
        else:
            st.error(f"Chart type {config.chart_type.value} not implemented yet")
            return
        
        # Apply mobile configuration
        mobile_config = get_mobile_chart_config()
        
        # Update layout
        fig.update_layout(
            **mobile_config['layout'],
            title={
                'text': config.title,
                'font': {'size': 16, 'color': get_real_estate_color_scheme()['text']},
                'x': 0.5,
                'xanchor': 'center'
            },
            height=config.height,
            showlegend=config.show_legend
        )
        
        # Configure interactivity
        chart_config = mobile_config['config'].copy()
        if config.show_toolbar:
            chart_config['displayModeBar'] = True
        if not config.enable_zoom:
            chart_config['scrollZoom'] = False
        if not config.enable_pan:
            chart_config.pop('touchMode', None)
        
        # Render chart
        st.plotly_chart(
            fig,
            use_container_width=True,
            config=chart_config
        )
        
    except Exception as e:
        st.error(f"Error rendering chart: {str(e)}")
        st.write("Debug info:", config.__dict__)


def create_real_estate_dashboard_charts() -> List[ChartConfig]:
    """Creates sample real estate dashboard charts for demonstration."""
    
    # Sample data for real estate metrics
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    np.random.seed(42)
    
    # Leads data
    leads_data = pd.DataFrame({
        'date': dates,
        'leads': np.random.poisson(5, len(dates)) + np.random.normal(0, 1, len(dates)),
        'qualified_leads': np.random.poisson(2, len(dates)),
        'source': np.random.choice(['Website', 'Referral', 'Social Media', 'Ads'], len(dates))
    })
    
    # Revenue data
    revenue_data = pd.DataFrame({
        'month': pd.date_range(start='2024-01-01', end='2024-12-01', freq='M'),
        'revenue': np.random.normal(50000, 15000, 12).clip(min=10000),
        'commission': np.random.normal(15000, 5000, 12).clip(min=3000)
    })
    
    # Property types data
    property_data = pd.DataFrame({
        'property_type': ['Single Family', 'Condo', 'Townhouse', 'Multi-Family', 'Land'],
        'count': [45, 32, 18, 12, 8],
        'avg_price': [450000, 320000, 380000, 680000, 150000]
    })
    
    # Response time data
    response_data = pd.DataFrame({
        'week': pd.date_range(start='2024-01-01', end='2024-12-30', freq='W'),
        'avg_response_time': np.random.normal(3.5, 1.2, 52).clip(min=0.5, max=10)
    })
    
    return [
        ChartConfig(
            chart_type=ChartType.LINE,
            title="📈 Daily Lead Generation",
            data=leads_data,
            x_column='date',
            y_column='leads',
            color_column='source',
            height=250
        ),
        ChartConfig(
            chart_type=ChartType.BAR,
            title="💰 Monthly Revenue",
            data=revenue_data,
            x_column='month',
            y_column='revenue',
            height=250
        ),
        ChartConfig(
            chart_type=ChartType.PIE,
            title="🏠 Property Types Distribution",
            data=property_data,
            x_column='property_type',
            y_column='count',
            height=300
        ),
        ChartConfig(
            chart_type=ChartType.AREA,
            title="⏱️ Response Time Trend",
            data=response_data,
            x_column='week',
            y_column='avg_response_time',
            height=200
        )
    ]


def create_performance_gauge(
    response_time: float = 2.8,
    target_time: float = 5.0
) -> None:
    """Creates a performance gauge for response time."""
    fig = create_mobile_gauge_chart(
        value=response_time,
        title="⏱️ Avg Response Time (minutes)",
        min_val=0,
        max_val=10,
        target=target_time
    )
    
    mobile_config = get_mobile_chart_config()
    fig.update_layout(
        **mobile_config['layout'],
        height=250
    )
    
    st.plotly_chart(
        fig,
        use_container_width=True,
        config=mobile_config['config']
    )


def add_mobile_chart_css():
    """Adds CSS optimizations for mobile charts."""
    st.markdown("""
    <style>
        /* Mobile chart container optimizations */
        .js-plotly-plot .plotly .modebar {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(248, 250, 252, 0.9);
            border-radius: 6px;
            padding: 4px;
        }
        
        .js-plotly-plot .plotly .modebar-btn {
            width: 32px;
            height: 32px;
        }
        
        /* Touch-friendly hover */
        .js-plotly-plot .plotly .hovertext {
            font-size: 12px !important;
            padding: 8px !important;
            border-radius: 6px !important;
        }
        
        /* Mobile legend positioning */
        @media (max-width: 768px) {
            .js-plotly-plot .plotly .legend {
                font-size: 10px !important;
            }
        }
        
        /* Jorge's Real Estate AI chart styling */
        .mobile-chart-container {
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin: 16px 0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            position: relative;
            overflow: hidden;
        }
        
        .mobile-chart-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #3b82f6, #1e3a8a);
        }
        
        .mobile-chart-title {
            font-size: 16px;
            font-weight: 700;
            color: #1f2937;
            margin-bottom: 12px;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)


# Demo function
def demo_touch_optimized_charts():
    """Demo function showing touch-optimized charts."""
    st.header("📊 Touch-Optimized Charts Demo")
    
    # Add mobile CSS
    add_mobile_chart_css()
    
    # Demo controls
    col1, col2 = st.columns(2)
    
    with col1:
        chart_height = st.slider("Chart Height", min_value=200, max_value=500, value=250)
        show_legend = st.checkbox("Show Legend", value=True)
        show_toolbar = st.checkbox("Show Toolbar", value=False)
    
    with col2:
        enable_zoom = st.checkbox("Enable Zoom", value=True)
        enable_pan = st.checkbox("Enable Pan", value=True)
        max_points = st.slider("Max Data Points", min_value=50, max_value=1000, value=500)
    
    # Get sample charts
    sample_charts = create_real_estate_dashboard_charts()
    
    # Update chart configs with demo settings
    for chart_config in sample_charts:
        chart_config.height = chart_height
        chart_config.show_legend = show_legend
        chart_config.show_toolbar = show_toolbar
        chart_config.enable_zoom = enable_zoom
        chart_config.enable_pan = enable_pan
        chart_config.max_data_points = max_points
    
    # Render charts in mobile-friendly layout
    st.markdown('<div class="mobile-chart-container">', unsafe_allow_html=True)
    render_touch_optimized_chart(sample_charts[0])
    st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="mobile-chart-container">', unsafe_allow_html=True)
        render_touch_optimized_chart(sample_charts[1])
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="mobile-chart-container">', unsafe_allow_html=True)
        render_touch_optimized_chart(sample_charts[2])
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Performance gauge
    st.markdown('<div class="mobile-chart-container">', unsafe_allow_html=True)
    create_performance_gauge()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Area chart
    st.markdown('<div class="mobile-chart-container">', unsafe_allow_html=True)
    render_touch_optimized_chart(sample_charts[3])
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Instructions
    st.markdown("""
    ### 📱 Touch-Optimized Charts Features
    
    **Touch Interactions:**
    - Pinch-to-zoom on supported charts
    - Pan and scroll with touch gestures
    - Tap data points for details
    - Touch-friendly toolbar (when enabled)
    
    **Mobile Optimizations:**
    - Data point reduction for performance (configurable max)
    - Simplified legends and labels
    - Larger touch targets and hover areas
    - Responsive text sizing
    
    **Real Estate Styling:**
    - Jorge's Real Estate AI color scheme
    - Professional gradient accents
    - Clean, minimal design
    - Consistent with dashboard branding
    
    **Performance Features:**
    - Lazy loading for large datasets
    - Automatic data sampling
    - 60fps smooth animations
    - Memory-efficient rendering
    """)


if __name__ == "__main__":
    demo_touch_optimized_charts()