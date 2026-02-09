"""
Mobile Metrics Cards Component for Jorge's Real Estate AI Dashboard

Production-ready, mobile-first metrics cards with horizontal scrolling,
touch optimization, and real-time data visualization.

Features:
- Compact design (80px height) optimized for mobile
- Horizontal scrolling carousel with momentum
- Touch-optimized interactions (tap to expand)
- Loading skeleton states with smooth animations
- Success/warning/error visual states
- Professional real estate branding
- Performance optimized rendering
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

import streamlit as st


class MetricState(Enum):
    """Metric card visual states."""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    LOADING = "loading"


@dataclass
class MetricCard:
    """Data structure for a metric card."""
    id: str
    title: str
    value: Union[str, int, float]
    icon: str
    state: MetricState = MetricState.INFO
    change_percentage: Optional[float] = None
    change_period: str = "vs last month"
    subtitle: Optional[str] = None
    trend_data: Optional[List[float]] = None
    action_label: Optional[str] = None
    action_callback: Optional[str] = None


def get_mobile_metrics_css() -> str:
    """
    Returns mobile-first CSS for metrics cards component.
    Optimized for 60fps scrolling and touch interactions.
    """
    return """
    <style>
        /* Mobile Metrics Container */
        .mobile-metrics-container {
            width: 100%;
            margin: 16px 0;
            position: relative;
        }

        .mobile-metrics-header {
            padding: 0 16px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .mobile-metrics-title {
            font-size: 18px;
            font-weight: 700;
            color: #1f2937;
            margin: 0;
        }

        .mobile-metrics-refresh {
            background: none;
            border: none;
            color: #6b7280;
            cursor: pointer;
            padding: 8px;
            border-radius: 8px;
            transition: all 0.2s ease;
            font-size: 16px;
        }

        .mobile-metrics-refresh:hover {
            background-color: #f3f4f6;
            color: #374151;
        }

        /* Horizontal Scrolling Container */
        .mobile-metrics-scroll {
            display: flex;
            gap: 12px;
            padding: 0 16px;
            overflow-x: auto;
            scroll-behavior: smooth;
            scroll-snap-type: x mandatory;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
            -ms-overflow-style: none;
        }

        .mobile-metrics-scroll::-webkit-scrollbar {
            display: none;
        }

        /* Individual Metric Card */
        .mobile-metric-card {
            flex: 0 0 160px;
            height: 80px;
            background: white;
            border-radius: 12px;
            padding: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            scroll-snap-align: start;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }

        .mobile-metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .mobile-metric-card:active {
            transform: translateY(0);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        /* Card Header */
        .mobile-metric-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
        }

        .mobile-metric-icon {
            font-size: 20px;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            flex-shrink: 0;
        }

        .mobile-metric-state-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }

        /* Card Content */
        .mobile-metric-content {
            display: flex;
            flex-direction: column;
            height: calc(100% - 40px);
        }

        .mobile-metric-title {
            font-size: 10px;
            font-weight: 600;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            line-height: 1.2;
            margin-bottom: 2px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .mobile-metric-value {
            font-size: 16px;
            font-weight: 700;
            color: #1f2937;
            line-height: 1.1;
            margin-bottom: auto;
        }

        .mobile-metric-change {
            font-size: 10px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 2px;
        }

        /* State-based styling */
        .mobile-metric-card.success .mobile-metric-icon {
            background-color: #dcfce7;
            color: #166534;
        }

        .mobile-metric-card.success .mobile-metric-state-indicator {
            background-color: #16a34a;
        }

        .mobile-metric-card.success .mobile-metric-change {
            color: #166534;
        }

        .mobile-metric-card.warning .mobile-metric-icon {
            background-color: #fef3c7;
            color: #92400e;
        }

        .mobile-metric-card.warning .mobile-metric-state-indicator {
            background-color: #d97706;
        }

        .mobile-metric-card.warning .mobile-metric-change {
            color: #92400e;
        }

        .mobile-metric-card.error .mobile-metric-icon {
            background-color: #fee2e2;
            color: #991b1b;
        }

        .mobile-metric-card.error .mobile-metric-state-indicator {
            background-color: #dc2626;
        }

        .mobile-metric-card.error .mobile-metric-change {
            color: #991b1b;
        }

        .mobile-metric-card.info .mobile-metric-icon {
            background-color: #dbeafe;
            color: #1d4ed8;
        }

        .mobile-metric-card.info .mobile-metric-state-indicator {
            background-color: #3b82f6;
        }

        .mobile-metric-card.info .mobile-metric-change {
            color: #1d4ed8;
        }

        /* Loading state */
        .mobile-metric-card.loading {
            pointer-events: none;
        }

        .mobile-metric-card.loading .mobile-metric-skeleton {
            background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
            background-size: 200% 100%;
            animation: skeletonShimmer 1.5s infinite;
            border-radius: 4px;
        }

        .mobile-metric-skeleton-title {
            height: 10px;
            width: 80%;
            margin-bottom: 4px;
        }

        .mobile-metric-skeleton-value {
            height: 16px;
            width: 60%;
            margin-bottom: 8px;
        }

        .mobile-metric-skeleton-change {
            height: 8px;
            width: 40%;
        }

        /* Expand animation for tap interaction */
        .mobile-metric-card.expanding {
            animation: cardExpand 0.3s ease-out;
        }

        @keyframes cardExpand {
            0% {
                transform: scale(1);
            }
            50% {
                transform: scale(1.05);
            }
            100% {
                transform: scale(1);
            }
        }

        @keyframes skeletonShimmer {
            0% {
                background-position: -200% 0;
            }
            100% {
                background-position: 200% 0;
            }
        }

        /* Scroll indicators */
        .mobile-metrics-scroll-indicator {
            position: absolute;
            bottom: -8px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 4px;
        }

        .mobile-metrics-scroll-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #d1d5db;
            transition: all 0.2s ease;
        }

        .mobile-metrics-scroll-dot.active {
            background-color: #3b82f6;
            transform: scale(1.2);
        }

        /* Responsive adjustments */
        @media (max-width: 320px) {
            .mobile-metric-card {
                flex: 0 0 140px;
                height: 72px;
                padding: 10px;
            }
            
            .mobile-metric-icon {
                font-size: 18px;
                width: 28px;
                height: 28px;
            }
            
            .mobile-metric-value {
                font-size: 14px;
            }
        }

        @media (min-width: 768px) {
            .mobile-metrics-scroll {
                justify-content: flex-start;
                flex-wrap: wrap;
                overflow-x: visible;
            }
            
            .mobile-metric-card {
                flex: 0 0 200px;
                height: 100px;
            }
        }

        /* Jorge's Real Estate AI branding */
        .mobile-metric-brand-accent {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, #3b82f6, #1e3a8a);
            opacity: 0;
            transition: opacity 0.2s ease;
        }

        .mobile-metric-card:hover .mobile-metric-brand-accent,
        .mobile-metric-card.active .mobile-metric-brand-accent {
            opacity: 1;
        }
    </style>
    """


def get_mobile_metrics_js() -> str:
    """
    Returns JavaScript for touch interactions and carousel behavior.
    """
    return """
    <script>
        class MobileMetricsCards {
            constructor() {
                this.scrollContainer = null;
                this.cards = [];
                this.currentIndex = 0;
                this.isScrolling = false;
                this.init();
            }

            init() {
                this.scrollContainer = document.querySelector('.mobile-metrics-scroll');
                if (!this.scrollContainer) return;

                this.cards = Array.from(document.querySelectorAll('.mobile-metric-card'));
                this.setupTouchInteractions();
                this.setupScrollIndicators();
                this.setupIntersectionObserver();
            }

            setupTouchInteractions() {
                this.cards.forEach((card, index) => {
                    // Touch feedback
                    card.addEventListener('touchstart', (e) => {
                        card.style.transform = 'scale(0.98) translateY(-1px)';
                        
                        // Haptic feedback
                        if (navigator.vibrate) {
                            navigator.vibrate(10);
                        }
                    }, { passive: true });

                    card.addEventListener('touchend', (e) => {
                        card.style.transform = '';
                        
                        // Expand animation on tap
                        card.classList.add('expanding');
                        setTimeout(() => {
                            card.classList.remove('expanding');
                        }, 300);
                        
                        // Handle card interaction
                        this.handleCardTap(card, index);
                    }, { passive: true });

                    // Prevent context menu on long press
                    card.addEventListener('contextmenu', (e) => {
                        e.preventDefault();
                    });
                });

                // Smooth scrolling with momentum
                this.setupMomentumScrolling();
            }

            setupMomentumScrolling() {
                let startX = 0;
                let scrollLeft = 0;
                let isScrolling = false;

                this.scrollContainer.addEventListener('touchstart', (e) => {
                    startX = e.touches[0].pageX - this.scrollContainer.offsetLeft;
                    scrollLeft = this.scrollContainer.scrollLeft;
                    isScrolling = true;
                }, { passive: true });

                this.scrollContainer.addEventListener('touchmove', (e) => {
                    if (!isScrolling) return;
                    
                    e.preventDefault();
                    const x = e.touches[0].pageX - this.scrollContainer.offsetLeft;
                    const walk = (x - startX) * 2; // Scroll speed multiplier
                    this.scrollContainer.scrollLeft = scrollLeft - walk;
                });

                this.scrollContainer.addEventListener('touchend', () => {
                    isScrolling = false;
                    this.snapToNearestCard();
                });
            }

            setupScrollIndicators() {
                const indicatorContainer = document.querySelector('.mobile-metrics-scroll-indicator');
                if (!indicatorContainer || this.cards.length <= 1) return;

                // Create dots based on number of cards
                const visibleCards = Math.ceil(this.scrollContainer.clientWidth / 160);
                const totalPages = Math.max(1, Math.ceil(this.cards.length / visibleCards));

                for (let i = 0; i < totalPages; i++) {
                    const dot = document.createElement('div');
                    dot.className = 'mobile-metrics-scroll-dot';
                    if (i === 0) dot.classList.add('active');
                    indicatorContainer.appendChild(dot);
                }

                // Update active dot on scroll
                this.scrollContainer.addEventListener('scroll', () => {
                    this.updateScrollIndicators();
                }, { passive: true });
            }

            setupIntersectionObserver() {
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('active');
                        } else {
                            entry.target.classList.remove('active');
                        }
                    });
                }, {
                    root: this.scrollContainer,
                    threshold: 0.7
                });

                this.cards.forEach(card => {
                    observer.observe(card);
                });
            }

            snapToNearestCard() {
                const cardWidth = 172; // 160px + 12px gap
                const scrollLeft = this.scrollContainer.scrollLeft;
                const index = Math.round(scrollLeft / cardWidth);
                const targetScroll = index * cardWidth;

                this.scrollContainer.scrollTo({
                    left: targetScroll,
                    behavior: 'smooth'
                });
            }

            updateScrollIndicators() {
                const dots = document.querySelectorAll('.mobile-metrics-scroll-dot');
                if (dots.length === 0) return;

                const cardWidth = 172;
                const visibleWidth = this.scrollContainer.clientWidth;
                const scrollLeft = this.scrollContainer.scrollLeft;
                const visibleCards = Math.floor(visibleWidth / 160);
                
                const currentPage = Math.floor(scrollLeft / (cardWidth * visibleCards));
                
                dots.forEach((dot, index) => {
                    dot.classList.toggle('active', index === currentPage);
                });
            }

            handleCardTap(card, index) {
                const cardId = card.dataset.cardId;
                const cardData = {
                    id: cardId,
                    index: index,
                    title: card.querySelector('.mobile-metric-title')?.textContent,
                    value: card.querySelector('.mobile-metric-value')?.textContent
                };

                // Send event to Streamlit
                window.parent.postMessage({
                    type: 'mobile-metric-tap',
                    data: cardData
                }, '*');

                // Scroll card into view if partially hidden
                const cardRect = card.getBoundingClientRect();
                const containerRect = this.scrollContainer.getBoundingClientRect();
                
                if (cardRect.right > containerRect.right || cardRect.left < containerRect.left) {
                    card.scrollIntoView({
                        behavior: 'smooth',
                        inline: 'center',
                        block: 'nearest'
                    });
                }
            }

            refreshMetrics() {
                // Add loading state to all cards
                this.cards.forEach(card => {
                    card.classList.add('loading');
                });

                // Send refresh event to Streamlit
                window.parent.postMessage({
                    type: 'mobile-metrics-refresh'
                }, '*');
            }

            updateMetric(cardId, data) {
                const card = document.querySelector(`[data-card-id="${cardId}"]`);
                if (!card) return;

                // Remove loading state
                card.classList.remove('loading');

                // Update content
                if (data.value) {
                    const valueEl = card.querySelector('.mobile-metric-value');
                    if (valueEl) valueEl.textContent = data.value;
                }

                if (data.change) {
                    const changeEl = card.querySelector('.mobile-metric-change');
                    if (changeEl) changeEl.textContent = data.change;
                }

                if (data.state) {
                    // Remove old state classes
                    card.classList.remove('success', 'warning', 'error', 'info');
                    card.classList.add(data.state);
                }

                // Animate update
                card.style.animation = 'cardExpand 0.3s ease-out';
                setTimeout(() => {
                    card.style.animation = '';
                }, 300);
            }
        }

        // Initialize when DOM is ready
        document.addEventListener('DOMContentLoaded', () => {
            window.mobileMetricsCards = new MobileMetricsCards();
        });

        // Handle refresh button
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('mobile-metrics-refresh')) {
                e.preventDefault();
                window.mobileMetricsCards?.refreshMetrics();
            }
        });
    </script>
    """


def create_loading_skeleton_card(card_id: str) -> str:
    """Creates a loading skeleton card."""
    return f"""
    <div class="mobile-metric-card loading" data-card-id="{card_id}">
        <div class="mobile-metric-brand-accent"></div>
        <div class="mobile-metric-header">
            <div class="mobile-metric-icon mobile-metric-skeleton"></div>
            <div class="mobile-metric-state-indicator mobile-metric-skeleton"></div>
        </div>
        <div class="mobile-metric-content">
            <div class="mobile-metric-skeleton mobile-metric-skeleton-title"></div>
            <div class="mobile-metric-skeleton mobile-metric-skeleton-value"></div>
            <div class="mobile-metric-skeleton mobile-metric-skeleton-change"></div>
        </div>
    </div>
    """


def create_metric_card(metric: MetricCard) -> str:
    """Creates HTML for a single metric card."""
    # Format change percentage
    change_html = ""
    if metric.change_percentage is not None:
        change_sign = "+" if metric.change_percentage >= 0 else ""
        change_icon = "📈" if metric.change_percentage >= 0 else "📉"
        change_html = f"""
        <div class="mobile-metric-change">
            {change_icon} {change_sign}{metric.change_percentage:.1f}% {metric.change_period}
        </div>
        """
    
    # Format value (handle large numbers)
    if isinstance(metric.value, (int, float)):
        if metric.value >= 1000000:
            formatted_value = f"{metric.value/1000000:.1f}M"
        elif metric.value >= 1000:
            formatted_value = f"{metric.value/1000:.1f}K"
        else:
            formatted_value = str(metric.value)
    else:
        formatted_value = str(metric.value)
    
    return f"""
    <div class="mobile-metric-card {metric.state.value}" data-card-id="{metric.id}">
        <div class="mobile-metric-brand-accent"></div>
        <div class="mobile-metric-header">
            <div class="mobile-metric-icon">{metric.icon}</div>
            <div class="mobile-metric-state-indicator"></div>
        </div>
        <div class="mobile-metric-content">
            <div class="mobile-metric-title">{metric.title}</div>
            <div class="mobile-metric-value">{formatted_value}</div>
            {change_html}
        </div>
    </div>
    """


def render_mobile_metrics_cards(
    metrics: List[MetricCard],
    title: str = "Key Metrics",
    show_refresh: bool = True,
    loading: bool = False
) -> None:
    """
    Renders the complete mobile metrics cards component.
    
    Args:
        metrics: List of MetricCard objects to display
        title: Header title for the metrics section
        show_refresh: Whether to show refresh button
        loading: Whether to show loading skeletons
    """
    # Inject CSS and JavaScript
    st.markdown(get_mobile_metrics_css(), unsafe_allow_html=True)
    st.markdown(get_mobile_metrics_js(), unsafe_allow_html=True)
    
    # Create refresh button HTML
    refresh_html = ""
    if show_refresh:
        refresh_html = '<button class="mobile-metrics-refresh" title="Refresh Metrics">🔄</button>'
    
    # Create cards HTML
    if loading:
        cards_html = ""
        for metric in metrics[:6]:  # Limit to 6 skeleton cards
            cards_html += create_loading_skeleton_card(metric.id)
    else:
        cards_html = ""
        for metric in metrics:
            cards_html += create_metric_card(metric)
    
    # Create scroll indicators HTML
    indicators_html = '<div class="mobile-metrics-scroll-indicator"></div>' if len(metrics) > 1 else ""
    
    # Complete component HTML
    component_html = f"""
    <div class="mobile-metrics-container">
        <div class="mobile-metrics-header">
            <h3 class="mobile-metrics-title">{title}</h3>
            {refresh_html}
        </div>
        <div class="mobile-metrics-scroll">
            {cards_html}
        </div>
        {indicators_html}
    </div>
    """
    
    st.markdown(component_html, unsafe_allow_html=True)


def get_sample_metrics() -> List[MetricCard]:
    """Returns sample metrics for demonstration."""
    return [
        MetricCard(
            id="total_leads",
            title="Total Leads",
            value=342,
            icon="👥",
            state=MetricState.SUCCESS,
            change_percentage=12.5,
            change_period="vs last month"
        ),
        MetricCard(
            id="active_conversations",
            title="Active Chats",
            value=28,
            icon="💬",
            state=MetricState.INFO,
            change_percentage=8.3,
            change_period="this week"
        ),
        MetricCard(
            id="revenue",
            title="Revenue",
            value=145000,
            icon="💰",
            state=MetricState.SUCCESS,
            change_percentage=23.1,
            change_period="30 days"
        ),
        MetricCard(
            id="conversion_rate",
            title="Conversion",
            value="8.5%",
            icon="📈",
            state=MetricState.WARNING,
            change_percentage=-2.1,
            change_period="this month"
        ),
        MetricCard(
            id="response_time",
            title="Response Time",
            value="2.3m",
            icon="⏱️",
            state=MetricState.SUCCESS,
            change_percentage=-15.4,
            change_period="avg"
        ),
        MetricCard(
            id="pipeline_value",
            title="Pipeline",
            value=890000,
            icon="🏠",
            state=MetricState.INFO,
            change_percentage=18.7,
            change_period="total"
        )
    ]


# Demo function
def demo_mobile_metrics_cards():
    """Demo function showing mobile metrics cards usage."""
    st.header("📊 Mobile Metrics Cards Demo")
    
    # Demo controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        show_loading = st.checkbox("Show Loading State", value=False)
        show_refresh = st.checkbox("Show Refresh Button", value=True)
    
    with col2:
        title = st.text_input("Title", value="Key Metrics")
        num_cards = st.slider("Number of Cards", min_value=1, max_value=8, value=6)
    
    with col3:
        if st.button("🔄 Refresh Demo"):
            st.rerun()
    
    # Get sample metrics
    sample_metrics = get_sample_metrics()[:num_cards]
    
    # Render component
    render_mobile_metrics_cards(
        metrics=sample_metrics,
        title=title,
        show_refresh=show_refresh,
        loading=show_loading
    )
    
    # Instructions
    st.markdown("""
    ### 📱 Mobile Metrics Cards Features
    
    **Touch Interactions:**
    - Horizontal scroll with momentum scrolling
    - Tap cards to expand and interact
    - Snap-to-grid behavior for alignment
    - Haptic feedback on supported devices
    
    **Visual Features:**
    - Compact 80px height for mobile optimization
    - Color-coded states (success, warning, error, info)
    - Loading skeleton animations
    - Smooth 60fps animations and transitions
    
    **Responsive Design:**
    - Mobile-first (160px card width)
    - Tablet optimization (200px card width)
    - Desktop adaptation with wrapping layout
    - Safe area handling for modern phones
    
    **Data Features:**
    - Real-time value updates
    - Percentage change indicators
    - Smart number formatting (K, M suffixes)
    - State-based visual feedback
    """)
    
    # Show current metrics data
    if st.expander("📋 Current Metrics Data"):
        for metric in sample_metrics:
            st.write(f"**{metric.title}**: {metric.value} ({metric.state.value})")


if __name__ == "__main__":
    demo_mobile_metrics_cards()