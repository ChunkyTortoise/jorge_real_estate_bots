"""
Real-Time Activity Feed Component for Jorge Real Estate AI Dashboard

Provides live streaming of all system events with:
- WebSocket connection for real-time updates
- HTTP polling fallback for Streamlit limitations
- Event filtering by type, contact, time range
- Auto-scroll and export functionality
- Connection status monitoring
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time
from io import StringIO
from urllib.parse import quote

from bots.shared.logger import get_logger

logger = get_logger(__name__)


class ActivityFeed:
    """
    Real-time activity feed component for Jorge's dashboard.

    Features:
    - JavaScript WebSocket client for real-time events
    - HTTP polling fallback for reliability
    - Event filtering and search
    - Export functionality
    - Auto-scroll to latest events
    - Connection status monitoring
    """

    def __init__(self,
                 websocket_url: str = "ws://localhost:8001/ws/dashboard",
                 api_base_url: str = "http://localhost:8001"):
        self.websocket_url = websocket_url
        self.api_base_url = api_base_url
        self.max_events = 100

        # Initialize session state
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize Streamlit session state for events and connection"""
        if 'activity_events' not in st.session_state:
            st.session_state.activity_events = []

        if 'last_event_id' not in st.session_state:
            st.session_state.last_event_id = None

        if 'websocket_connected' not in st.session_state:
            st.session_state.websocket_connected = False

        if 'last_poll_time' not in st.session_state:
            st.session_state.last_poll_time = datetime.now()

        if 'activity_feed_client_id' not in st.session_state:
            st.session_state.activity_feed_client_id = f"dashboard_{int(time.time())}"

    def render(self):
        """Render the complete activity feed component"""
        st.subheader("📊 Real-Time Activity Feed")

        # Connection status and controls
        self._render_controls()

        # WebSocket client (JavaScript)
        self._render_websocket_client()

        # Polling fallback
        self._handle_polling_fallback()

        # Event list display
        self._render_event_list()

    def _render_controls(self):
        """Render activity feed controls and filters"""
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

        with col1:
            # Connection status
            if st.session_state.websocket_connected:
                st.success("🟢 Live Connected")
            else:
                st.warning("🟡 Polling Mode")

        with col2:
            # Auto-scroll toggle
            auto_scroll = st.checkbox("Auto-scroll", value=True,
                                    help="Automatically scroll to latest events")
            st.session_state.auto_scroll_enabled = auto_scroll

        with col3:
            # Refresh button for manual polling
            if st.button("🔄 Refresh Events"):
                self._manual_refresh()

        with col4:
            # Export button
            if st.button("📥 Export Events"):
                self._export_events()

        # Event filters
        st.markdown("**Filters:**")
        filter_col1, filter_col2, filter_col3 = st.columns([3, 3, 2])

        with filter_col1:
            event_types = st.multiselect(
                "Event Types",
                ["lead", "ghl", "cache", "system"],
                default=["lead", "ghl"],
                help="Filter events by category"
            )
            st.session_state.event_type_filter = event_types

        with filter_col2:
            search_query = st.text_input(
                "Search Contact ID",
                placeholder="Enter contact ID...",
                help="Search events for specific contact"
            )
            st.session_state.search_query = search_query.strip()

        with filter_col3:
            time_range = st.selectbox(
                "Time Range",
                ["Last 5 min", "Last 15 min", "Last 30 min", "Last 1 hour"],
                index=1,
                help="Filter events by time range"
            )
            st.session_state.time_range = time_range

    def _render_websocket_client(self):
        """Inject JavaScript WebSocket client for real-time updates"""
        token = st.session_state.get("auth_token")
        token_param = f"&token={quote(token)}" if token else ""
        websocket_js = f"""
        <script>
        // WebSocket connection for real-time events
        let ws = null;
        let reconnectInterval = null;
        let isConnected = false;

        const clientId = '{st.session_state.activity_feed_client_id}';
        const wsUrl = '{self.websocket_url}?client_id=' + clientId + '{token_param}';

        function connectWebSocket() {{
            try {{
                ws = new WebSocket(wsUrl);

                ws.onopen = function(event) {{
                    console.log('WebSocket connected');
                    isConnected = true;

                    // Notify Streamlit of connection status
                    window.parent.postMessage({{
                        type: 'websocket_status',
                        connected: true
                    }}, '*');

                    // Clear reconnect interval
                    if (reconnectInterval) {{
                        clearInterval(reconnectInterval);
                        reconnectInterval = null;
                    }}
                }};

                ws.onmessage = function(event) {{
                    try {{
                        const eventData = JSON.parse(event.data);

                        // Ignore heartbeat events
                        if (eventData.event_type === 'heartbeat') {{
                            return;
                        }}

                        // Send event to Streamlit
                        window.parent.postMessage({{
                            type: 'new_event',
                            event: eventData
                        }}, '*');

                    }} catch (error) {{
                        console.error('Error parsing WebSocket message:', error);
                    }}
                }};

                ws.onclose = function(event) {{
                    console.log('WebSocket disconnected');
                    isConnected = false;

                    // Notify Streamlit of disconnection
                    window.parent.postMessage({{
                        type: 'websocket_status',
                        connected: false
                    }}, '*');

                    // Start reconnection attempts
                    if (!reconnectInterval) {{
                        reconnectInterval = setInterval(connectWebSocket, 5000);
                    }}
                }};

                ws.onerror = function(error) {{
                    console.error('WebSocket error:', error);
                }};

            }} catch (error) {{
                console.error('Failed to connect WebSocket:', error);

                // Try reconnection
                if (!reconnectInterval) {{
                    reconnectInterval = setInterval(connectWebSocket, 5000);
                }}
            }}
        }}

        // Send periodic pings to keep connection alive
        setInterval(function() {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send('ping');
            }}
        }}, 30000);

        // Initialize connection
        connectWebSocket();
        </script>

        <div id="websocket-status" style="display: none;">
            WebSocket client active
        </div>
        """

        # Render WebSocket client (hidden)
        components.html(websocket_js, height=0)

    def _handle_polling_fallback(self):
        """Handle HTTP polling fallback when WebSocket is not available"""
        current_time = datetime.now()

        # Poll every 2 seconds if not connected via WebSocket
        if not st.session_state.websocket_connected:
            time_since_last_poll = (current_time - st.session_state.last_poll_time).total_seconds()

            if time_since_last_poll >= 2.0:  # Poll every 2 seconds
                self._poll_recent_events()
                st.session_state.last_poll_time = current_time

    def _poll_recent_events(self):
        """Poll for recent events via HTTP API"""
        try:
            # Get time range for polling
            minutes_back = self._get_time_range_minutes(st.session_state.get('time_range', 'Last 15 min'))

            # Build API request
            params = {
                'since_minutes': minutes_back,
                'limit': self.max_events
            }

            # Add event type filter
            if st.session_state.get('event_type_filter'):
                event_types = []
                for category in st.session_state.event_type_filter:
                    event_types.extend([
                        f"{category}.analyzed", f"{category}.scored", f"{category}.cache_hit",
                        f"{category}.error", f"{category}.updated", f"{category}.sent"
                    ])
                params['event_types'] = ','.join(event_types)

            # Make API request
            headers = {}
            token = st.session_state.get("auth_token")
            if token:
                headers["Authorization"] = f"Bearer {token}"

            response = requests.get(
                f"{self.api_base_url}/api/events/recent",
                params=params,
                headers=headers,
                timeout=3
            )

            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])

                # Update events in session state
                self._update_events(events)

                logger.debug(f"Polled {len(events)} events via HTTP")
            else:
                logger.warning(f"Events polling failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Events polling error: {e}")

    def _update_events(self, new_events: List[Dict]):
        """Update events in session state, avoiding duplicates"""
        if not new_events:
            return

        current_events = st.session_state.activity_events

        # Add new events, avoiding duplicates
        for event in new_events:
            event_id = event.get('event_id')

            # Check if event already exists
            if not any(e.get('event_id') == event_id for e in current_events):
                current_events.insert(0, event)  # Add to beginning (newest first)

        # Sort by timestamp (newest first)
        current_events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        # Keep only latest N events
        st.session_state.activity_events = current_events[:self.max_events]

    def _manual_refresh(self):
        """Manual refresh of events"""
        st.session_state.last_poll_time = datetime.now() - timedelta(seconds=10)
        self._poll_recent_events()
        st.rerun()

    def _render_event_list(self):
        """Render the list of activity events"""
        # Get filtered events
        filtered_events = self._get_filtered_events()

        if not filtered_events:
            st.info("No events found. Events will appear here as they occur.")
            return

        # Display event count
        st.caption(f"Showing {len(filtered_events)} events")

        # Container for events
        events_container = st.container()

        with events_container:
            # Render events
            for i, event in enumerate(filtered_events[:50]):  # Limit to 50 displayed events
                self._render_single_event(event, i)

        # Auto-scroll trigger
        if st.session_state.get('auto_scroll_enabled', True) and filtered_events:
            # This will cause the page to scroll to the bottom
            st.markdown('<div id="bottom"></div>', unsafe_allow_html=True)

    def _render_single_event(self, event: Dict, index: int):
        """Render a single event in the activity feed"""
        event_type = event.get('event_type', 'unknown')
        timestamp = event.get('timestamp', '')
        source = event.get('source', 'unknown')
        payload = event.get('payload', {})

        # Event icon and color based on type
        icon, color = self._get_event_icon_color(event_type)

        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime('%H:%M:%S')
        except:
            time_str = timestamp[:8] if len(timestamp) >= 8 else timestamp

        # Event message
        message = self._format_event_message(event_type, payload)

        # Create expandable event card
        with st.expander(f"{icon} {time_str} - {message}", expanded=False):
            col1, col2 = st.columns([1, 3])

            with col1:
                st.caption(f"**Type:** {event_type}")
                st.caption(f"**Source:** {source}")
                st.caption(f"**Time:** {timestamp}")

            with col2:
                st.caption("**Event Data:**")
                if payload:
                    # Display payload in a nice format
                    for key, value in payload.items():
                        if key not in ['email', 'phone', 'ssn']:  # Hide sensitive data
                            st.caption(f"• **{key}:** {value}")
                else:
                    st.caption("No additional data")

    def _get_event_icon_color(self, event_type: str) -> tuple:
        """Get icon and color for event type"""
        if event_type.startswith('lead.'):
            if 'error' in event_type:
                return '🔴', 'red'
            elif 'hot_detected' in event_type:
                return '🔥', 'orange'
            elif 'analyzed' in event_type:
                return '🔵', 'blue'
            elif 'cache_hit' in event_type:
                return '⚡', 'green'
            else:
                return '🔵', 'blue'

        elif event_type.startswith('ghl.'):
            if 'error' in event_type:
                return '🔴', 'red'
            else:
                return '🟢', 'green'

        elif event_type.startswith('cache.'):
            if 'hit' in event_type:
                return '💨', 'green'
            elif 'miss' in event_type:
                return '⏳', 'orange'
            else:
                return '💾', 'blue'

        elif event_type.startswith('system.'):
            return '⚪', 'gray'

        return '•', 'gray'

    def _format_event_message(self, event_type: str, payload: Dict) -> str:
        """Format human-readable event message"""
        contact_id = payload.get('contact_id', 'Unknown')

        # Truncate contact ID for display
        display_contact_id = contact_id[:8] + '...' if len(contact_id) > 8 else contact_id

        if event_type == 'lead.analyzed':
            score = payload.get('score', 0)
            temp = payload.get('temperature', 'warm')
            temp_icon = '🔥' if temp == 'hot' else '🟡' if temp == 'warm' else '🔵'
            return f"Lead {display_contact_id} scored {score} ({temp_icon} {temp})"

        elif event_type == 'lead.hot_detected':
            score = payload.get('score', 0)
            return f"🔥 HOT LEAD {display_contact_id} (score: {score})"

        elif event_type == 'lead.cache_hit':
            time_ms = payload.get('response_time_ms', 0)
            return f"⚡ Cache hit for {display_contact_id} ({time_ms:.1f}ms)"

        elif event_type == 'ghl.tag_added':
            tag = payload.get('tag', 'unknown')
            return f"🏷️ Tag '{tag}' added to {display_contact_id}"

        elif event_type == 'ghl.message_sent':
            msg_type = payload.get('message_type', 'unknown')
            return f"📬 {msg_type.upper()} sent to {display_contact_id}"

        elif event_type == 'cache.hit':
            time_ms = payload.get('response_time_ms', 0)
            return f"💨 Cache hit ({time_ms:.1f}ms)"

        elif event_type == 'cache.miss':
            return f"⏳ Cache miss - computing fresh data"

        elif event_type.endswith('error'):
            error_msg = payload.get('error_message', 'Unknown error')
            return f"❌ Error: {error_msg[:50]}..."

        else:
            return f"{event_type.replace('.', ' ').title()}"

    def _get_filtered_events(self) -> List[Dict]:
        """Get events filtered by current filter settings"""
        all_events = st.session_state.activity_events

        if not all_events:
            return []

        filtered = all_events.copy()

        # Filter by event type categories
        if st.session_state.get('event_type_filter'):
            type_filter = st.session_state.event_type_filter
            filtered = [
                event for event in filtered
                if any(event.get('event_type', '').startswith(f"{cat}.") for cat in type_filter)
            ]

        # Filter by search query (contact ID)
        if st.session_state.get('search_query'):
            query = st.session_state.search_query.lower()
            filtered = [
                event for event in filtered
                if query in str(event.get('payload', {}).get('contact_id', '')).lower()
                or query in event.get('event_type', '').lower()
            ]

        # Filter by time range
        time_range = st.session_state.get('time_range', 'Last 15 min')
        minutes_back = self._get_time_range_minutes(time_range)
        cutoff_time = datetime.now() - timedelta(minutes=minutes_back)

        filtered = [
            event for event in filtered
            if self._parse_event_time(event.get('timestamp', '')) >= cutoff_time
        ]

        return filtered

    def _get_time_range_minutes(self, time_range: str) -> int:
        """Convert time range string to minutes"""
        if 'hour' in time_range:
            return 60
        elif '30 min' in time_range:
            return 30
        elif '15 min' in time_range:
            return 15
        elif '5 min' in time_range:
            return 5
        else:
            return 15  # Default

    def _parse_event_time(self, timestamp_str: str) -> datetime:
        """Parse event timestamp string to datetime"""
        try:
            # Handle ISO format with or without timezone
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'

            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            # Fallback to current time if parsing fails
            return datetime.now()

    def _export_events(self):
        """Export filtered events to CSV"""
        filtered_events = self._get_filtered_events()

        if not filtered_events:
            st.warning("No events to export")
            return

        # Convert to DataFrame
        export_data = []
        for event in filtered_events:
            payload = event.get('payload', {})

            row = {
                'Timestamp': event.get('timestamp', ''),
                'Event Type': event.get('event_type', ''),
                'Source': event.get('source', ''),
                'Contact ID': payload.get('contact_id', ''),
                'Details': self._format_event_message(event.get('event_type', ''), payload)
            }

            # Add specific payload fields
            for key, value in payload.items():
                if key not in ['contact_id', 'email', 'phone', 'ssn']:  # Exclude sensitive data
                    row[f"payload_{key}"] = value

            export_data.append(row)

        df = pd.DataFrame(export_data)

        # Generate CSV
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue()

        # Provide download button
        st.download_button(
            label="📥 Download Events CSV",
            data=csv_data,
            file_name=f"jorge_activity_feed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
