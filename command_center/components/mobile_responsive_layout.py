"""
Mobile Responsive Layout Utilities for Jorge's Real Estate AI Dashboard

Production-ready responsive layout system with mobile-first design,
adaptive breakpoints, and touch-friendly spacing optimized for real estate workflows.

Features:
- Breakpoint system: 320px (mobile), 768px (tablet), 1024px (desktop)
- Adaptive column layouts with intelligent wrapping
- Touch-friendly spacing system (8px grid)
- Mobile-first containers with safe area handling
- Professional Jorge's Real Estate AI styling
- Performance-optimized CSS with minimal footprint
"""

import streamlit as st
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass


class BreakpointSize(Enum):
    """Responsive breakpoint sizes."""
    MOBILE = "mobile"      # 320px - 767px
    TABLET = "tablet"      # 768px - 1023px
    DESKTOP = "desktop"    # 1024px+


class ColumnLayout(Enum):
    """Predefined column layouts."""
    SINGLE = "single"           # 1 column
    HALF = "half"              # 2 columns
    THIRD = "third"            # 3 columns
    QUARTER = "quarter"        # 4 columns
    SIDEBAR_MAIN = "sidebar"   # Sidebar + main content
    HERO_GRID = "hero"         # Hero layout with grid


@dataclass
class ResponsiveConfig:
    """Configuration for responsive layouts."""
    mobile_columns: int = 1
    tablet_columns: int = 2
    desktop_columns: int = 3
    gap: str = "16px"
    padding: str = "16px"
    max_width: str = "1200px"
    center: bool = True


