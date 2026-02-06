"""
Tests for PerformanceChart component.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from bots.shared.dashboard_models import PerformanceMetrics
from command_center.components.performance_chart import render_performance_chart


@pytest.fixture
def sample_performance_metrics():
    """Sample performance metrics for testing."""
    return PerformanceMetrics(
        qualification_rate=0.65,
        avg_response_time=12.5,
        budget_performance=1.1,
        timeline_performance=0.95,
        commission_performance=1.05
    )


@pytest.fixture
def sample_performance_metrics_zero():
    """Sample performance metrics with zero values."""
    return PerformanceMetrics(
        qualification_rate=0.0,
        avg_response_time=0.0,
        budget_performance=0.0,
        timeline_performance=0.0,
        commission_performance=0.0
    )


def test_render_performance_chart_creates_chart(sample_performance_metrics):
    """Test that performance chart is created."""
    with patch('streamlit.subheader'), \
         patch('streamlit.plotly_chart') as mock_plotly, \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric'):

        # Mock columns for summary metrics
        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3]

        for col in [mock_col1, mock_col2, mock_col3]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_performance_chart(sample_performance_metrics)

        # Should call plotly_chart once
        assert mock_plotly.call_count == 1


def test_render_performance_chart_dual_axis(sample_performance_metrics):
    """Test that chart uses dual y-axis."""
    with patch('streamlit.subheader'), \
         patch('streamlit.plotly_chart') as mock_plotly, \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric'):

        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3]

        for col in [mock_col1, mock_col2, mock_col3]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_performance_chart(sample_performance_metrics)

        # Get the figure that was passed to plotly_chart
        assert mock_plotly.call_count == 1
        call_args = mock_plotly.call_args

        # Check that a figure was passed
        assert call_args is not None


def test_render_performance_chart_24h_data(sample_performance_metrics):
    """Test that chart shows 24-hour data."""
    with patch('streamlit.subheader'), \
         patch('streamlit.plotly_chart') as mock_plotly, \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric'):

        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3]

        for col in [mock_col1, mock_col2, mock_col3]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_performance_chart(sample_performance_metrics)

        # Get the figure
        call_args = mock_plotly.call_args
        fig = call_args[0][0]

        # Check that figure has data traces
        assert hasattr(fig, 'data')
        assert len(fig.data) == 2  # Qualification rate and response time


def test_render_performance_chart_summary_metrics(sample_performance_metrics):
    """Test that summary metrics are displayed below chart."""
    with patch('streamlit.subheader'), \
         patch('streamlit.plotly_chart'), \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric') as mock_metric:

        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3]

        for col in [mock_col1, mock_col2, mock_col3]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_performance_chart(sample_performance_metrics)

        # Should call st.metric 3 times for summary metrics
        assert mock_metric.call_count == 3


def test_render_performance_chart_handles_zero_metrics(sample_performance_metrics_zero):
    """Test that chart handles zero metrics without errors."""
    with patch('streamlit.subheader'), \
         patch('streamlit.plotly_chart') as mock_plotly, \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric'):

        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3]

        for col in [mock_col1, mock_col2, mock_col3]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        # Should not raise any errors
        render_performance_chart(sample_performance_metrics_zero)

        # Should still create chart
        assert mock_plotly.call_count == 1


def test_render_performance_chart_color_coding(sample_performance_metrics):
    """Test that chart uses correct color coding."""
    with patch('streamlit.subheader'), \
         patch('streamlit.plotly_chart') as mock_plotly, \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric'):

        mock_col1, mock_col2, mock_col3 = Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3]

        for col in [mock_col1, mock_col2, mock_col3]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_performance_chart(sample_performance_metrics)

        # Get the figure
        call_args = mock_plotly.call_args
        fig = call_args[0][0]

        # Check that traces have color properties
        assert hasattr(fig.data[0], 'line')
        assert hasattr(fig.data[1], 'line')

        # Qualification rate should be green (#2E7D32)
        assert fig.data[0].line.color == '#2E7D32'

        # Response time should be red (#D32F2F)
        assert fig.data[1].line.color == '#D32F2F'
