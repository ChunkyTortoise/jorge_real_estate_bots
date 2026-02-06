"""
Mobile Dashboard Integration Example for Jorge's Real Estate AI

Complete integration example showing how all mobile-first components
work together in a production-ready real estate agent dashboard.

Components Integrated:
1. Mobile Navigation (Bottom navigation with touch optimization)
2. Mobile Metrics Cards (Horizontal scrolling carousel)
3. Touch-Optimized Charts (Real estate analytics)
4. Field Access Dashboard (GPS, voice, photos)
5. Responsive Layout System (Mobile-first containers)
6. Offline Indicator (Connection status and sync queue)

Features:
- Seamless component integration
- Consistent Jorge's Real Estate AI branding
- Touch-optimized user experience
- Offline-first architecture
- Real estate workflow optimization
"""

import streamlit as st
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Import all mobile components
from mobile_navigation import create_mobile_navigation_component, update_navigation_badges
from mobile_metrics_cards import render_mobile_metrics_cards, MetricCard, MetricState
from touch_optimized_charts import render_touch_optimized_chart, ChartConfig, ChartType
from field_access_dashboard import create_field_access_dashboard, get_sample_sync_queue as get_field_sync_queue
from mobile_responsive_layout import apply_responsive_layout_system, create_responsive_container, create_responsive_grid, create_responsive_card
from offline_indicator import create_offline_indicator, ConnectionStatus, SyncItem, SyncItemStatus, SyncPriority, NetworkMetrics


def get_jorge_ai_branding_css() -> str:
    """Returns Jorge's Real Estate AI specific branding CSS."""
    return """
    <style>
        /* Jorge's Real Estate AI Mobile Dashboard Integration */
        .jorge-mobile-dashboard {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            min-height: 100vh;
            padding-bottom: 80px; /* Space for bottom navigation */
        }

        .jorge-dashboard-header {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: white;
            padding: 24px 16px 16px;
            margin: -16px -16px 16px;
            position: relative;
            overflow: hidden;
        }

        .jorge-dashboard-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="2" fill="rgba(255,255,255,0.1)"/></svg>') repeat;
            opacity: 0.3;
        }

        .jorge-dashboard-title {
            font-size: 20px;
            font-weight: 700;
            margin: 0 0 8px;
            position: relative;
            z-index: 1;
        }

        .jorge-dashboard-subtitle {
            font-size: 14px;
            opacity: 0.9;
            margin: 0;
            position: relative;
            z-index: 1;
        }

        .jorge-dashboard-time {
            position: absolute;
            top: 16px;
            right: 16px;
            font-size: 12px;
            opacity: 0.8;
            z-index: 1;
        }

        .jorge-section-title {
            font-size: 18px;
            font-weight: 600;
            color: #1f2937;
            margin: 24px 0 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .jorge-section-divider {
            width: 100%;
            height: 1px;
            background: linear-gradient(90deg, transparent, #e5e7eb, transparent);
            margin: 20px 0;
        }

        /* Mobile-specific animations */
        .jorge-mobile-fade-in {
            animation: jorgeFadeIn 0.5s ease-out;
        }

        @keyframes jorgeFadeIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Quick action cards */
        .jorge-quick-actions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
            gap: 12px;
            margin: 16px 0;
        }

        .jorge-quick-action {
            background: white;
            border-radius: 12px;
            padding: 16px 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            cursor: pointer;
            transition: all 0.2s ease;
            border: 2px solid transparent;
        }

        .jorge-quick-action:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
            border-color: #3b82f6;
        }

        .jorge-quick-action-icon {
            font-size: 24px;
            margin-bottom: 4px;
        }

        .jorge-quick-action-label {
            font-size: 12px;
            font-weight: 600;
            color: #374151;
        }

        /* Status badges */
        .jorge-status-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: #f3f4f6;
            color: #374151;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }

        .jorge-status-badge.success {
            background: #dcfce7;
            color: #166534;
        }

        .jorge-status-badge.warning {
            background: #fef3c7;
            color: #92400e;
        }

        .jorge-status-badge.error {
            background: #fee2e2;
            color: #991b1b;
        }

        /* Mobile-optimized tables */
        .jorge-mobile-table {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .jorge-mobile-table-row {
            display: flex;
            align-items: center;
            padding: 12px 16px;
            border-bottom: 1px solid #f1f5f9;
            min-height: 48px;
        }

        .jorge-mobile-table-row:last-child {
            border-bottom: none;
        }

        .jorge-mobile-table-cell {
            flex: 1;
            font-size: 14px;
        }

        .jorge-mobile-table-cell.primary {
            font-weight: 600;
            color: #1f2937;
        }

        .jorge-mobile-table-cell.secondary {
            color: #6b7280;
            font-size: 12px;
        }

        /* Floating action button */
        .jorge-fab {
            position: fixed;
            bottom: 90px;
            right: 16px;
            z-index: 999;
            background: linear-gradient(135deg, #3b82f6, #1e3a8a);
            color: white;
            border: none;
            border-radius: 28px;
            width: 56px;
            height: 56px;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
            transition: all 0.3s ease;
        }

        .jorge-fab:hover {
            transform: scale(1.1);
            box-shadow: 0 8px 24px rgba(59, 130, 246, 0.4);
        }

        /* Safe area handling for iOS */
        @supports (padding-bottom: env(safe-area-inset-bottom)) {
            .jorge-mobile-dashboard {
                padding-bottom: calc(80px + env(safe-area-inset-bottom));
            }
        }
    </style>
    """


