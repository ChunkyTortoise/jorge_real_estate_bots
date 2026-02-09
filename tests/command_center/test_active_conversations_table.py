"""
Tests for ActiveConversationsTable component.
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from bots.shared.dashboard_models import ConversationStage, ConversationState, Temperature
from command_center.components.active_conversations_table import _format_temperature, render_active_conversations


@pytest.fixture
def sample_conversations():
    """Sample conversations for testing."""
    now = datetime.now()
    return [
        ConversationState(
            contact_id="contact_1",
            seller_name="John Doe",
            stage=ConversationStage.Q2,
            temperature=Temperature.HOT,
            current_question=2,
            questions_answered=2,
            last_activity=now - timedelta(minutes=5),
            conversation_started=now - timedelta(hours=1),
            is_qualified=False
        ),
        ConversationState(
            contact_id="contact_2",
            seller_name="Jane Smith",
            stage=ConversationStage.Q3,
            temperature=Temperature.WARM,
            current_question=3,
            questions_answered=3,
            last_activity=now - timedelta(minutes=30),
            conversation_started=now - timedelta(hours=2),
            is_qualified=False
        ),
        ConversationState(
            contact_id="contact_3",
            seller_name="Bob Johnson",
            stage=ConversationStage.QUALIFIED,
            temperature=Temperature.HOT,
            current_question=4,
            questions_answered=4,
            last_activity=now - timedelta(hours=1),
            conversation_started=now - timedelta(hours=3),
            is_qualified=True
        ),
    ]


def create_column_mock():
    """Helper to create mock columns with proper context manager support."""
    def columns_side_effect(arg):
        if isinstance(arg, list):
            cols = [Mock() for _ in arg]
        else:
            cols = [Mock() for _ in range(arg)]

        for col in cols:
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=None)
        return cols

    return columns_side_effect


def test_render_active_conversations_displays_all_conversations(sample_conversations):
    """Test that all conversations are displayed."""
    with patch('streamlit.subheader'), \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.text_input') as mock_text_input, \
         patch('streamlit.selectbox') as mock_selectbox, \
         patch('streamlit.markdown'), \
         patch('streamlit.expander') as mock_expander, \
         patch('streamlit.write'):

        # Mock search and filter inputs
        mock_text_input.return_value = ""
        mock_selectbox.return_value = "All"
        mock_columns.side_effect = create_column_mock()

        # Mock expander
        mock_expander.return_value.__enter__ = Mock()
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        render_active_conversations(sample_conversations, page=1, page_size=10)

        # Should call expander 3 times (one for each conversation)
        assert mock_expander.call_count == 3


def test_render_active_conversations_pagination_works(sample_conversations):
    """Test pagination logic."""
    with patch('streamlit.subheader'), \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.text_input') as mock_text_input, \
         patch('streamlit.selectbox') as mock_selectbox, \
         patch('streamlit.markdown'), \
         patch('streamlit.expander') as mock_expander, \
         patch('streamlit.button') as mock_button, \
         patch('streamlit.write'):

        mock_text_input.return_value = ""
        mock_selectbox.return_value = "All"
        mock_button.return_value = False
        mock_columns.side_effect = create_column_mock()

        mock_expander.return_value.__enter__ = Mock()
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        # Test page 1 with page_size=2 (should show 2 conversations)
        render_active_conversations(sample_conversations, page=1, page_size=2)

        # Should show 2 conversations on page 1
        assert mock_expander.call_count == 2


def test_render_active_conversations_search_filters(sample_conversations):
    """Test search filtering by name."""
    with patch('streamlit.subheader'), \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.text_input') as mock_text_input, \
         patch('streamlit.selectbox') as mock_selectbox, \
         patch('streamlit.markdown'), \
         patch('streamlit.expander') as mock_expander, \
         patch('streamlit.write'):

        # Mock search for "John"
        mock_text_input.return_value = "John"
        mock_selectbox.return_value = "All"
        mock_columns.side_effect = create_column_mock()

        mock_expander.return_value.__enter__ = Mock()
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        render_active_conversations(sample_conversations, page=1, page_size=10)

        # Should show 2 conversations (John Doe and Bob Johnson)
        assert mock_expander.call_count == 2


def test_render_active_conversations_temperature_filter(sample_conversations):
    """Test temperature filtering."""
    with patch('streamlit.subheader'), \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.text_input') as mock_text_input, \
         patch('streamlit.selectbox') as mock_selectbox, \
         patch('streamlit.markdown'), \
         patch('streamlit.expander') as mock_expander, \
         patch('streamlit.write'):

        mock_text_input.return_value = ""
        # Filter for HOT leads only
        mock_selectbox.return_value = "HOT"
        mock_columns.side_effect = create_column_mock()

        mock_expander.return_value.__enter__ = Mock()
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        render_active_conversations(sample_conversations, page=1, page_size=10)

        # Should show 2 HOT conversations
        assert mock_expander.call_count == 2


def test_render_active_conversations_shows_time_ago(sample_conversations):
    """Test that time-since-last-activity is calculated."""
    with patch('streamlit.subheader'), \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.text_input') as mock_text_input, \
         patch('streamlit.selectbox') as mock_selectbox, \
         patch('streamlit.markdown'), \
         patch('streamlit.expander') as mock_expander, \
         patch('streamlit.write') as mock_write:

        mock_text_input.return_value = ""
        mock_selectbox.return_value = "All"
        mock_columns.side_effect = create_column_mock()

        mock_expander.return_value.__enter__ = Mock()
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        render_active_conversations(sample_conversations, page=1, page_size=10)

        # Check that write was called with time ago
        write_calls = [str(call) for call in mock_write.call_args_list]
        time_ago_calls = [c for c in write_calls if 'm ago' in c]

        # Should have time ago for each conversation
        assert len(time_ago_calls) >= 3


def test_render_active_conversations_expandable_details(sample_conversations):
    """Test that expandable rows show conversation details."""
    with patch('streamlit.subheader'), \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.text_input') as mock_text_input, \
         patch('streamlit.selectbox') as mock_selectbox, \
         patch('streamlit.markdown'), \
         patch('streamlit.expander') as mock_expander, \
         patch('streamlit.write') as mock_write:

        mock_text_input.return_value = ""
        mock_selectbox.return_value = "All"
        mock_columns.side_effect = create_column_mock()

        mock_expander.return_value.__enter__ = Mock()
        mock_expander.return_value.__exit__ = Mock(return_value=None)

        render_active_conversations(sample_conversations, page=1, page_size=10)

        # Check that write was called with conversation details
        write_calls = [str(call) for call in mock_write.call_args_list]

        # Should show contact ID, stage, temperature, questions, etc.
        assert any('Contact ID' in c for c in write_calls)
        assert any('Stage' in c for c in write_calls)
        assert any('Temperature' in c for c in write_calls)


def test_render_active_conversations_handles_empty_list():
    """Test that component handles empty conversation list."""
    with patch('streamlit.subheader'), \
         patch('streamlit.columns') as mock_columns, \
         patch('streamlit.text_input') as mock_text_input, \
         patch('streamlit.selectbox') as mock_selectbox, \
         patch('streamlit.markdown'), \
         patch('streamlit.expander') as mock_expander:

        mock_text_input.return_value = ""
        mock_selectbox.return_value = "All"
        mock_columns.side_effect = create_column_mock()

        # Should not raise any errors
        render_active_conversations([], page=1, page_size=10)

        # Should not call expander for empty list
        assert mock_expander.call_count == 0


def test_format_temperature_returns_emoji():
    """Test that temperature formatting includes emojis."""
    assert "🔥" in _format_temperature(Temperature.HOT)
    assert "⚡" in _format_temperature(Temperature.WARM)
    assert "❄️" in _format_temperature(Temperature.COLD)

    assert "HOT" in _format_temperature(Temperature.HOT)
    assert "WARM" in _format_temperature(Temperature.WARM)
    assert "COLD" in _format_temperature(Temperature.COLD)
