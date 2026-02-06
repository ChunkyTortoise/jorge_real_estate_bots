"""
Mobile Navigation Component for Jorge's Real Estate AI Dashboard

Production-ready, mobile-first navigation with touch optimization,
thumb-zone positioning, and swipe gesture support.

Features:
- Bottom navigation bar (thumb-zone optimized)
- Touch targets ≥ 44px minimum size
- Active state styling with haptic feedback
- Notification badges for real-time updates
- Swipe gesture support between tabs
- Professional Jorge's Real Estate AI branding
"""

import streamlit as st
from typing import Dict, List, Optional, Tuple
from datetime import datetime


def get_mobile_navigation_css() -> str:
    """
    Returns mobile-first CSS for the navigation component.
    Optimized for touch interactions and professional branding.
    """
    return """
    <style>
        /* Mobile Navigation Container */
        .mobile-nav-container {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(20px);
            box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
            padding: 8px 0 env(safe-area-inset-bottom, 8px);
            animation: slideUp 0.3s ease-out;
        }

        /* Navigation Items Container */
        .mobile-nav-items {
            display: flex;
            justify-content: space-around;
            align-items: center;
            max-width: 600px;
            margin: 0 auto;
            padding: 0 16px;
        }

        /* Individual Navigation Item */
        .mobile-nav-item {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 56px;
            min-width: 44px;
            padding: 8px 4px;
            border-radius: 12px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            position: relative;
            text-decoration: none;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }

        .mobile-nav-item:hover {
            background-color: rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
        }

        .mobile-nav-item:active {
            transform: translateY(0);
            background-color: rgba(255, 255, 255, 0.2);
        }

        /* Active state styling */
        .mobile-nav-item.active {
            background-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
        }

        .mobile-nav-item.active::before {
            content: '';
            position: absolute;
            top: 0;
            left: 50%;
            width: 24px;
            height: 3px;
            background: linear-gradient(90deg, #fbbf24, #f59e0b);
            border-radius: 0 0 12px 12px;
            transform: translateX(-50%);
            animation: activeIndicator 0.3s ease-out;
        }

        /* Icon styling */
        .mobile-nav-icon {
            font-size: 20px;
            margin-bottom: 4px;
            transition: transform 0.2s ease;
        }

        .mobile-nav-item.active .mobile-nav-icon {
            transform: scale(1.1);
        }

        /* Label styling */
        .mobile-nav-label {
            font-size: 10px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.8);
            text-align: center;
            line-height: 1.2;
            transition: color 0.2s ease;
        }

        .mobile-nav-item.active .mobile-nav-label {
            color: white;
        }

        /* Notification badge */
        .mobile-nav-badge {
            position: absolute;
            top: 4px;
            right: 8px;
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
            font-size: 10px;
            font-weight: 700;
            border-radius: 10px;
            min-width: 18px;
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid white;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            animation: badgePulse 2s infinite;
        }

        /* Animations */
        @keyframes slideUp {
            from {
                transform: translateY(100%);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        @keyframes activeIndicator {
            from {
                width: 0;
                opacity: 0;
            }
            to {
                width: 24px;
                opacity: 1;
            }
        }

        @keyframes badgePulse {
            0%, 100% {
                transform: scale(1);
                opacity: 1;
            }
            50% {
                transform: scale(1.1);
                opacity: 0.8;
            }
        }

        /* Swipe gesture indicator */
        .mobile-nav-swipe-indicator {
            position: absolute;
            top: -3px;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            opacity: 0;
            transition: opacity 0.2s ease;
        }

        .mobile-nav-container.swiping .mobile-nav-swipe-indicator {
            opacity: 1;
        }

        /* Responsive adjustments */
        @media (max-width: 320px) {
            .mobile-nav-items {
                padding: 0 8px;
            }
            
            .mobile-nav-item {
                min-height: 48px;
                padding: 6px 2px;
            }
            
            .mobile-nav-icon {
                font-size: 18px;
            }
            
            .mobile-nav-label {
                font-size: 9px;
            }
        }

        @media (min-width: 768px) {
            .mobile-nav-container {
                display: none; /* Hide on tablet/desktop */
            }
        }

        /* Jorge's Real Estate AI branding accent */
        .mobile-nav-brand-accent {
            position: absolute;
            top: -1px;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, #fbbf24, #f59e0b, #fbbf24);
            animation: brandAccent 3s ease-in-out infinite;
        }

        @keyframes brandAccent {
            0%, 100% {
                opacity: 0.6;
            }
            50% {
                opacity: 1;
            }
        }
    </style>
    """


