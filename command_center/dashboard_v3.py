"""
Jorge Real Estate AI - Dashboard V3
Consolidated command center with navigation and auth gating.
"""
import asyncio
import os
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any

import streamlit as st

from bots.shared.dashboard_data_service import DashboardDataService
from command_center.components.active_conversations import ActiveConversationsComponent
from command_center.components.active_conversations_table import render_active_conversations
from command_center.components.activity_feed import ActivityFeed
from command_center.components.auth_component import (
    check_authentication,
    create_user_management_interface,
    render_login_form,
    render_password_change_form,
    render_user_menu,
    require_permission,
)
from command_center.components.commission_tracking import CommissionTrackingComponent
from command_center.components.export_manager import ExportManager
from command_center.components.field_access_dashboard import create_field_access_dashboard, get_sample_sync_queue
from command_center.components.ghl_integration_status import create_ghl_integration_status
from command_center.components.ghl_status_ui import GHLStatusUI
from command_center.components.global_filters import GlobalFilters
from command_center.components.hero_metrics_card import render_hero_metrics
from command_center.components.hero_metrics_ui import HeroMetricsUI
from command_center.components.lead_intelligence_dashboard import LeadIntelligenceDashboard
from command_center.components.mobile_dashboard_integration import (
    get_jorge_ai_branding_css,
    get_sample_real_estate_data,
    render_mobile_dashboard_tab,
)
from command_center.components.mobile_metrics_cards import get_sample_metrics, render_mobile_metrics_cards
from command_center.components.mobile_navigation import create_mobile_navigation_component, demo_mobile_navigation
from command_center.components.mobile_responsive_layout import (
    apply_responsive_layout_system,
    create_responsive_card,
    create_responsive_container,
    create_responsive_grid,
)
from command_center.components.offline_indicator import (
    ConnectionStatus,
    NetworkMetrics,
    SyncItem,
    SyncItemStatus,
    SyncPriority,
    create_offline_indicator,
)
from command_center.components.performance_analytics import PerformanceAnalyticsComponent
from command_center.components.performance_chart import render_performance_chart
from command_center.components.seller_bot_pipeline import SellerBotPipelineViz
from command_center.components.touch_optimized_charts import ChartConfig, ChartType, render_touch_optimized_chart