def get_responsive_layout_css() -> str:
    """
    Returns comprehensive CSS for responsive layout system.
    Mobile-first approach with Jorge's Real Estate AI styling.
    """
    return """
    <style>
        /* =================
           RESPONSIVE SYSTEM
           ================= */

        /* CSS Custom Properties for Dynamic Theming */
        :root {
            /* Jorge's Real Estate AI Color Palette */
            --jorge-primary: #3b82f6;
            --jorge-secondary: #1e3a8a;
            --jorge-accent: #f59e0b;
            --jorge-success: #10b981;
            --jorge-warning: #f59e0b;
            --jorge-error: #ef4444;
            --jorge-background: #ffffff;
            --jorge-surface: #f8fafc;
            --jorge-text: #1f2937;
            --jorge-text-secondary: #6b7280;
            --jorge-border: #e5e7eb;
            
            /* Spacing System (8px grid) */
            --spacing-xs: 4px;
            --spacing-sm: 8px;
            --spacing-md: 16px;
            --spacing-lg: 24px;
            --spacing-xl: 32px;
            --spacing-2xl: 48px;
            --spacing-3xl: 64px;
            
            /* Breakpoints */
            --mobile-max: 767px;
            --tablet-min: 768px;
            --tablet-max: 1023px;
            --desktop-min: 1024px;
            
            /* Touch Targets */
            --touch-target-min: 44px;
            --touch-target-optimal: 48px;
            
            /* Border Radius */
            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --radius-xl: 16px;
            
            /* Shadows */
            --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1);
            --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.1);
            --shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.1);
            --shadow-xl: 0 8px 24px rgba(0, 0, 0, 0.15);
        }

        /* =================
           BASE CONTAINERS
           ================= */

        .responsive-container {
            width: 100%;
            margin: 0 auto;
            padding: 0 var(--spacing-md);
            box-sizing: border-box;
        }

        .responsive-container.max-width-sm {
            max-width: 640px;
        }

        .responsive-container.max-width-md {
            max-width: 768px;
        }

        .responsive-container.max-width-lg {
            max-width: 1024px;
        }

        .responsive-container.max-width-xl {
            max-width: 1200px;
        }

        .responsive-container.max-width-2xl {
            max-width: 1400px;
        }

        .responsive-container.full-width {
            max-width: none;
        }

        /* Safe Area Handling for Mobile Devices */
        .responsive-container.safe-area {
            padding-left: max(var(--spacing-md), env(safe-area-inset-left));
            padding-right: max(var(--spacing-md), env(safe-area-inset-right));
            padding-top: max(var(--spacing-md), env(safe-area-inset-top));
            padding-bottom: max(var(--spacing-md), env(safe-area-inset-bottom));
        }

        /* =================
           GRID SYSTEM
           ================= */

        .responsive-grid {
            display: grid;
            gap: var(--spacing-md);
            width: 100%;
        }

        .responsive-grid.gap-xs { gap: var(--spacing-xs); }
        .responsive-grid.gap-sm { gap: var(--spacing-sm); }
        .responsive-grid.gap-md { gap: var(--spacing-md); }
        .responsive-grid.gap-lg { gap: var(--spacing-lg); }
        .responsive-grid.gap-xl { gap: var(--spacing-xl); }

        /* Mobile-First Grid Columns (320px+) */
        .responsive-grid.cols-1 { grid-template-columns: 1fr; }
        .responsive-grid.cols-2 { grid-template-columns: repeat(2, 1fr); }
        .responsive-grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
        .responsive-grid.cols-4 { grid-template-columns: repeat(4, 1fr); }

        /* Auto-fit columns for dynamic layouts */
        .responsive-grid.auto-fit-sm { 
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
        }
        .responsive-grid.auto-fit-md { 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
        }
        .responsive-grid.auto-fit-lg { 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
        }
        .responsive-grid.auto-fit-xl { 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
        }

        /* Tablet Responsive (768px+) */
        @media (min-width: 768px) {
            .responsive-container {
                padding: 0 var(--spacing-lg);
            }
            
            .responsive-grid {
                gap: var(--spacing-lg);
            }
            
            .responsive-grid.tablet-cols-1 { grid-template-columns: 1fr; }
            .responsive-grid.tablet-cols-2 { grid-template-columns: repeat(2, 1fr); }
            .responsive-grid.tablet-cols-3 { grid-template-columns: repeat(3, 1fr); }
            .responsive-grid.tablet-cols-4 { grid-template-columns: repeat(4, 1fr); }
            .responsive-grid.tablet-cols-5 { grid-template-columns: repeat(5, 1fr); }
            .responsive-grid.tablet-cols-6 { grid-template-columns: repeat(6, 1fr); }
        }

        /* Desktop Responsive (1024px+) */
        @media (min-width: 1024px) {
            .responsive-container {
                padding: 0 var(--spacing-xl);
            }
            
            .responsive-grid {
                gap: var(--spacing-xl);
            }
            
            .responsive-grid.desktop-cols-1 { grid-template-columns: 1fr; }
            .responsive-grid.desktop-cols-2 { grid-template-columns: repeat(2, 1fr); }
            .responsive-grid.desktop-cols-3 { grid-template-columns: repeat(3, 1fr); }
            .responsive-grid.desktop-cols-4 { grid-template-columns: repeat(4, 1fr); }
            .responsive-grid.desktop-cols-5 { grid-template-columns: repeat(5, 1fr); }
            .responsive-grid.desktop-cols-6 { grid-template-columns: repeat(6, 1fr); }
            .responsive-grid.desktop-cols-8 { grid-template-columns: repeat(8, 1fr); }
            .responsive-grid.desktop-cols-12 { grid-template-columns: repeat(12, 1fr); }
        }

        /* =================
           FLEXBOX LAYOUTS
           ================= */

        .responsive-flex {
            display: flex;
            gap: var(--spacing-md);
            width: 100%;
        }

        .responsive-flex.direction-column { flex-direction: column; }
        .responsive-flex.direction-row { flex-direction: row; }
        .responsive-flex.wrap { flex-wrap: wrap; }
        .responsive-flex.nowrap { flex-wrap: nowrap; }

        .responsive-flex.justify-start { justify-content: flex-start; }
        .responsive-flex.justify-center { justify-content: center; }
        .responsive-flex.justify-end { justify-content: flex-end; }
        .responsive-flex.justify-between { justify-content: space-between; }
        .responsive-flex.justify-around { justify-content: space-around; }

        .responsive-flex.align-start { align-items: flex-start; }
        .responsive-flex.align-center { align-items: center; }
        .responsive-flex.align-end { align-items: flex-end; }
        .responsive-flex.align-stretch { align-items: stretch; }

        /* Responsive Flex Direction */
        @media (max-width: 767px) {
            .responsive-flex.mobile-column { flex-direction: column; }
            .responsive-flex.mobile-row { flex-direction: row; }
        }

        @media (min-width: 768px) and (max-width: 1023px) {
            .responsive-flex.tablet-column { flex-direction: column; }
            .responsive-flex.tablet-row { flex-direction: row; }
        }

        @media (min-width: 1024px) {
            .responsive-flex.desktop-column { flex-direction: column; }
            .responsive-flex.desktop-row { flex-direction: row; }
        }

        /* =================
           SPACING UTILITIES
           ================= */

        /* Margin Classes */
        .m-0 { margin: 0; }
        .m-xs { margin: var(--spacing-xs); }
        .m-sm { margin: var(--spacing-sm); }
        .m-md { margin: var(--spacing-md); }
        .m-lg { margin: var(--spacing-lg); }
        .m-xl { margin: var(--spacing-xl); }
        .m-2xl { margin: var(--spacing-2xl); }

        .mt-0 { margin-top: 0; }
        .mt-xs { margin-top: var(--spacing-xs); }
        .mt-sm { margin-top: var(--spacing-sm); }
        .mt-md { margin-top: var(--spacing-md); }
        .mt-lg { margin-top: var(--spacing-lg); }
        .mt-xl { margin-top: var(--spacing-xl); }

        .mb-0 { margin-bottom: 0; }
        .mb-xs { margin-bottom: var(--spacing-xs); }
        .mb-sm { margin-bottom: var(--spacing-sm); }
        .mb-md { margin-bottom: var(--spacing-md); }
        .mb-lg { margin-bottom: var(--spacing-lg); }
        .mb-xl { margin-bottom: var(--spacing-xl); }

        .ml-0 { margin-left: 0; }
        .ml-auto { margin-left: auto; }
        .mr-0 { margin-right: 0; }
        .mr-auto { margin-right: auto; }

        .mx-0 { margin-left: 0; margin-right: 0; }
        .mx-auto { margin-left: auto; margin-right: auto; }

        /* Padding Classes */
        .p-0 { padding: 0; }
        .p-xs { padding: var(--spacing-xs); }
        .p-sm { padding: var(--spacing-sm); }
        .p-md { padding: var(--spacing-md); }
        .p-lg { padding: var(--spacing-lg); }
        .p-xl { padding: var(--spacing-xl); }

        .pt-0 { padding-top: 0; }
        .pt-xs { padding-top: var(--spacing-xs); }
        .pt-sm { padding-top: var(--spacing-sm); }
        .pt-md { padding-top: var(--spacing-md); }
        .pt-lg { padding-top: var(--spacing-lg); }

        .pb-0 { padding-bottom: 0; }
        .pb-xs { padding-bottom: var(--spacing-xs); }
        .pb-sm { padding-bottom: var(--spacing-sm); }
        .pb-md { padding-bottom: var(--spacing-md); }
        .pb-lg { padding-bottom: var(--spacing-lg); }

        .px-0 { padding-left: 0; padding-right: 0; }
        .px-xs { padding-left: var(--spacing-xs); padding-right: var(--spacing-xs); }
        .px-sm { padding-left: var(--spacing-sm); padding-right: var(--spacing-sm); }
        .px-md { padding-left: var(--spacing-md); padding-right: var(--spacing-md); }
        .px-lg { padding-left: var(--spacing-lg); padding-right: var(--spacing-lg); }

        .py-0 { padding-top: 0; padding-bottom: 0; }
        .py-xs { padding-top: var(--spacing-xs); padding-bottom: var(--spacing-xs); }
        .py-sm { padding-top: var(--spacing-sm); padding-bottom: var(--spacing-sm); }
        .py-md { padding-top: var(--spacing-md); padding-bottom: var(--spacing-md); }
        .py-lg { padding-top: var(--spacing-lg); padding-bottom: var(--spacing-lg); }

        /* =================
           CARDS & SURFACES
           ================= */

        .responsive-card {
            background: var(--jorge-background);
            border: 1px solid var(--jorge-border);
            border-radius: var(--radius-lg);
            padding: var(--spacing-md);
            box-shadow: var(--shadow-sm);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }

        .responsive-card:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-1px);
        }

        .responsive-card.elevated {
            box-shadow: var(--shadow-md);
        }

        .responsive-card.elevated:hover {
            box-shadow: var(--shadow-lg);
        }

        .responsive-card.interactive {
            cursor: pointer;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }

        .responsive-card.interactive:active {
            transform: translateY(0);
            box-shadow: var(--shadow-sm);
        }

        /* Card Header */
        .responsive-card-header {
            margin: calc(-1 * var(--spacing-md)) calc(-1 * var(--spacing-md)) var(--spacing-md);
            padding: var(--spacing-md);
            background: var(--jorge-surface);
            border-bottom: 1px solid var(--jorge-border);
            font-weight: 600;
            color: var(--jorge-text);
        }

        /* Card with Jorge's branding accent */
        .responsive-card.jorge-branded::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--jorge-primary), var(--jorge-accent));
        }

        /* =================
           BUTTONS & TOUCHES
           ================= */

        .responsive-button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: var(--spacing-xs);
            min-height: var(--touch-target-min);
            min-width: var(--touch-target-min);
            padding: var(--spacing-sm) var(--spacing-md);
            border: none;
            border-radius: var(--radius-md);
            font-weight: 600;
            font-size: 14px;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            user-select: none;
            -webkit-tap-highlight-color: transparent;
            white-space: nowrap;
        }

        .responsive-button.primary {
            background: var(--jorge-primary);
            color: white;
        }

        .responsive-button.primary:hover {
            background: #2563eb;
            transform: translateY(-1px);
        }

        .responsive-button.secondary {
            background: var(--jorge-surface);
            color: var(--jorge-text);
            border: 1px solid var(--jorge-border);
        }

        .responsive-button.secondary:hover {
            background: #f1f5f9;
        }

        .responsive-button:active {
            transform: translateY(0);
        }

        /* Large touch-friendly buttons for mobile */
        .responsive-button.large {
            min-height: var(--touch-target-optimal);
            padding: var(--spacing-md) var(--spacing-lg);
            font-size: 16px;
        }

        /* =================
           VISIBILITY UTILITIES
           ================= */

        .hidden-mobile {
            display: block;
        }

        .hidden-tablet {
            display: block;
        }

        .hidden-desktop {
            display: block;
        }

        .show-mobile {
            display: none;
        }

        .show-tablet {
            display: none;
        }

        .show-desktop {
            display: none;
        }

        @media (max-width: 767px) {
            .hidden-mobile { display: none !important; }
            .show-mobile { display: block !important; }
        }

        @media (min-width: 768px) and (max-width: 1023px) {
            .hidden-tablet { display: none !important; }
            .show-tablet { display: block !important; }
        }

        @media (min-width: 1024px) {
            .hidden-desktop { display: none !important; }
            .show-desktop { display: block !important; }
        }

        /* =================
           TYPOGRAPHY
           ================= */

        .responsive-text-xs { font-size: 12px; line-height: 1.4; }
        .responsive-text-sm { font-size: 14px; line-height: 1.4; }
        .responsive-text-base { font-size: 16px; line-height: 1.5; }
        .responsive-text-lg { font-size: 18px; line-height: 1.5; }
        .responsive-text-xl { font-size: 20px; line-height: 1.5; }
        .responsive-text-2xl { font-size: 24px; line-height: 1.4; }
        .responsive-text-3xl { font-size: 30px; line-height: 1.3; }

        .text-center { text-align: center; }
        .text-left { text-align: left; }
        .text-right { text-align: right; }

        .font-normal { font-weight: 400; }
        .font-medium { font-weight: 500; }
        .font-semibold { font-weight: 600; }
        .font-bold { font-weight: 700; }

        .text-primary { color: var(--jorge-primary); }
        .text-secondary { color: var(--jorge-text-secondary); }
        .text-success { color: var(--jorge-success); }
        .text-warning { color: var(--jorge-warning); }
        .text-error { color: var(--jorge-error); }

        /* Responsive Typography */
        @media (min-width: 768px) {
            .responsive-text-2xl { font-size: 28px; }
            .responsive-text-3xl { font-size: 36px; }
        }

        @media (min-width: 1024px) {
            .responsive-text-2xl { font-size: 32px; }
            .responsive-text-3xl { font-size: 42px; }
        }

        /* =================
           SPECIAL LAYOUTS
           ================= */

        /* Hero Section Layout */
        .hero-layout {
            display: grid;
            grid-template-columns: 1fr;
            gap: var(--spacing-lg);
            align-items: center;
            min-height: 400px;
            padding: var(--spacing-2xl) var(--spacing-md);
            background: linear-gradient(135deg, var(--jorge-surface) 0%, #e2e8f0 100%);
            border-radius: var(--radius-xl);
            position: relative;
            overflow: hidden;
        }

        @media (min-width: 768px) {
            .hero-layout {
                grid-template-columns: 1fr 1fr;
                min-height: 500px;
                padding: var(--spacing-3xl) var(--spacing-xl);
            }
        }

        /* Sidebar Layout */
        .sidebar-layout {
            display: grid;
            grid-template-columns: 1fr;
            gap: var(--spacing-lg);
        }

        @media (min-width: 768px) {
            .sidebar-layout {
                grid-template-columns: 300px 1fr;
            }
        }

        @media (min-width: 1024px) {
            .sidebar-layout {
                grid-template-columns: 350px 1fr;
            }
        }

        /* Dashboard Grid Layout */
        .dashboard-layout {
            display: grid;
            grid-template-columns: 1fr;
            gap: var(--spacing-md);
        }

        @media (min-width: 768px) {
            .dashboard-layout {
                grid-template-columns: repeat(2, 1fr);
                gap: var(--spacing-lg);
            }
        }

        @media (min-width: 1024px) {
            .dashboard-layout {
                grid-template-columns: repeat(3, 1fr);
                gap: var(--spacing-xl);
            }
        }

        @media (min-width: 1200px) {
            .dashboard-layout {
                grid-template-columns: repeat(4, 1fr);
            }
        }
    </style>
    """