def get_mobile_navigation_js() -> str:
    """
    Returns JavaScript for touch interactions and swipe gestures.
    Optimized for 60fps performance and smooth animations.
    """
    return """
    <script>
        class MobileNavigation {
            constructor() {
                this.startX = 0;
                this.startTime = 0;
                this.isSwipeActive = false;
                this.swipeThreshold = 50;
                this.timeThreshold = 300;
                this.init();
            }

            init() {
                this.setupSwipeGestures();
                this.setupTouchFeedback();
                this.setupKeyboardNavigation();
            }

            setupSwipeGestures() {
                const navContainer = document.querySelector('.mobile-nav-container');
                if (!navContainer) return;

                // Touch start
                navContainer.addEventListener('touchstart', (e) => {
                    this.startX = e.touches[0].clientX;
                    this.startTime = Date.now();
                    this.isSwipeActive = false;
                    navContainer.classList.add('swiping');
                }, { passive: true });

                // Touch move
                navContainer.addEventListener('touchmove', (e) => {
                    if (!this.isSwipeActive) {
                        const deltaX = Math.abs(e.touches[0].clientX - this.startX);
                        if (deltaX > 10) {
                            this.isSwipeActive = true;
                        }
                    }
                }, { passive: true });

                // Touch end
                navContainer.addEventListener('touchend', (e) => {
                    navContainer.classList.remove('swiping');
                    
                    if (!this.isSwipeActive) return;

                    const endX = e.changedTouches[0].clientX;
                    const deltaX = endX - this.startX;
                    const deltaTime = Date.now() - this.startTime;

                    if (Math.abs(deltaX) > this.swipeThreshold && deltaTime < this.timeThreshold) {
                        this.handleSwipe(deltaX > 0 ? 'right' : 'left');
                    }
                }, { passive: true });
            }

            setupTouchFeedback() {
                const navItems = document.querySelectorAll('.mobile-nav-item');
                navItems.forEach(item => {
                    item.addEventListener('touchstart', (e) => {
                        // Haptic feedback (if supported)
                        if (navigator.vibrate) {
                            navigator.vibrate(10);
                        }
                        
                        item.style.transform = 'scale(0.95)';
                    }, { passive: true });

                    item.addEventListener('touchend', (e) => {
                        item.style.transform = '';
                        
                        // Trigger click after brief delay for visual feedback
                        setTimeout(() => {
                            const index = parseInt(item.dataset.tabIndex);
                            if (!isNaN(index)) {
                                this.navigateToTab(index);
                            }
                        }, 100);
                    }, { passive: true });
                });
            }

            setupKeyboardNavigation() {
                document.addEventListener('keydown', (e) => {
                    if (e.altKey) {
                        const key = e.key;
                        const tabMap = {
                            '1': 0, '2': 1, '3': 2, '4': 3, '5': 4
                        };
                        
                        if (tabMap.hasOwnProperty(key)) {
                            e.preventDefault();
                            this.navigateToTab(tabMap[key]);
                        }
                    }
                });
            }

            handleSwipe(direction) {
                const activeTab = document.querySelector('.mobile-nav-item.active');
                if (!activeTab) return;

                const currentIndex = parseInt(activeTab.dataset.tabIndex);
                const totalTabs = document.querySelectorAll('.mobile-nav-item').length;
                
                let newIndex;
                if (direction === 'left') {
                    newIndex = (currentIndex + 1) % totalTabs;
                } else {
                    newIndex = (currentIndex - 1 + totalTabs) % totalTabs;
                }

                this.navigateToTab(newIndex);
            }

            navigateToTab(index) {
                // Update visual state
                const navItems = document.querySelectorAll('.mobile-nav-item');
                navItems.forEach((item, i) => {
                    item.classList.toggle('active', i === index);
                });

                // Trigger tab change via Streamlit
                const tabNames = ['overview', 'analytics', 'quick-add', 'chats', 'profile'];
                if (tabNames[index]) {
                    window.parent.postMessage({
                        type: 'mobile-nav-change',
                        tab: tabNames[index],
                        index: index
                    }, '*');
                }

                // Animate transition
                this.animateTabTransition(index);
            }

            animateTabTransition(index) {
                const navItems = document.querySelectorAll('.mobile-nav-item');
                const activeItem = navItems[index];
                
                if (activeItem) {
                    activeItem.style.animation = 'none';
                    activeItem.offsetHeight; // Trigger reflow
                    activeItem.style.animation = 'activeIndicator 0.3s ease-out';
                }
            }

            updateBadgeCount(tabIndex, count) {
                const navItem = document.querySelector(`[data-tab-index="${tabIndex}"]`);
                if (!navItem) return;

                let badge = navItem.querySelector('.mobile-nav-badge');
                
                if (count > 0) {
                    if (!badge) {
                        badge = document.createElement('div');
                        badge.className = 'mobile-nav-badge';
                        navItem.appendChild(badge);
                    }
                    badge.textContent = count > 99 ? '99+' : count.toString();
                    badge.style.display = 'flex';
                } else if (badge) {
                    badge.style.display = 'none';
                }
            }
        }

        // Initialize when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                new MobileNavigation();
            });
        } else {
            new MobileNavigation();
        }
    </script>
    """


