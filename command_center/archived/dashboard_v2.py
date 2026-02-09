"""
Jorge's Real Estate AI Dashboard v2.0 - Phase 3B Integration

Advanced analytics dashboard with:
- Enhanced hero metrics with ROI analysis
- Real-time performance analytics
- Active seller conversation management
- Commission tracking and forecasting
- GHL integration monitoring

Features comprehensive business intelligence with mobile-responsive design.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Phase 3A components (existing)
from bots.shared.dashboard_data_service import get_dashboard_data_service

# Import services
from bots.shared.logger import get_logger
from command_center.components.active_conversations import render_active_conversations

# Import authentication
from command_center.components.auth_component import (
    check_authentication,
    create_user_management_interface,
    render_login_form,
    render_user_menu,
    require_permission,
)
from command_center.components.commission_tracking import render_commission_tracking
from command_center.components.enhanced_hero_metrics import render_enhanced_hero_metrics
from command_center.components.ghl_integration_status import render_ghl_integration_status

# Import Phase 3B components (new)
from command_center.components.performance_analytics import render_performance_analytics

logger = get_logger(__name__)

# Configure Streamlit page
st.set_page_config(
    page_title="Jorge's AI Dashboard v2.0",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get help': 'https://github.com/jorge-real-estate-ai/help',
        'Report a bug': 'https://github.com/jorge-real-estate-ai/issues',
        'About': """
        # Jorge's Real Estate AI Dashboard v2.0

        **Phase 3B Advanced Analytics**

        Professional real estate intelligence platform powered by AI.

        Features:
        - Real-time performance analytics
        - Seller conversation management
        - Commission tracking & forecasting
        - GHL integration monitoring

        Built with ❤️ by Claude Code Assistant
        """
    }
)

# Apply custom CSS for professional styling
st.markdown("""
<style>
    /* Main dashboard styling */
    .main .block-container {
        padding: 1rem 2rem;
        max-width: 100%;
    }

    /* Header styling */
    .dashboard-header {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }

    .dashboard-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
    }

    .dashboard-header .subtitle {
        font-size: 1.2rem;
        opacity: 0.9;
        margin-top: 0.5rem;
    }

    /* Metric card styling */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #f8fafc;
        padding: 0.5rem;
        border-radius: 10px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
    }

    /* Success/warning/error states */
    .success-box {
        background-color: #dcfce7;
        border: 1px solid #16a34a;
        border-radius: 8px;
        padding: 1rem;
        color: #15803d;
    }

    .warning-box {
        background-color: #fef3c7;
        border: 1px solid #d97706;
        border-radius: 8px;
        padding: 1rem;
        color: #92400e;
    }

    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Responsive design */
    @media (max-width: 768px) {
        .main .block-container {
            padding: 0.5rem 1rem;
        }

        .dashboard-header h1 {
            font-size: 1.8rem;
        }
    }
</style>
""", unsafe_allow_html=True)


def render_dashboard_header():
    """Render the main dashboard header with live status."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    st.markdown(f"""
    <div class="dashboard-header">
        <h1>🏠 Jorge's Real Estate AI Dashboard v2.0</h1>
        <div class="subtitle">
            Advanced Analytics & Intelligence Platform • Last Updated: {current_time}
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_quick_stats():
    """Render quick stats sidebar."""
    with st.sidebar:
        st.header("📊 Quick Stats")

        try:
            # Get dashboard summary data
            data_service = get_dashboard_data_service()

            # Fetch data asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            summary_data = loop.run_until_complete(
                data_service.get_complete_dashboard_data()
            )
            loop.close()

            if summary_data and summary_data.get('status') == 'success':
                hero_data = summary_data.get('hero_data', {})

                st.metric(
                    "Total Leads",
                    hero_data.get('total_leads', 'N/A'),
                    help="Total leads in system"
                )

                st.metric(
                    "Active Conversations",
                    hero_data.get('active_conversations', 'N/A'),
                    help="Currently active seller conversations"
                )

                st.metric(
                    "Revenue (30d)",
                    f"${hero_data.get('revenue_30_day', 0):,.0f}",
                    help="Revenue generated in last 30 days"
                )

                st.metric(
                    "Pipeline Value",
                    f"${hero_data.get('commission_pipeline', 0):,.0f}",
                    help="Total commission pipeline value"
                )
            else:
                st.warning("⚠️ Data temporarily unavailable")

        except Exception as e:
            logger.exception(f"Error fetching quick stats: {e}")
            st.error("❌ Unable to load stats")