def create_responsive_container(
    content: str,
    max_width: str = "xl",
    safe_area: bool = True,
    center: bool = True,
    padding: Optional[str] = None
) -> str:
    """
    Creates a responsive container with Jorge's Real Estate AI styling.
    
    Args:
        content: HTML content to wrap
        max_width: Container max width (sm, md, lg, xl, 2xl, full)
        safe_area: Enable safe area padding for mobile devices
        center: Center the container
        padding: Custom padding class
        
    Returns:
        HTML string for responsive container
    """
    classes = ["responsive-container", f"max-width-{max_width}"]
    
    if safe_area:
        classes.append("safe-area")
    
    if padding:
        classes.append(padding)
    
    class_str = " ".join(classes)
    
    return f'<div class="{class_str}">{content}</div>'


def create_responsive_grid(
    items: List[str],
    mobile_cols: int = 1,
    tablet_cols: int = 2,
    desktop_cols: int = 3,
    gap: str = "md",
    auto_fit: bool = False,
    auto_fit_min: str = "200px"
) -> str:
    """
    Creates a responsive grid layout.
    
    Args:
        items: List of HTML content for grid items
        mobile_cols: Number of columns on mobile
        tablet_cols: Number of columns on tablet
        desktop_cols: Number of columns on desktop
        gap: Gap size (xs, sm, md, lg, xl)
        auto_fit: Use auto-fit columns instead of fixed columns
        auto_fit_min: Minimum column width for auto-fit
        
    Returns:
        HTML string for responsive grid
    """
    if auto_fit:
        # Determine auto-fit class based on min width
        auto_fit_classes = {
            "150px": "auto-fit-sm",
            "200px": "auto-fit-md", 
            "250px": "auto-fit-lg",
            "300px": "auto-fit-xl"
        }
        auto_fit_class = auto_fit_classes.get(auto_fit_min, "auto-fit-md")
        classes = [f"responsive-grid {auto_fit_class} gap-{gap}"]
    else:
        classes = [
            f"responsive-grid cols-{mobile_cols}",
            f"tablet-cols-{tablet_cols}",
            f"desktop-cols-{desktop_cols}",
            f"gap-{gap}"
        ]
    
    class_str = " ".join(classes)
    items_html = "".join(f"<div>{item}</div>" for item in items)
    
    return f'<div class="{class_str}">{items_html}</div>'