# Page config
st.set_page_config(
    page_title="Jorge Real Estate AI Dashboard",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Title
st.title("🏠 Jorge Real Estate AI Dashboard")
st.markdown("**Real-time qualification, analytics, and automation**")


def _serialize(obj: Any) -> Any:
    """Convert dataclasses/enums/datetimes to JSON-friendly structures."""
    if hasattr(obj, "__dataclass_fields__"):
        return _serialize(asdict(obj))
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {key: _serialize(val) for key, val in obj.items()}
    if isinstance(obj, list):
        return [_serialize(val) for val in obj]
    return obj


@st.cache_data(ttl=30)
def load_dashboard_data():
    """Load dashboard data with 30-second cache."""
    service = DashboardDataService()
    return asyncio.run(service.get_dashboard_data())


def render_overview(location_id: str) -> None:
    st.subheader("Overview")
    with st.spinner("Loading dashboard data..."):
        dashboard_data = load_dashboard_data()

    render_hero_metrics(dashboard_data.hero_metrics)
    st.markdown("---")
    render_performance_chart(dashboard_data.performance_metrics)

    st.markdown("---")
    if location_id:
        HeroMetricsUI().render_hero_metrics_section(location_id)
    else:
        st.info("Set a GHL Location ID in the sidebar to enable ROI Command Center metrics.")


def render_conversations(location_id: str) -> None:
    st.subheader("Conversations")
    tab1, tab2, tab3 = st.tabs(["📋 Table", "🧠 Advanced", "📡 Activity Feed"])

    with tab1:
        dashboard_data = load_dashboard_data()
        render_active_conversations(
            conversations=dashboard_data.active_conversations.conversations,
            page=st.session_state.page,
            page_size=10,
        )

    with tab2:
        ActiveConversationsComponent().render()

    with tab3:
        ActivityFeed().render()


def render_pipeline(location_id: str) -> None:
    st.subheader("Seller Bot Pipeline")
    pipeline_location = location_id or "default"
    SellerBotPipelineViz().render_seller_pipeline_section(pipeline_location)


def render_analytics(location_id: str) -> None:
    st.subheader("Analytics")
    tab1, tab2, tab3 = st.tabs(["⚡ Performance", "💰 Commission", "🧠 Lead Intelligence"])

    with tab1:
        PerformanceAnalyticsComponent().render()

    with tab2:
        CommissionTrackingComponent().render()

    with tab3:
        lead_location = location_id or "default"
        LeadIntelligenceDashboard().render_lead_intelligence_section(lead_location)


def render_integrations(location_id: str) -> None:
    st.subheader("Integrations")
    tab1, tab2 = st.tabs(["🔗 GHL Status UI", "🧾 Raw Status Data"])

    with tab1:
        if location_id:
            GHLStatusUI().render_ghl_status_section(location_id)
        else:
            st.info("Set a GHL Location ID in the sidebar to load integration status.")

    with tab2:
        if location_id:
            try:
                status_component = asyncio.run(create_ghl_integration_status())
                status_data = asyncio.run(status_component.get_integration_status(location_id))
                st.json(_serialize(status_data))
            except Exception as exc:
                st.error(f"Failed to load raw integration data: {exc}")
        else:
            st.info("Set a GHL Location ID to view raw integration data.")


def render_mobile(location_id: str) -> None:
    st.subheader("Mobile Experience")
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "📱 Integrated Demo",
            "📊 Metrics Cards",
            "🧭 Navigation",
            "🧱 Responsive Layout",
            "📈 Touch Charts",
            "🛜 Offline Indicator",
            "🚗 Field Access",
        ]
    )

    sample_data = get_sample_real_estate_data()

    with tab1:
        apply_responsive_layout_system()
        st.markdown(get_jorge_ai_branding_css(), unsafe_allow_html=True)
        tab_choice = st.selectbox(
            "Mobile Tab",
            ["overview", "analytics", "quick-add", "chats", "profile"],
            index=0,
        )
        render_mobile_dashboard_tab(tab_choice, sample_data)
        create_mobile_navigation_component(current_tab=tab_choice, show_on_desktop=True)

    with tab2:
        metrics = get_sample_metrics()
        render_mobile_metrics_cards(metrics, title="Key Metrics", show_refresh=True)

    with tab3:
        demo_mobile_navigation()

    with tab4:
        apply_responsive_layout_system()
        cards = [
            create_responsive_card(
                f"<h4>Mobile Card {i + 1}</h4><p>Responsive layout preview.</p>",
                interactive=True,
                jorge_branded=True,
            )
            for i in range(6)
        ]
        grid_html = create_responsive_grid(cards, mobile_cols=1, tablet_cols=2, desktop_cols=3)
        container_html = create_responsive_container(grid_html, max_width="lg")
        st.markdown(container_html, unsafe_allow_html=True)

    with tab5:
        chart_data = sample_data["leads_data"].head(30)
        chart = ChartConfig(
            chart_type=ChartType.LINE,
            title="📈 Lead Velocity",
            data=chart_data,
            x_column="date",
            y_column="leads",
            color_column="source",
            height=260,
        )
        render_touch_optimized_chart(chart)

    with tab6:
        sync_queue = [
            SyncItem(
                id="sync_1",
                item_type="lead_update",
                timestamp=datetime.now(),
                priority=SyncPriority.NORMAL,
                status=SyncItemStatus.SYNCING,
                data_size=1200,
            ),
            SyncItem(
                id="sync_2",
                item_type="photo_upload",
                timestamp=datetime.now(),
                priority=SyncPriority.URGENT,
                status=SyncItemStatus.PENDING,
                data_size=4200,
            ),
        ]
        network_metrics = NetworkMetrics(
            latency=120.0,
            bandwidth=450.0,
            packet_loss=0.2,
            connection_type="wifi",
            signal_strength=82,
        )
        create_offline_indicator(
            connection_status=ConnectionStatus.ONLINE,
            sync_queue=sync_queue,
            network_metrics=network_metrics,
            expanded=True,
        )

    with tab7:
        create_field_access_dashboard(
            current_location=(32.7767, -96.7970),
            address="Dallas, TX",
            gps_accuracy=8.2,
            sync_queue=get_sample_sync_queue(),
            online_status=True,
        )


def render_exports(location_id: str) -> None:
    st.subheader("Exports")
    dashboard_data = load_dashboard_data()
    ExportManager().render_export_controls(data=dashboard_data)
    st.info("Use the sidebar controls to generate exports.")


def render_filters(location_id: str) -> None:
    st.subheader("Filters")
    GlobalFilters().render_sidebar_filters()
    st.info("Global filters appear in the sidebar for this section.")


def render_admin(location_id: str) -> None:
    st.subheader("Admin")
    create_user_management_interface()


NAV_SECTIONS = {
    "Overview": render_overview,
    "Conversations": render_conversations,
    "Pipeline": render_pipeline,
    "Analytics": render_analytics,
    "Integrations": render_integrations,
    "Mobile": render_mobile,
    "Exports": render_exports,
    "Filters": render_filters,
    "Admin": render_admin,
}


# Initialize session state
if "page" not in st.session_state:
    st.session_state.page = 1
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()


# Authentication gating
user = check_authentication()
if not user:
    render_login_form()
    st.stop()

if st.session_state.get("must_change_password"):
    render_password_change_form(user)
    st.stop()

if not require_permission(user, "dashboard", "read"):
    st.stop()


# Sidebar controls + navigation
default_location = os.getenv("GHL_LOCATION_ID", "")
with st.sidebar:
    st.header("Navigation")
    section = st.radio("Go to", list(NAV_SECTIONS.keys()), index=0)
    location_id = st.text_input(
        "GHL Location ID",
        value=st.session_state.get("location_id", default_location),
    )
    st.session_state.location_id = location_id

    auto_refresh = st.checkbox("Auto-refresh (30s)", value=True)

    if st.button("🔄 Refresh Now"):
        st.session_state.last_refresh = datetime.now()
        st.rerun()

    st.markdown("---")
    st.markdown(f"**Last Updated**: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

render_user_menu(user)


# Main content
try:
    NAV_SECTIONS[section](location_id)
except Exception as exc:
    st.error(f"Error loading dashboard section: {exc}")
    st.info("Try refreshing or selecting a different section.")


# Auto-refresh logic
if auto_refresh:
    import time

    time.sleep(30)
    st.session_state.last_refresh = datetime.now()
    st.rerun()
