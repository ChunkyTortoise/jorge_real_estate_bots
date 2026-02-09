"""
Tests for HeroMetricsCard component.
"""
from unittest.mock import Mock, patch

import pytest

from bots.shared.dashboard_models import HeroMetrics
from command_center.components.hero_metrics_card import render_hero_metrics


@pytest.fixture
def sample_hero_metrics():
    """Sample hero metrics for testing."""
    return HeroMetrics(
        active_conversations=42,
        active_conversations_change=5,
        qualification_rate=0.65,
        qualification_rate_change=0.05,
        avg_response_time_minutes=12.5,
        response_time_change=-1.2,
        hot_leads_count=8,
        hot_leads_change=2
    )


@pytest.fixture
def sample_hero_metrics_zero():
    """Sample hero metrics with zero values for testing."""
    return HeroMetrics(
        active_conversations=0,
        active_conversations_change=0,
        qualification_rate=0.0,
        qualification_rate_change=0.0,
        avg_response_time_minutes=0.0,
        response_time_change=0.0,
        hot_leads_count=0,
        hot_leads_change=0
    )


def test_render_hero_metrics_displays_all_metrics(sample_hero_metrics):
    """Test that all 4 metrics are displayed."""
    with patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric') as mock_metric:

        # Mock 4 columns
        mock_col1, mock_col2, mock_col3, mock_col4 = Mock(), Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3, mock_col4]

        # Mock column __enter__ and __exit__ for context manager
        for col in [mock_col1, mock_col2, mock_col3, mock_col4]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_hero_metrics(sample_hero_metrics)

        # Should create 4 columns
        mock_columns.assert_called_once_with(4)

        # Should call st.metric 4 times
        assert mock_metric.call_count == 4


def test_render_hero_metrics_formats_percentage(sample_hero_metrics):
    """Test qualification rate formatted as percentage."""
    with patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric') as mock_metric:

        mock_col1, mock_col2, mock_col3, mock_col4 = Mock(), Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3, mock_col4]

        for col in [mock_col1, mock_col2, mock_col3, mock_col4]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_hero_metrics(sample_hero_metrics)

        # Find the qualification rate metric call
        calls = [str(call) for call in mock_metric.call_args_list]
        qual_rate_call = [c for c in calls if 'Qualification Rate' in c]

        assert len(qual_rate_call) == 1
        assert '65.0%' in qual_rate_call[0]


def test_render_hero_metrics_shows_deltas(sample_hero_metrics):
    """Test that delta indicators are shown for changes."""
    with patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric') as mock_metric:

        mock_col1, mock_col2, mock_col3, mock_col4 = Mock(), Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3, mock_col4]

        for col in [mock_col1, mock_col2, mock_col3, mock_col4]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_hero_metrics(sample_hero_metrics)

        # Check that delta is passed to metrics
        for call in mock_metric.call_args_list:
            if 'delta' in call.kwargs:
                # Delta should be present
                assert call.kwargs['delta'] is not None or call.kwargs['delta'] == 0


def test_render_hero_metrics_inverse_color_response_time(sample_hero_metrics):
    """Test that response time uses inverse delta color (lower is better)."""
    with patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric') as mock_metric:

        mock_col1, mock_col2, mock_col3, mock_col4 = Mock(), Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3, mock_col4]

        for col in [mock_col1, mock_col2, mock_col3, mock_col4]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        render_hero_metrics(sample_hero_metrics)

        # Find response time metric call
        response_time_calls = [call for call in mock_metric.call_args_list if 'Avg Response Time' in str(call)]

        assert len(response_time_calls) == 1
        # Check that delta_color='inverse' is set
        assert 'delta_color' in response_time_calls[0].kwargs
        assert response_time_calls[0].kwargs['delta_color'] == 'inverse'


def test_render_hero_metrics_handles_zero_values(sample_hero_metrics_zero):
    """Test that component handles zero values correctly."""
    with patch('streamlit.columns') as mock_columns, \
         patch('streamlit.metric') as mock_metric:

        mock_col1, mock_col2, mock_col3, mock_col4 = Mock(), Mock(), Mock(), Mock()
        mock_columns.return_value = [mock_col1, mock_col2, mock_col3, mock_col4]

        for col in [mock_col1, mock_col2, mock_col3, mock_col4]:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)

        # Should not raise any errors
        render_hero_metrics(sample_hero_metrics_zero)

        # Should still call st.metric 4 times
        assert mock_metric.call_count == 4