def create_responsive_flex(
    items: List[str],
    direction: str = "row",
    wrap: bool = True,
    justify: str = "start",
    align: str = "center",
    gap: str = "md",
    responsive_direction: Optional[Dict[str, str]] = None
) -> str:
    """
    Creates a responsive flexbox layout.
    
    Args:
        items: List of HTML content for flex items
        direction: Flex direction (row, column)
        wrap: Enable flex wrap
        justify: Justify content (start, center, end, between, around)
        align: Align items (start, center, end, stretch)
        gap: Gap size (xs, sm, md, lg, xl)
        responsive_direction: Dict of breakpoint directions
        
    Returns:
        HTML string for responsive flex
    """
    classes = [
        f"responsive-flex direction-{direction}",
        "wrap" if wrap else "nowrap",
        f"justify-{justify}",
        f"align-{align}",
        f"gap-{gap}"
    ]
    
    if responsive_direction:
        for breakpoint, resp_direction in responsive_direction.items():
            classes.append(f"{breakpoint}-{resp_direction}")
    
    class_str = " ".join(classes)
    items_html = "".join(f"<div>{item}</div>" for item in items)
    
    return f'<div class="{class_str}">{items_html}</div>'


def create_responsive_card(
    content: str,
    title: Optional[str] = None,
    elevated: bool = False,
    interactive: bool = False,
    jorge_branded: bool = True,
    padding: str = "md"
) -> str:
    """
    Creates a responsive card component.
    
    Args:
        content: Card content HTML
        title: Optional card title
        elevated: Add elevated shadow
        interactive: Make card interactive/clickable
        jorge_branded: Add Jorge's brand accent
        padding: Padding size
        
    Returns:
        HTML string for responsive card
    """
    classes = ["responsive-card"]
    
    if elevated:
        classes.append("elevated")
    if interactive:
        classes.append("interactive")
    if jorge_branded:
        classes.append("jorge-branded")
    
    class_str = " ".join(classes)
    
    header_html = ""
    if title:
        header_html = f'<div class="responsive-card-header">{title}</div>'
    
    return f"""
    <div class="{class_str}">
        {header_html}
        <div class="p-{padding}">
            {content}
        </div>
    </div>
    """