def render_mobile_navigation(
    current_tab: str = "overview",
    notification_counts: Optional[Dict[str, int]] = None
) -> str:
    """
    Renders the mobile navigation component.
    
    Args:
        current_tab: Currently active tab name
        notification_counts: Dict of tab names to notification counts
        
    Returns:
        HTML string for the mobile navigation
    """
    if notification_counts is None:
        notification_counts = {}
    
    # Navigation items configuration
    nav_items = [
        {
            'id': 'overview',
            'icon': '🏠',
            'label': 'Overview',
            'alt_text': 'Business Overview Dashboard'
        },
        {
            'id': 'analytics',
            'icon': '📈',
            'label': 'Analytics',
            'alt_text': 'Performance Analytics'
        },
        {
            'id': 'quick-add',
            'icon': '➕',
            'label': 'Quick Add',
            'alt_text': 'Quick Add Lead or Property'
        },
        {
            'id': 'chats',
            'icon': '🗣️',
            'label': 'Chats',
            'alt_text': 'Active Conversations'
        },
        {
            'id': 'profile',
            'icon': '👤',
            'label': 'Profile',
            'alt_text': 'User Profile and Settings'
        }
    ]
    
    # Generate navigation items HTML
    nav_items_html = ""
    for i, item in enumerate(nav_items):
        is_active = item['id'] == current_tab
        badge_count = notification_counts.get(item['id'], 0)
        
        # Generate badge HTML if count > 0
        badge_html = ""
        if badge_count > 0:
            display_count = "99+" if badge_count > 99 else str(badge_count)
            badge_html = f'<div class="mobile-nav-badge">{display_count}</div>'
        
        active_class = "active" if is_active else ""
        
        nav_items_html += f"""
        <div class="mobile-nav-item {active_class}" 
             data-tab-index="{i}" 
             data-tab-id="{item['id']}"
             role="button"
             tabindex="0"
             aria-label="{item['alt_text']}"
             aria-selected="{str(is_active).lower()}">
            <div class="mobile-nav-icon">{item['icon']}</div>
            <div class="mobile-nav-label">{item['label']}</div>
            {badge_html}
        </div>
        """
    
    # Complete navigation HTML
    navigation_html = f"""
    <div class="mobile-nav-container" role="navigation" aria-label="Main Navigation">
        <div class="mobile-nav-brand-accent"></div>
        <div class="mobile-nav-swipe-indicator"></div>
        <div class="mobile-nav-items">
            {nav_items_html}
        </div>
    </div>
    """
    
    return navigation_html