def get_sample_real_estate_data() -> Dict[str, Any]:
    """Generates comprehensive sample real estate data for the dashboard."""
    np.random.seed(42)
    
    # Generate dates
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    
    # Leads data
    leads_data = pd.DataFrame({
        'date': dates,
        'leads': np.random.poisson(8, len(dates)) + 5,
        'qualified': np.random.poisson(3, len(dates)) + 1,
        'source': np.random.choice(['Website', 'Referral', 'Social Media', 'Ads'], len(dates))
    })
    
    # Revenue data
    # Use a fixed 12-month series to avoid DataFrame column length mismatches.
    monthly_dates = pd.date_range(start='2024-01-01', periods=12, freq='MS')
    revenue_data = pd.DataFrame({
        'month': monthly_dates,
        'revenue': np.random.normal(75000, 20000, len(monthly_dates)).clip(min=20000),
        'commission': np.random.normal(22500, 6000, len(monthly_dates)).clip(min=6000)
    })
    
    # Property data
    property_data = pd.DataFrame({
        'type': ['Single Family', 'Condo', 'Townhouse', 'Multi-Family', 'Luxury'],
        'count': [52, 38, 24, 15, 12],
        'avg_price': [485000, 340000, 420000, 750000, 1200000]
    })
    
    return {
        'leads_data': leads_data,
        'revenue_data': revenue_data,
        'property_data': property_data,
        'last_updated': datetime.now()
    }


def create_dashboard_metrics() -> List[MetricCard]:
    """Creates real estate dashboard metrics."""
    return [
        MetricCard(
            id="total_leads",
            title="Total Leads",
            value=1247,
            icon="👥",
            state=MetricState.SUCCESS,
            change_percentage=18.5,
            change_period="vs last month"
        ),
        MetricCard(
            id="active_listings",
            title="Active Listings",
            value=89,
            icon="🏠",
            state=MetricState.INFO,
            change_percentage=12.3,
            change_period="this quarter"
        ),
        MetricCard(
            id="monthly_revenue",
            title="Revenue (30d)",
            value=186500,
            icon="💰",
            state=MetricState.SUCCESS,
            change_percentage=24.7,
            change_period="vs last month"
        ),
        MetricCard(
            id="avg_response",
            title="Response Time",
            value="3.2m",
            icon="⏱️",
            state=MetricState.SUCCESS,
            change_percentage=-22.1,
            change_period="improvement"
        ),
        MetricCard(
            id="conversion_rate",
            title="Conversion Rate",
            value="12.8%",
            icon="📊",
            state=MetricState.WARNING,
            change_percentage=-4.2,
            change_period="this month"
        ),
        MetricCard(
            id="pipeline_value",
            title="Pipeline Value",
            value=2450000,
            icon="💎",
            state=MetricState.INFO,
            change_percentage=31.5,
            change_period="total"
        )
    ]