def create_hero_section(
    title: str,
    subtitle: str,
    content: str,
    background_gradient: bool = True
) -> str:
    """Creates a responsive hero section layout."""
    bg_class = "hero-layout" if background_gradient else "hero-layout-plain"
    
    return f"""
    <div class="{bg_class}">
        <div>
            <h1 class="responsive-text-3xl font-bold text-primary mb-md">{title}</h1>
            <p class="responsive-text-lg text-secondary mb-lg">{subtitle}</p>
        </div>
        <div>{content}</div>
    </div>
    """


def create_dashboard_layout(items: List[str]) -> str:
    """Creates a responsive dashboard grid layout."""
    items_html = "".join(f"<div>{item}</div>" for item in items)
    return f'<div class="dashboard-layout">{items_html}</div>'


def create_sidebar_layout(sidebar_content: str, main_content: str) -> str:
    """Creates a responsive sidebar layout."""
    return f"""
    <div class="sidebar-layout">
        <div class="responsive-card">
            {sidebar_content}
        </div>
        <div>
            {main_content}
        </div>
    </div>
    """


def apply_responsive_layout_system():
    """Applies the complete responsive layout system to the Streamlit app."""
    st.markdown(get_responsive_layout_css(), unsafe_allow_html=True)


# Demo function
def demo_responsive_layouts():
    """Demo function showing all responsive layout components."""
    st.header("📱 Mobile Responsive Layout System Demo")
    
    # Apply layout system
    apply_responsive_layout_system()
    
    # Demo controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        container_width = st.selectbox("Container Width", ["sm", "md", "lg", "xl", "2xl", "full"])
        mobile_cols = st.slider("Mobile Columns", 1, 4, 1)
        
    with col2:
        tablet_cols = st.slider("Tablet Columns", 1, 6, 2)
        desktop_cols = st.slider("Desktop Columns", 1, 6, 3)
        
    with col3:
        gap_size = st.selectbox("Gap Size", ["xs", "sm", "md", "lg", "xl"], index=2)
        auto_fit = st.checkbox("Auto-fit Columns", False)
    
    # Hero section demo
    hero_content = create_responsive_card(
        """
        <div class="text-center">
            <h3 class="responsive-text-xl font-semibold mb-sm">Get Started Today</h3>
            <p class="text-secondary mb-md">Transform your real estate business with AI-powered insights.</p>
            <button class="responsive-button primary large">Start Free Trial</button>
        </div>
        """,
        jorge_branded=True
    )
    
    hero_html = create_hero_section(
        title="Jorge's Real Estate AI",
        subtitle="Professional AI-powered platform for modern real estate professionals",
        content=hero_content
    )
    
    st.markdown(hero_html, unsafe_allow_html=True)
    
    # Grid layout demo
    st.subheader("📊 Responsive Grid Layout")
    
    sample_cards = [
        create_responsive_card(
            f"""
            <div class="text-center">
                <div style="font-size: 32px; margin-bottom: 8px;">📈</div>
                <h4 class="font-semibold mb-xs">Analytics</h4>
                <p class="text-sm text-secondary">Real-time insights</p>
            </div>
            """,
            interactive=True,
            jorge_branded=True
        ) for i in range(8)
    ]
    
    if auto_fit:
        grid_html = create_responsive_grid(
            items=sample_cards,
            gap=gap_size,
            auto_fit=True,
            auto_fit_min="200px"
        )
    else:
        grid_html = create_responsive_grid(
            items=sample_cards,
            mobile_cols=mobile_cols,
            tablet_cols=tablet_cols,
            desktop_cols=desktop_cols,
            gap=gap_size
        )
    
    container_html = create_responsive_container(
        content=grid_html,
        max_width=container_width
    )
    
    st.markdown(container_html, unsafe_allow_html=True)
    
    # Flex layout demo
    st.subheader("🔄 Responsive Flex Layout")
    
    flex_items = [
        '<div class="responsive-button primary">Primary Action</div>',
        '<div class="responsive-button secondary">Secondary</div>',
        '<div class="responsive-button secondary">Tertiary</div>'
    ]
    
    flex_html = create_responsive_flex(
        items=flex_items,
        justify="center",
        wrap=True,
        responsive_direction={"mobile": "column", "tablet": "row"}
    )
    
    st.markdown(create_responsive_container(flex_html), unsafe_allow_html=True)
    
    # Sidebar layout demo
    st.subheader("📋 Sidebar Layout")
    
    sidebar_content = """
    <h4 class="font-semibold mb-md">Quick Stats</h4>
    <div class="mb-sm">
        <div class="text-xs text-secondary">Total Leads</div>
        <div class="font-bold text-primary">1,234</div>
    </div>
    <div class="mb-sm">
        <div class="text-xs text-secondary">Active Properties</div>
        <div class="font-bold text-success">89</div>
    </div>
    <div>
        <div class="text-xs text-secondary">Revenue</div>
        <div class="font-bold text-warning">$234K</div>
    </div>
    """
    
    main_content = create_responsive_card(
        """
        <h4 class="font-semibold mb-md">Main Dashboard Content</h4>
        <p class="text-secondary mb-md">This area contains the primary dashboard content that adapts to different screen sizes.</p>
        <div class="responsive-flex justify-between">
            <button class="responsive-button primary">Primary Action</button>
            <button class="responsive-button secondary">Secondary</button>
        </div>
        """,
        jorge_branded=True
    )
    
    sidebar_html = create_sidebar_layout(sidebar_content, main_content)
    
    st.markdown(create_responsive_container(sidebar_html), unsafe_allow_html=True)
    
    # Responsive utilities demo
    st.subheader("👁️ Visibility Utilities")
    
    visibility_demo = """
    <div class="responsive-card jorge-branded">
        <div class="show-mobile text-center p-lg">
            <h4 class="text-primary font-semibold">📱 Mobile View</h4>
            <p class="text-sm">This content only shows on mobile devices (≤767px)</p>
        </div>
        
        <div class="show-tablet text-center p-lg">
            <h4 class="text-primary font-semibold">📱 Tablet View</h4>
            <p class="text-sm">This content only shows on tablets (768px-1023px)</p>
        </div>
        
        <div class="show-desktop text-center p-lg">
            <h4 class="text-primary font-semibold">🖥️ Desktop View</h4>
            <p class="text-sm">This content only shows on desktop (≥1024px)</p>
        </div>
        
        <div class="hidden-mobile text-center p-lg">
            <h4 class="text-secondary font-semibold">Hidden on Mobile</h4>
            <p class="text-sm">This content is hidden on mobile devices</p>
        </div>
    </div>
    """
    
    st.markdown(create_responsive_container(visibility_demo), unsafe_allow_html=True)
    
    # Typography demo
    st.subheader("✏️ Responsive Typography")
    
    typography_demo = """
    <div class="responsive-card jorge-branded">
        <h1 class="responsive-text-3xl font-bold text-primary mb-md">Heading 1 (Responsive)</h1>
        <h2 class="responsive-text-2xl font-semibold text-secondary mb-md">Heading 2 (Responsive)</h2>
        <h3 class="responsive-text-xl font-medium mb-md">Heading 3</h3>
        <p class="responsive-text-base mb-md">This is base text that maintains optimal readability across all devices with proper line height and spacing.</p>
        <p class="responsive-text-sm text-secondary">Small text for captions and secondary information.</p>
    </div>
    """
    
    st.markdown(create_responsive_container(typography_demo), unsafe_allow_html=True)
    
    # Instructions
    st.markdown("""
    ### 📱 Responsive Layout Features
    
    **Breakpoint System:**
    - **Mobile**: 320px - 767px (1-2 columns typically)
    - **Tablet**: 768px - 1023px (2-3 columns typically)  
    - **Desktop**: 1024px+ (3+ columns typically)
    
    **Grid System:**
    - Mobile-first responsive grid with intelligent column wrapping
    - Auto-fit columns for dynamic layouts
    - Configurable gaps and spacing
    - Touch-friendly sizing on mobile
    
    **Spacing System:**
    - 8px grid system for consistent spacing
    - CSS custom properties for easy theming
    - Safe area handling for modern mobile devices
    - Touch target optimization (≥44px)
    
    **Jorge's Real Estate AI Styling:**
    - Professional color palette
    - Branded card accents
    - Consistent component styling
    - Performance-optimized CSS
    
    **Layout Components:**
    - Responsive containers with max-width constraints
    - Flexible grid and flexbox systems
    - Card components with hover states
    - Hero sections and dashboard layouts
    - Sidebar layouts with mobile adaptation
    
    **Utility Classes:**
    - Visibility utilities (show/hide by breakpoint)
    - Spacing utilities (margin/padding)
    - Typography utilities (responsive text sizing)
    - Color utilities (brand colors)
    """)


if __name__ == "__main__":
    demo_responsive_layouts()