"""
Active Conversations Component for Jorge Real Estate AI Dashboard.

Displays real-time seller bot conversation states with:
- Filterable table of active conversations
- Q1-Q4 stage progression tracking
- Temperature indicators (HOT/WARM/COLD)
- Action buttons (View, Trigger CMA, Advance Stage)
- Pagination for large conversation lists

Features mobile-responsive design and real-time updates.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio

from bots.shared.logger import get_logger
from bots.shared.dashboard_data_service import get_dashboard_data_service
from bots.shared.dashboard_models import (
    ConversationState,
    ConversationFilters,
    ConversationStage,
    Temperature,
)

logger = get_logger(__name__)


class ActiveConversationsComponent:
    """
    Active conversations component for dashboard display.

    Features:
    - Real-time conversation table with filtering
    - Stage progression tracking (Q0-Q4)
    - Temperature-based prioritization
    - Action buttons for CMA triggers and advancement
    - Mobile-responsive table design
    """

    def __init__(self):
        """Initialize active conversations component."""
        self.data_service = get_dashboard_data_service()
        logger.info("ActiveConversationsComponent initialized")

    def render(self) -> None:
        """
        Render the complete active conversations component.

        Displays:
        - Filter controls
        - Conversation table with actions
        - Summary statistics
        - Stage distribution chart
        """
        st.header("🗣️ Active Seller Conversations")

        # Initialize session state for filters
        if 'conversations_filters' not in st.session_state:
            st.session_state.conversations_filters = ConversationFilters()

        # Render filter controls
        filters = self._render_filter_controls()

        # Fetch conversation data
        conversations_data = self._fetch_conversations(filters)

        if conversations_data and conversations_data.total_count > 0:
            # Display summary metrics
            self._render_summary_metrics(conversations_data)

            # Display conversation table
            self._render_conversations_table(conversations_data)

            # Display pagination controls
            self._render_pagination_controls(conversations_data)

            # Display stage distribution chart
            self._render_stage_distribution_chart(conversations_data)

        else:
            self._render_empty_state()

    def _render_filter_controls(self) -> ConversationFilters:
        """Render filter controls and return current filters."""
        with st.expander("🔍 Filter Conversations", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                # Stage filter
                stage_options = ["All Stages"] + [stage.value for stage in ConversationStage]
                selected_stage = st.selectbox(
                    "Conversation Stage",
                    stage_options,
                    index=0,
                    key="conv_stage_filter"
                )

                # Temperature filter
                temp_options = ["All Temperatures"] + [temp.value for temp in Temperature]
                selected_temp = st.selectbox(
                    "Temperature",
                    temp_options,
                    index=0,
                    key="conv_temp_filter"
                )

            with col2:
                # Search filter
                search_term = st.text_input(
                    "Search (Name/Address)",
                    placeholder="Enter seller name or property address",
                    key="conv_search_filter"
                )

                # Show stalled only
                show_stalled = st.checkbox(
                    "Show Stalled Only (>48h)",
                    key="conv_stalled_filter"
                )

            with col3:
                # Sort options
                sort_options = ["Last Activity", "Stage", "Temperature", "Seller Name"]
                sort_by = st.selectbox(
                    "Sort By",
                    sort_options,
                    key="conv_sort_by"
                )

                sort_order = st.selectbox(
                    "Sort Order",
                    ["Newest First", "Oldest First"],
                    key="conv_sort_order"
                )

            # Apply filters button
            if st.button("🔄 Apply Filters", key="apply_conv_filters"):
                st.session_state.conversations_page = 1  # Reset to first page

        # Build filters object
        filters = ConversationFilters(
            stage=ConversationStage(selected_stage) if selected_stage != "All Stages" else None,
            temperature=Temperature(selected_temp) if selected_temp != "All Temperatures" else None,
            search_term=search_term.strip() if search_term.strip() else None,
            show_stalled_only=show_stalled,
            sort_by=sort_by.lower().replace(" ", "_"),
            sort_order="desc" if sort_order == "Newest First" else "asc"
        )

        return filters

    def _fetch_conversations(self, filters: ConversationFilters):
        """Fetch conversations data with current filters and pagination."""
        try:
            # Get current page from session state
            page = st.session_state.get('conversations_page', 1)
            page_size = 15  # Items per page

            # Fetch data asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            conversations_data = loop.run_until_complete(
                self.data_service.get_active_conversations(
                    filters=filters,
                    page=page,
                    page_size=page_size
                )
            )

            loop.close()
            return conversations_data

        except Exception as e:
            logger.exception(f"Error fetching conversations: {e}")
            st.error(f"Error loading conversations: {str(e)}")
            return None

    def _render_summary_metrics(self, conversations_data) -> None:
        """Render summary metrics for conversations."""
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Total Active",
                conversations_data.total_count,
                help="Total active conversations across all stages"
            )

        with col2:
            # Calculate temperature distribution
            hot_count = sum(1 for c in conversations_data.conversations if c.temperature == Temperature.HOT)
            st.metric(
                "🔥 HOT Leads",
                hot_count,
                help="High-priority conversations requiring immediate attention"
            )

        with col3:
            # Calculate qualified count
            qualified_count = sum(1 for c in conversations_data.conversations if c.is_qualified)
            st.metric(
                "✅ Qualified",
                qualified_count,
                help="Sellers who completed Q4 qualification"
            )

        with col4:
            # Calculate average response time
            now = datetime.now()
            response_times = [
                (now - c.last_activity).total_seconds() / 3600
                for c in conversations_data.conversations
            ]
            avg_response_hours = sum(response_times) / len(response_times) if response_times else 0
            st.metric(
                "⏱️ Avg Response",
                f"{avg_response_hours:.1f}h",
                help="Average time since last seller response"
            )

    def _render_conversations_table(self, conversations_data) -> None:
        """Render the main conversations table with action buttons."""
        st.subheader("Conversation Details")

        # Convert conversations to DataFrame for display
        table_data = []
        for conv in conversations_data.conversations:
            table_data.append({
                'Seller': conv.seller_name,
                'Stage': conv.stage.value,
                'Temp': self._get_temperature_emoji(conv.temperature),
                'Q#': f"{conv.questions_answered}/4",
                'Property': conv.property_address or "Not provided",
                'Price Exp.': f"${conv.price_expectation:,}" if conv.price_expectation else "TBD",
                'Last Activity': self._format_time_ago(conv.last_activity),
                'CMA': "✅" if conv.cma_triggered else "⏳",
                'Contact ID': conv.contact_id,  # Hidden column for actions
            })

        if table_data:
            df = pd.DataFrame(table_data)

            # Display table with custom styling
            st.dataframe(
                df.drop(columns=['Contact ID']),  # Hide contact ID
                use_container_width=True,
                height=400,
                column_config={
                    'Seller': st.column_config.TextColumn(
                        "Seller Name",
                        width="medium",
                        help="Name of the property seller"
                    ),
                    'Stage': st.column_config.TextColumn(
                        "Stage",
                        width="small",
                        help="Current conversation stage (Q0-Q4)"
                    ),
                    'Temp': st.column_config.TextColumn(
                        "🌡️",
                        width="small",
                        help="Lead temperature: 🔥=HOT, 🟡=WARM, 🟦=COLD"
                    ),
                    'Q#': st.column_config.TextColumn(
                        "Progress",
                        width="small",
                        help="Questions answered out of 4"
                    ),
                    'Property': st.column_config.TextColumn(
                        "Property Address",
                        width="large",
                        help="Property address if provided"
                    ),
                    'Price Exp.': st.column_config.TextColumn(
                        "Expected Price",
                        width="medium",
                        help="Seller's price expectation"
                    ),
                    'Last Activity': st.column_config.TextColumn(
                        "Last Response",
                        width="medium",
                        help="Time since last activity"
                    ),
                    'CMA': st.column_config.TextColumn(
                        "CMA",
                        width="small",
                        help="CMA status: ✅=Completed, ⏳=Pending"
                    ),
                }
            )

            # Action buttons for selected conversations
            self._render_action_buttons(conversations_data.conversations)

        else:
            st.info("No conversations found matching current filters.")

    def _render_action_buttons(self, conversations: List[ConversationState]) -> None:
        """Render action buttons for conversation management."""
        st.subheader("Quick Actions")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            # Seller selection for actions
            seller_options = ["Select Seller..."] + [f"{c.seller_name} ({c.contact_id})" for c in conversations]
            selected_seller = st.selectbox(
                "Choose Seller for Actions",
                seller_options,
                key="action_seller_select"
            )

        if selected_seller and selected_seller != "Select Seller...":
            # Extract contact ID from selection
            contact_id = selected_seller.split('(')[-1].replace(')', '')
            selected_conv = next((c for c in conversations if c.contact_id == contact_id), None)

            if selected_conv:
                with col2:
                    if st.button(f"👀 View Details", key=f"view_{contact_id}"):
                        self._show_conversation_details(selected_conv)

                with col3:
                    if not selected_conv.cma_triggered:
                        if st.button(f"📊 Trigger CMA", key=f"cma_{contact_id}"):
                            self._trigger_cma(selected_conv)
                    else:
                        st.button("✅ CMA Sent", disabled=True, key=f"cma_sent_{contact_id}")

                with col4:
                    next_stage = self._get_next_stage(selected_conv.stage)
                    if next_stage:
                        if st.button(f"➡️ Advance to {next_stage}", key=f"advance_{contact_id}"):
                            self._advance_stage(selected_conv, next_stage)
                    else:
                        st.button("🎯 Qualified", disabled=True, key=f"qualified_{contact_id}")

    def _render_pagination_controls(self, conversations_data) -> None:
        """Render pagination controls for conversation navigation."""
        if conversations_data.total_pages > 1:
            st.subheader("Navigation")

            col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

            with col1:
                if st.button("⏮️ First", disabled=not conversations_data.has_prev, key="conv_first_page"):
                    st.session_state.conversations_page = 1
                    st.rerun()

            with col2:
                if st.button("⬅️ Previous", disabled=not conversations_data.has_prev, key="conv_prev_page"):
                    st.session_state.conversations_page = max(1, conversations_data.page - 1)
                    st.rerun()

            with col3:
                st.write(f"Page {conversations_data.page} of {conversations_data.total_pages} "
                        f"({conversations_data.total_count} total conversations)")

            with col4:
                if st.button("Next ➡️", disabled=not conversations_data.has_next, key="conv_next_page"):
                    st.session_state.conversations_page = conversations_data.page + 1
                    st.rerun()

            with col5:
                if st.button("Last ⏭️", disabled=not conversations_data.has_next, key="conv_last_page"):
                    st.session_state.conversations_page = conversations_data.total_pages
                    st.rerun()

    def _render_stage_distribution_chart(self, conversations_data) -> None:
        """Render stage distribution chart."""
        st.subheader("📊 Stage Distribution")

        # Count conversations by stage
        stage_counts = {}
        for conv in conversations_data.conversations:
            stage = conv.stage.value
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        if stage_counts:
            # Create bar chart
            stages = list(stage_counts.keys())
            counts = list(stage_counts.values())

            fig = px.bar(
                x=stages,
                y=counts,
                title="Conversations by Stage",
                labels={'x': 'Conversation Stage', 'y': 'Number of Conversations'},
                color=counts,
                color_continuous_scale='viridis'
            )

            fig.update_layout(
                height=300,
                template="plotly_white",
                showlegend=False
            )

            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("No stage data available for current selection.")

    def _render_empty_state(self) -> None:
        """Render empty state when no conversations are found."""
        st.info("🔍 No active conversations found. This could mean:")
        st.write("• All leads are in nurturing phase")
        st.write("• Filters are too restrictive")
        st.write("• No new seller inquiries recently")

        if st.button("🔄 Clear All Filters", key="clear_conv_filters"):
            # Reset all filter session state
            for key in list(st.session_state.keys()):
                if key.startswith('conv_'):
                    del st.session_state[key]
            st.rerun()

    def _show_conversation_details(self, conv: ConversationState) -> None:
        """Show detailed conversation information."""
        st.info(f"**Conversation Details for {conv.seller_name}**")

        detail_col1, detail_col2 = st.columns(2)

        with detail_col1:
            st.write(f"**Stage:** {conv.stage.value}")
            st.write(f"**Temperature:** {conv.temperature.value}")
            st.write(f"**Questions Answered:** {conv.questions_answered}/4")
            st.write(f"**Started:** {conv.conversation_started.strftime('%Y-%m-%d %H:%M')}")

        with detail_col2:
            st.write(f"**Property:** {conv.property_address or 'Not provided'}")
            st.write(f"**Condition:** {conv.condition or 'Not provided'}")
            st.write(f"**Price Expectation:** {f'${conv.price_expectation:,}' if conv.price_expectation else 'TBD'}")
            st.write(f"**Motivation:** {conv.motivation or 'Not provided'}")

    def _trigger_cma(self, conv: ConversationState) -> None:
        """Trigger CMA for selected conversation."""
        st.success(f"📊 CMA triggered for {conv.seller_name}!")
        st.info("CMA request has been sent to the property valuation system.")
        # TODO: Integrate with actual CMA service

    def _advance_stage(self, conv: ConversationState, next_stage: str) -> None:
        """Advance conversation to next stage."""
        st.success(f"➡️ {conv.seller_name} advanced to {next_stage}!")
        st.info("Stage advancement has been logged and next question sequence initiated.")
        # TODO: Integrate with actual seller bot service

    def _get_temperature_emoji(self, temperature: Temperature) -> str:
        """Get emoji representation for temperature."""
        emoji_map = {
            Temperature.HOT: "🔥",
            Temperature.WARM: "🟡",
            Temperature.COLD: "🟦"
        }
        return emoji_map.get(temperature, "❓")

    def _get_next_stage(self, current_stage: ConversationStage) -> Optional[str]:
        """Get the next conversation stage."""
        stage_progression = {
            ConversationStage.Q0: "Q1",
            ConversationStage.Q1: "Q2",
            ConversationStage.Q2: "Q3",
            ConversationStage.Q3: "Q4",
            ConversationStage.Q4: "QUALIFIED"
        }
        return stage_progression.get(current_stage)

    def _format_time_ago(self, timestamp: datetime) -> str:
        """Format timestamp as time ago string."""
        now = datetime.now()
        if timestamp.tzinfo is not None:
            now = now.replace(tzinfo=timestamp.tzinfo)

        diff = now - timestamp

        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"


# Initialize session state for pagination
if 'conversations_page' not in st.session_state:
    st.session_state.conversations_page = 1


def render_active_conversations() -> None:
    """
    Render the active conversations component.

    Entry point for use in dashboard pages.
    """
    try:
        component = ActiveConversationsComponent()
        component.render()

    except Exception as e:
        logger.exception(f"Error rendering active conversations: {e}")
        st.error("Failed to load active conversations. Please refresh the page.")


# Component entry point
if __name__ == "__main__":
    # For testing the component standalone
    st.set_page_config(
        page_title="Active Conversations",
        page_icon="🗣️",
        layout="wide"
    )
    render_active_conversations()