def create_dashboard_charts(data: Dict[str, Any]) -> List[ChartConfig]:
    """Creates chart configurations for the dashboard."""
    return [
        ChartConfig(
            chart_type=ChartType.LINE,
            title="📈 Daily Lead Generation",
            data=data['leads_data'].head(90),  # Last 90 days
            x_column='date',
            y_column='leads',
            color_column='source',
            height=250
        ),
        ChartConfig(
            chart_type=ChartType.BAR,
            title="💰 Monthly Revenue",
            data=data['revenue_data'],
            x_column='month',
            y_column='revenue',
            height=250
        ),
        ChartConfig(
            chart_type=ChartType.PIE,
            title="🏠 Property Types",
            data=data['property_data'],
            x_column='type',
            y_column='count',
            height=280
        )
    ]


def render_quick_actions() -> str:
    """Renders quick action buttons for real estate workflows."""
    actions = [
        {'icon': '📞', 'label': 'Call Lead'},
        {'icon': '✉️', 'label': 'Send Email'},
        {'icon': '📅', 'label': 'Schedule'},
        {'icon': '📝', 'label': 'Add Note'},
        {'icon': '📊', 'label': 'View Stats'},
        {'icon': '📱', 'label': 'Text Client'}
    ]
    
    actions_html = ""
    for action in actions:
        actions_html += f"""
        <div class="jorge-quick-action">
            <div class="jorge-quick-action-icon">{action['icon']}</div>
            <div class="jorge-quick-action-label">{action['label']}</div>
        </div>
        """
    
    return f'<div class="jorge-quick-actions">{actions_html}</div>'


def render_recent_activity() -> str:
    """Renders recent activity feed."""
    activities = [
        {
            'time': '2 min ago',
            'title': 'New lead: Sarah Johnson',
            'subtitle': 'Interested in 3BR condo downtown',
            'status': 'success'
        },
        {
            'time': '15 min ago', 
            'title': 'Property showing scheduled',
            'subtitle': '123 Oak Street - Tomorrow 2:00 PM',
            'status': 'warning'
        },
        {
            'time': '1 hour ago',
            'title': 'Contract signed!',
            'subtitle': '456 Pine Avenue - $485,000',
            'status': 'success'
        },
        {
            'time': '3 hours ago',
            'title': 'Follow-up reminder',
            'subtitle': 'Call Mike Thompson about inspection',
            'status': 'error'
        }
    ]
    
    activity_html = ""
    for activity in activities:
        activity_html += f"""
        <div class="jorge-mobile-table-row">
            <div class="jorge-mobile-table-cell">
                <div class="jorge-mobile-table-cell primary">{activity['title']}</div>
                <div class="jorge-mobile-table-cell secondary">{activity['subtitle']}</div>
            </div>
            <div class="jorge-mobile-table-cell" style="flex: 0 0 auto;">
                <div class="jorge-status-badge {activity['status']}">{activity['time']}</div>
            </div>
        </div>
        """
    
    return f'<div class="jorge-mobile-table">{activity_html}</div>'