def render_dashboard_tabs():
    """Render the main dashboard tabs with Phase 3A and 3B components."""

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏠 Overview",
        "📈 Performance",
        "🗣️ Conversations",
        "💰 Commission",
        "🔗 GHL Status",
        "ℹ️ About"
    ])

    with tab1:
        render_overview_tab()

    with tab2:
        render_performance_tab()

    with tab3:
        render_conversations_tab()

    with tab4:
        render_commission_tab()

    with tab5:
        render_ghl_status_tab()

    with tab6:
        render_about_tab()


def render_overview_tab():
    """Render the overview tab with hero metrics."""
    st.header("🏠 Business Overview")

    try:
        # Render Phase 3A enhanced hero metrics
        render_enhanced_hero_metrics()

        # Add summary insights
        st.subheader("📊 Key Insights")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            <div class="success-box">
                <h4>🎯 Performance Highlights</h4>
                <ul>
                    <li>Lead response time under 5-minute rule compliance</li>
                    <li>Strong cache performance reducing AI costs</li>
                    <li>Active seller conversation pipeline</li>
                    <li>Positive revenue trend and forecasting</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown("""
            <div class="warning-box">
                <h4>⚠️ Areas for Focus</h4>
                <ul>
                    <li>Monitor Q3-Q4 conversation advancement</li>
                    <li>Track commission pipeline conversion</li>
                    <li>Optimize lead source ROI performance</li>
                    <li>Maintain GHL integration health</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        logger.exception(f"Error rendering overview tab: {e}")
        st.error("Failed to load overview. Please refresh the page.")


def render_performance_tab():
    """Render the performance analytics tab."""
    st.header("📈 Performance Analytics")

    try:
        # Render Phase 3B performance analytics
        render_performance_analytics()

    except Exception as e:
        logger.exception(f"Error rendering performance tab: {e}")
        st.error("Failed to load performance analytics. Please refresh the page.")


def render_conversations_tab():
    """Render the active conversations tab."""
    st.header("🗣️ Active Conversations")

    try:
        # Render Phase 3B active conversations
        render_active_conversations()

    except Exception as e:
        logger.exception(f"Error rendering conversations tab: {e}")
        st.error("Failed to load conversations. Please refresh the page.")


def render_commission_tab():
    """Render the commission tracking tab."""
    st.header("💰 Commission Tracking")

    try:
        # Render Phase 3B commission tracking
        render_commission_tracking()

    except Exception as e:
        logger.exception(f"Error rendering commission tab: {e}")
        st.error("Failed to load commission tracking. Please refresh the page.")


def render_ghl_status_tab():
    """Render the GHL integration status tab."""
    st.header("🔗 GHL Integration")

    try:
        # Render Phase 3A GHL integration status
        render_ghl_integration_status()

    except Exception as e:
        logger.exception(f"Error rendering GHL status tab: {e}")
        st.error("Failed to load GHL status. Please refresh the page.")


def render_about_tab():
    """Render the about/help tab."""
    st.header("ℹ️ About This Dashboard")

    st.markdown("""
    ## Jorge's Real Estate AI Dashboard v2.0

    **Phase 3B Advanced Analytics Platform**

    This dashboard provides comprehensive business intelligence for real estate operations with AI-powered insights.

    ### 🚀 Features

    **Phase 3A (Core Foundation)**
    - Enhanced hero metrics with ROI analysis
    - Lead source performance tracking
    - 30-day revenue forecasting
    - GHL integration monitoring

    **Phase 3B (Advanced Analytics)**
    - Real-time performance analytics
    - Active conversation management
    - Commission tracking & forecasting
    - Interactive data visualization

    ### 📊 Dashboard Sections

    1. **🏠 Overview**: Key business metrics and insights
    2. **📈 Performance**: System performance and optimization metrics
    3. **🗣️ Conversations**: Active seller conversation tracking
    4. **💰 Commission**: Revenue forecasting and pipeline analysis
    5. **🔗 GHL Status**: GoHighLevel integration health monitoring

    ### 🔄 Data Updates

    - **Real-time**: Conversation states, performance metrics
    - **Every 30 seconds**: Hero metrics, dashboard summary
    - **Every 5 minutes**: Budget/timeline distributions, commission data
    - **Every hour**: Cost savings, long-term analytics

    ### 🎯 Key Performance Indicators

    - **Lead Response Time**: Target <5 minutes
    - **Cache Hit Rate**: Target >80%
    - **AI Response Time**: Target <2000ms
    - **GHL API Health**: Target >98%
    - **Qualification Rate**: Target >10%

    ### 🛠️ Technical Architecture

    **Backend Services**:
    - MetricsService: Performance aggregation
    - DashboardDataService: Data orchestration
    - PerformanceTracker: Real-time monitoring

    **Data Models**:
    - 12 comprehensive dataclasses for type safety
    - Multi-tier caching (30s-1hr TTL)
    - Async/await throughout for performance

    **UI Components**:
    - Mobile-responsive design
    - Interactive Plotly visualizations
    - Error boundaries and fallback states
    - Professional styling and animations

    ### 📱 Mobile Responsiveness

    This dashboard is optimized for:
    - Desktop computers (1920x1080+)
    - Tablets (768px+)
    - Mobile phones (320px+)

    ### 🔒 Security & Privacy

    - No sensitive data exposed in logs
    - Secure caching with TTL expiration
    - Error handling with graceful degradation
    - PII protection in data models

    ### 📞 Support

    For technical support or feature requests:
    - GitHub Issues: [Report a Bug](https://github.com/jorge-real-estate-ai/issues)
    - Documentation: [Help Center](https://github.com/jorge-real-estate-ai/help)

    ---

    **Built with ❤️ by Claude Code Assistant**
    *Version 2.0 • January 2026 • Phase 3B Advanced Analytics*
    """)


def render_footer():
    """Render dashboard footer with status and refresh info."""
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔄 Refresh Data", help="Refresh all dashboard data"):
            # Clear any cached data
            st.cache_data.clear()
            st.rerun()

    with col2:
        st.write("🟢 **Status:** Online")

    with col3:
        st.write(f"⏰ **Updated:** {datetime.now().strftime('%H:%M:%S')}")

    with col4:
        st.write("📊 **Version:** 2.0 (Phase 3B)")


def main():
    """Main dashboard application entry point with authentication."""
    try:
        # Check authentication
        user = check_authentication()
        
        if not user:
            # Show login form
            st.markdown("""
            <div style="text-align: center; padding: 2rem;">
                <h1>🏠 Jorge's Real Estate AI Dashboard</h1>
                <p style="font-size: 1.2rem; color: #6b7280; margin-bottom: 3rem;">
                    Professional real estate intelligence platform
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            render_login_form()
            return
        
        # User is authenticated - render user menu
        render_user_menu(user)
        
        # Check dashboard access permission
        if not require_permission(user, 'dashboard', 'read'):
            st.stop()
        
        # Render dashboard header
        render_dashboard_header()

        # Add user context to header
        st.sidebar.success(f"Welcome back, {user.name}! 👋")
        
        # Show user management for admins
        if user.role.value == 'admin':
            with st.sidebar.expander("👥 User Management"):
                create_user_management_interface()

        # Render sidebar quick stats
        render_quick_stats()

        # Render main dashboard tabs
        render_dashboard_tabs()

        # Render footer
        render_footer()

        # Auto-refresh every 30 seconds (for real-time data)
        # st.rerun()  # Uncomment for auto-refresh

    except Exception as e:
        logger.exception(f"Critical error in dashboard main: {e}")
        st.error("🚨 Critical dashboard error. Please refresh the page.")

        if st.button("🔄 Force Refresh"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()


if __name__ == "__main__":
    main()