def create_mobile_navigation_component(
    current_tab: str = "overview",
    notification_counts: Optional[Dict[str, int]] = None,
    show_on_desktop: bool = False
) -> None:
    """
    Creates and renders the complete mobile navigation component.
    
    Args:
        current_tab: Currently active tab name
        notification_counts: Optional dict of notification counts per tab
        show_on_desktop: Whether to show navigation on desktop (default: False)
    """
    # Add CSS for hiding on desktop unless explicitly shown
    desktop_css = "" if show_on_desktop else """
        @media (min-width: 768px) {
            .mobile-nav-container {
                display: none !important;
            }
        }
    """
    
    # Inject CSS and JavaScript
    st.markdown(get_mobile_navigation_css() + f"<style>{desktop_css}</style>", unsafe_allow_html=True)
    st.markdown(get_mobile_navigation_js(), unsafe_allow_html=True)
    
    # Render navigation
    navigation_html = render_mobile_navigation(current_tab, notification_counts)
    st.markdown(navigation_html, unsafe_allow_html=True)


def update_navigation_badges(notification_counts: Dict[str, int]) -> None:
    """
    Updates notification badges via JavaScript.
    
    Args:
        notification_counts: Dict mapping tab IDs to notification counts
    """
    update_script = f"""
    <script>
        const mobileNav = window.mobileNavigation;
        if (mobileNav && typeof mobileNav.updateBadgeCount === 'function') {{
            const counts = {notification_counts};
            Object.entries(counts).forEach(([tabId, count]) => {{
                const tabIndex = ['overview', 'analytics', 'quick-add', 'chats', 'profile'].indexOf(tabId);
                if (tabIndex !== -1) {{
                    mobileNav.updateBadgeCount(tabIndex, count);
                }}
            }});
        }}
    </script>
    """
    st.markdown(update_script, unsafe_allow_html=True)


# Example usage and demo function
def demo_mobile_navigation():
    """Demo function showing mobile navigation usage."""
    st.header("📱 Mobile Navigation Demo")
    
    # Demo configuration
    current_tab = st.selectbox(
        "Current Tab",
        ["overview", "analytics", "quick-add", "chats", "profile"],
        index=0
    )
    
    # Demo notification counts
    st.subheader("Notification Counts")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        overview_count = st.number_input("Overview", min_value=0, max_value=99, value=0)
        analytics_count = st.number_input("Analytics", min_value=0, max_value=99, value=2)
    
    with col2:
        quick_add_count = st.number_input("Quick Add", min_value=0, max_value=99, value=0)
        chats_count = st.number_input("Chats", min_value=0, max_value=99, value=5)
    
    with col3:
        profile_count = st.number_input("Profile", min_value=0, max_value=99, value=1)
        show_desktop = st.checkbox("Show on Desktop", value=True)
    
    notification_counts = {
        'overview': overview_count,
        'analytics': analytics_count,
        'quick-add': quick_add_count,
        'chats': chats_count,
        'profile': profile_count
    }
    
    # Render navigation
    create_mobile_navigation_component(
        current_tab=current_tab,
        notification_counts=notification_counts,
        show_on_desktop=show_desktop
    )
    
    # Instructions
    st.markdown("""
    ### 📱 Mobile Navigation Features
    
    **Touch Interactions:**
    - Tap navigation items to switch tabs
    - Swipe left/right to navigate between tabs
    - Touch targets are ≥44px for accessibility
    
    **Visual Features:**
    - Active tab indication with orange accent
    - Notification badges with counts
    - Smooth animations and transitions
    - Professional Jorge's Real Estate AI branding
    
    **Keyboard Support:**
    - Alt+1-5 to switch between tabs
    - Fully accessible with screen readers
    
    **Responsive Design:**
    - Hidden on desktop (768px+) unless enabled
    - Optimized for mobile (320px-767px)
    - Safe area handling for iPhone home indicator
    """)


if __name__ == "__main__":
    demo_mobile_navigation()