def render_mobile_dashboard_tab(tab_name: str, data: Dict[str, Any]) -> None:
    """Renders content for each mobile dashboard tab."""
    
    if tab_name == "overview":
        # Dashboard header
        current_time = datetime.now().strftime("%H:%M")
        st.markdown(f"""
        <div class="jorge-dashboard-header">
            <div class="jorge-dashboard-time">{current_time}</div>
            <h1 class="jorge-dashboard-title">🏠 Jorge's Real Estate AI</h1>
            <p class="jorge-dashboard-subtitle">Mobile Command Center</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Key metrics
        st.markdown('<h2 class="jorge-section-title">📊 Key Metrics</h2>', unsafe_allow_html=True)
        metrics = create_dashboard_metrics()
        render_mobile_metrics_cards(metrics, title="", show_refresh=True)
        
        # Quick actions
        st.markdown('<h2 class="jorge-section-title">⚡ Quick Actions</h2>', unsafe_allow_html=True)
        st.markdown(render_quick_actions(), unsafe_allow_html=True)
        
        # Recent activity
        st.markdown('<h2 class="jorge-section-title">📋 Recent Activity</h2>', unsafe_allow_html=True)
        st.markdown(render_recent_activity(), unsafe_allow_html=True)
    
    elif tab_name == "analytics":
        st.markdown('<h2 class="jorge-section-title">📈 Performance Analytics</h2>', unsafe_allow_html=True)
        
        charts = create_dashboard_charts(data)
        
        # Render charts in mobile-optimized layout
        for chart in charts:
            st.markdown('<div class="jorge-mobile-fade-in">', unsafe_allow_html=True)
            render_touch_optimized_chart(chart)
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('<div class="jorge-section-divider"></div>', unsafe_allow_html=True)
    
    elif tab_name == "quick-add":
        st.markdown('<h2 class="jorge-section-title">➕ Quick Add</h2>', unsafe_allow_html=True)
        
        # Quick add form (simplified for demo)
        st.markdown(create_responsive_card("""
        <h4 style="margin-top: 0;">Add New Lead</h4>
        <div style="margin-bottom: 12px;">
            <input type="text" placeholder="Lead Name" style="width: 100%; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px;">
        </div>
        <div style="margin-bottom: 12px;">
            <input type="tel" placeholder="Phone Number" style="width: 100%; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px;">
        </div>
        <div style="margin-bottom: 16px;">
            <select style="width: 100%; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px;">
                <option>Lead Source</option>
                <option>Website</option>
                <option>Referral</option>
                <option>Social Media</option>
                <option>Advertisement</option>
            </select>
        </div>
        <button style="width: 100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600;">
            Add Lead
        </button>
        """, jorge_branded=True), unsafe_allow_html=True)
        
        st.markdown('<div class="jorge-section-divider"></div>', unsafe_allow_html=True)
        
        st.markdown(create_responsive_card("""
        <h4 style="margin-top: 0;">Add Property</h4>
        <div style="margin-bottom: 12px;">
            <input type="text" placeholder="Property Address" style="width: 100%; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px;">
        </div>
        <div style="margin-bottom: 12px;">
            <input type="number" placeholder="Price" style="width: 100%; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px;">
        </div>
        <div style="margin-bottom: 16px;">
            <select style="width: 100%; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px;">
                <option>Property Type</option>
                <option>Single Family</option>
                <option>Condo</option>
                <option>Townhouse</option>
                <option>Multi-Family</option>
            </select>
        </div>
        <button style="width: 100%; padding: 12px; background: #10b981; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600;">
            Add Property
        </button>
        """, jorge_branded=True), unsafe_allow_html=True)
    
    elif tab_name == "chats":
        st.markdown('<h2 class="jorge-section-title">🗣️ Active Conversations</h2>', unsafe_allow_html=True)
        
        # Conversation list (simplified for demo)
        conversations = [
            {'name': 'Sarah Johnson', 'message': 'When can we schedule a viewing?', 'time': '2m', 'unread': 2},
            {'name': 'Mike Thompson', 'message': 'Thanks for the property details!', 'time': '15m', 'unread': 0},
            {'name': 'Lisa Chen', 'message': 'Is the price negotiable?', 'time': '1h', 'unread': 1},
            {'name': 'David Rodriguez', 'message': 'Inspection completed successfully', 'time': '3h', 'unread': 0},
        ]
        
        conversations_html = ""
        for conv in conversations:
            unread_badge = f'<span style="background: #ef4444; color: white; border-radius: 10px; padding: 2px 6px; font-size: 10px; font-weight: bold;">{conv["unread"]}</span>' if conv['unread'] > 0 else ''
            
            conversations_html += f"""
            <div class="jorge-mobile-table-row">
                <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #3b82f6, #1e3a8a); border-radius: 20px; margin-right: 12px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">
                    {conv['name'][0]}
                </div>
                <div class="jorge-mobile-table-cell">
                    <div class="jorge-mobile-table-cell primary">{conv['name']}</div>
                    <div class="jorge-mobile-table-cell secondary">{conv['message']}</div>
                </div>
                <div class="jorge-mobile-table-cell" style="flex: 0 0 auto; text-align: right;">
                    <div style="font-size: 12px; color: #6b7280; margin-bottom: 4px;">{conv['time']}</div>
                    {unread_badge}
                </div>
            </div>
            """
        
        st.markdown(f'<div class="jorge-mobile-table">{conversations_html}</div>', unsafe_allow_html=True)
    
    elif tab_name == "profile":
        st.markdown('<h2 class="jorge-section-title">👤 Profile & Settings</h2>', unsafe_allow_html=True)
        
        # Profile card
        st.markdown(create_responsive_card("""
        <div style="text-align: center; padding: 20px 0;">
            <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #3b82f6, #1e3a8a); border-radius: 40px; margin: 0 auto 16px; display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; font-weight: bold;">
                JA
            </div>
            <h3 style="margin: 0 0 4px;">Jorge Agent</h3>
            <p style="margin: 0; color: #6b7280; font-size: 14px;">Senior Real Estate Professional</p>
            <p style="margin: 8px 0 0; color: #6b7280; font-size: 12px;">📍 Downtown District • ⭐ 4.9 Rating</p>
        </div>
        """, jorge_branded=True), unsafe_allow_html=True)
        
        # Settings menu
        settings_items = [
            {'icon': '🔔', 'title': 'Notifications', 'subtitle': 'Push, email, SMS preferences'},
            {'icon': '🎨', 'title': 'Appearance', 'subtitle': 'Theme, contrast, layout'},
            {'icon': '📊', 'title': 'Analytics', 'subtitle': 'Data export, reporting'},
            {'icon': '🔒', 'title': 'Privacy', 'subtitle': 'Data sharing, permissions'},
            {'icon': '❓', 'title': 'Help & Support', 'subtitle': 'Documentation, contact'},
            {'icon': '⚙️', 'title': 'Advanced', 'subtitle': 'Developer options, sync'},
        ]
        
        settings_html = ""
        for item in settings_items:
            settings_html += f"""
            <div class="jorge-mobile-table-row">
                <div style="font-size: 20px; margin-right: 12px;">{item['icon']}</div>
                <div class="jorge-mobile-table-cell">
                    <div class="jorge-mobile-table-cell primary">{item['title']}</div>
                    <div class="jorge-mobile-table-cell secondary">{item['subtitle']}</div>
                </div>
                <div class="jorge-mobile-table-cell" style="flex: 0 0 auto; color: #6b7280;">
                    ›
                </div>
            </div>
            """
        
        st.markdown(f'<div class="jorge-mobile-table">{settings_html}</div>', unsafe_allow_html=True)


def create_integrated_mobile_dashboard():
    """Creates the complete integrated mobile dashboard."""
    
    # Apply responsive layout system
    apply_responsive_layout_system()
    
    # Add Jorge's AI branding CSS
    st.markdown(get_jorge_ai_branding_css(), unsafe_allow_html=True)
    
    # Get sample data
    data = get_sample_real_estate_data()
    
    # Initialize session state for current tab
    if 'current_mobile_tab' not in st.session_state:
        st.session_state.current_mobile_tab = "overview"
    
    # Create notification counts for navigation badges
    notification_counts = {
        'overview': 0,
        'analytics': 0,
        'quick-add': 0,
        'chats': 3,  # 3 unread messages
        'profile': 1   # 1 notification
    }
    
    # Container for the entire dashboard
    st.markdown('<div class="jorge-mobile-dashboard">', unsafe_allow_html=True)
    
    # Render current tab content
    render_mobile_dashboard_tab(st.session_state.current_mobile_tab, data)
    
    # Close dashboard container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mobile navigation (always at bottom)
    create_mobile_navigation_component(
        current_tab=st.session_state.current_mobile_tab,
        notification_counts=notification_counts,
        show_on_desktop=True  # Show for demo purposes
    )
    
    # Offline indicator (always at top right)
    create_offline_indicator(
        connection_status=ConnectionStatus.ONLINE,
        sync_queue=[],  # Empty for demo
        network_metrics=NetworkMetrics(latency=120, connection_type="wifi", signal_strength=85),
        expanded=False
    )
    
    # Floating action button
    st.markdown("""
    <button class="jorge-fab" title="Quick Add">
        ➕
    </button>
    """, unsafe_allow_html=True)


# Tab switching demo (for demonstration purposes)
def handle_tab_switching_demo():
    """Handles tab switching for demonstration purposes."""
    st.sidebar.header("🎮 Demo Controls")
    
    # Tab selection
    selected_tab = st.sidebar.selectbox(
        "Switch Mobile Tab",
        ["overview", "analytics", "quick-add", "chats", "profile"],
        index=["overview", "analytics", "quick-add", "chats", "profile"].index(st.session_state.current_mobile_tab)
    )
    
    if selected_tab != st.session_state.current_mobile_tab:
        st.session_state.current_mobile_tab = selected_tab
        st.rerun()
    
    # Demo options
    st.sidebar.subheader("🔧 Component Options")
    
    show_field_dashboard = st.sidebar.checkbox("Show Field Dashboard", value=False)
    high_contrast_mode = st.sidebar.checkbox("High Contrast Mode", value=False)
    
    if show_field_dashboard:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🏠 Field Access Dashboard")
        
        create_field_access_dashboard(
            current_location=(40.7589, -73.9851),
            address="123 Main Street, New York, NY",
            gps_accuracy=8.5,
            sync_queue=get_field_sync_queue(),
            online_status=True,
            high_contrast=high_contrast_mode
        )


# Main demo function
def demo_integrated_mobile_dashboard():
    """Main demo function for the integrated mobile dashboard."""
    
    st.set_page_config(
        page_title="Jorge's Mobile Dashboard",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="auto"
    )
    
    # Handle tab switching
    handle_tab_switching_demo()
    
    # Create the integrated dashboard
    create_integrated_mobile_dashboard()
    
    # Instructions in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    ### 📱 Integrated Mobile Dashboard
    
    **Components Included:**
    - ✅ Mobile Navigation (Bottom bar)
    - ✅ Mobile Metrics Cards (Horizontal scroll)
    - ✅ Touch-Optimized Charts (Real estate data)
    - ✅ Field Access Dashboard (GPS, voice, photos)
    - ✅ Responsive Layout System (Mobile-first)
    - ✅ Offline Indicator (Connection status)
    
    **Touch Interactions:**
    - Tap navigation items to switch tabs
    - Swipe left/right between tabs
    - Tap metrics cards to expand
    - Pinch-zoom on charts
    - Pull-to-refresh on data
    
    **Real Estate Features:**
    - Lead management and tracking
    - Property analytics and insights
    - Field data collection (GPS, photos, voice)
    - Client conversation management
    - Revenue and performance metrics
    
    **Technical Features:**
    - Mobile-first responsive design
    - Offline queue with auto-sync
    - Touch targets ≥44px
    - Professional Jorge's AI branding
    - 60fps smooth animations
    - Safe area handling for modern phones
    """)


if __name__ == "__main__":
    demo_integrated_mobile_dashboard()