"""
Active Conversations Table Component for Jorge Real Estate AI Dashboard.

Displays paginated, filterable list of active seller conversations.
"""
import streamlit as st
from typing import List
from bots.shared.dashboard_models import ConversationState, Temperature
from datetime import datetime


def render_active_conversations(
    conversations: List[ConversationState],
    page: int = 1,
    page_size: int = 10
) -> None:
    """
    Render paginated table of active conversations.

    Args:
        conversations: List of ConversationState from DashboardDataService
        page: Current page number (1-indexed)
        page_size: Number of conversations per page
    """
    # Temperature filter
    st.subheader("Active Conversations")

    col1, col2 = st.columns([3, 1])
    with col1:
        search = st.text_input("Search by contact name", key="search_conversations")
    with col2:
        temp_filter = st.selectbox(
            "Filter by Temperature",
            options=["All", "HOT", "WARM", "COLD"],
            key="temp_filter"
        )

    # Apply filters
    filtered = conversations
    if search:
        filtered = [c for c in filtered if search.lower() in c.seller_name.lower()]
    if temp_filter != "All":
        filtered = [c for c in filtered if c.temperature.value.upper() == temp_filter]

    # Pagination
    total = len(filtered)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_conversations = filtered[start_idx:end_idx]

    # Table header
    st.markdown(f"**Showing {start_idx + 1}-{min(end_idx, total)} of {total} conversations**")

    # Render table
    for conv in page_conversations:
        with st.expander(f"**{conv.seller_name}** - {_format_temperature(conv.temperature)} - Stage {conv.stage.value}"):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.write(f"**Contact ID**: {conv.contact_id}")
                st.write(f"**Stage**: {conv.stage.value}")

            with col2:
                st.write(f"**Temperature**: {_format_temperature(conv.temperature)}")
                st.write(f"**Qualified**: {'Yes' if conv.is_qualified else 'No'}")

            with col3:
                st.write(f"**Questions**: {conv.questions_answered}/{conv.current_question}")
                st.write(f"**Started**: {conv.conversation_started.strftime('%Y-%m-%d %H:%M')}")

            with col4:
                st.write(f"**Last Activity**: {conv.last_activity.strftime('%Y-%m-%d %H:%M')}")
                minutes_ago = (datetime.now() - conv.last_activity).total_seconds() / 60
                st.write(f"**({minutes_ago:.0f}m ago)**")

    # Pagination controls
    if total > page_size:
        total_pages = (total + page_size - 1) // page_size
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            if page > 1:
                if st.button("← Previous"):
                    st.session_state.page = page - 1
                    st.rerun()

        with col2:
            st.write(f"Page {page} of {total_pages}")

        with col3:
            if page < total_pages:
                if st.button("Next →"):
                    st.session_state.page = page + 1
                    st.rerun()


def _format_temperature(temp: Temperature) -> str:
    """Format temperature with emoji."""
    emoji_map = {
        Temperature.HOT: "🔥",
        Temperature.WARM: "⚡",
        Temperature.COLD: "❄️"
    }
    return f"{emoji_map.get(temp, '')} {temp.value.upper()}"
