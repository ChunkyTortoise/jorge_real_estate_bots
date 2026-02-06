"""
Seller Bot Q1-Q4 Pipeline Visualization - Jorge's Seller Qualification Dashboard

Enhanced seller bot visualization with:
- Q1-Q4 qualification flow with conversion funnel
- Temperature-based seller categorization (HOT/WARM/COLD)
- CMA automation triggers with commission predictions
- Active conversation management
- Performance analytics and trends

Author: Claude Code Assistant
Created: 2026-01-23
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.seller_bot.jorge_seller_bot import create_seller_bot, SellerStatus
from bots.shared.logger import get_logger

logger = get_logger(__name__)


class SellerBotPipelineViz:
    """
    Seller Bot Q1-Q4 Pipeline Visualization

    Features:
    - Q1-Q4 conversion funnel with drop-off analysis
    - Temperature distribution with CMA triggers
    - Active conversations table with action buttons
    - Commission potential tracking
    - Performance trends and analytics
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.seller_bot = create_seller_bot()

    def render_seller_pipeline_section(self, location_id: str) -> None:
        """
        Render the complete seller bot pipeline section.

        Args:
            location_id: GHL location ID for data filtering
        """
        # Section header with CMA automation controls
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown("""
            <h3 style='margin-bottom: 8px;'>🏠 Seller Bot Q1-Q4 Pipeline</h3>
            <p style='color: #6b7280; margin-top: 0; margin-bottom: 20px;'>Jorge's confrontational qualification system with CMA automation</p>
            """, unsafe_allow_html=True)

        with col2:
            if st.button("🚀 Auto-Generate CMAs", help="Generate CMAs for all Q4 qualified sellers", use_container_width=True):
                self._trigger_bulk_cma_generation()

        # Load seller pipeline data
        pipeline_data = self._load_seller_pipeline_data(location_id)

        if not pipeline_data:
            self._render_loading_state()
            return

        # First row: Pipeline funnel and temperature distribution
        col1, col2 = st.columns([2, 1])

        with col1:
            self._render_q1_q4_funnel(pipeline_data)

        with col2:
            self._render_temperature_distribution(pipeline_data)

        # Second row: Active conversations and commission tracking
        col1, col2 = st.columns(2)

        with col1:
            self._render_active_conversations_table(pipeline_data)

        with col2:
            self._render_commission_tracking(pipeline_data)

    @st.cache_data(ttl=120)  # Cache for 2 minutes for real-time feel
    def _load_seller_pipeline_data(_self, location_id: str) -> List[Dict[str, Any]]:
        """Load seller pipeline data with caching"""
        try:
            # Generate realistic mock seller data
            mock_sellers = []

            # Q4 qualified sellers (HOT - ready for CMA)
            q4_hot_sellers = [
                {
                    "id": "seller_1",
                    "name": "John Smith",
                    "current_question": 4,
                    "questions_answered": 4,
                    "condition": "move_in_ready",
                    "price_expectation": 450000,
                    "motivation": "job_relocation",
                    "urgency": "high",
                    "offer_accepted": True,
                    "timeline_acceptable": True,
                    "temperature": "hot",
                    "needs_cma": True,
                    "last_interaction": datetime.now() - timedelta(minutes=15),
                    "commission_potential": 450000 * 0.75 * 0.06  # $20,250
                },
                {
                    "id": "seller_2",
                    "name": "Sarah Johnson",
                    "current_question": 4,
                    "questions_answered": 4,
                    "condition": "needs_minor_repairs",
                    "price_expectation": 650000,
                    "motivation": "divorce",
                    "urgency": "medium",
                    "offer_accepted": True,
                    "timeline_acceptable": True,
                    "temperature": "hot",
                    "needs_cma": True,
                    "last_interaction": datetime.now() - timedelta(hours=1),
                    "commission_potential": 650000 * 0.75 * 0.06  # $29,250
                }
            ]

            # Q3 sellers (WARM - in qualification)
            q3_warm_sellers = [
                {
                    "id": "seller_3",
                    "name": "Mike Davis",
                    "current_question": 3,
                    "questions_answered": 3,
                    "condition": "needs_major_repairs",
                    "price_expectation": 320000,
                    "motivation": "foreclosure",
                    "urgency": "high",
                    "offer_accepted": None,
                    "timeline_acceptable": None,
                    "temperature": "warm",
                    "needs_cma": False,
                    "last_interaction": datetime.now() - timedelta(hours=3),
                    "commission_potential": 320000 * 0.75 * 0.06  # $14,400
                },
                {
                    "id": "seller_4",
                    "name": "Lisa Wilson",
                    "current_question": 3,
                    "questions_answered": 3,
                    "condition": "move_in_ready",
                    "price_expectation": 580000,
                    "motivation": "upsizing",
                    "urgency": "medium",
                    "offer_accepted": None,
                    "timeline_acceptable": None,
                    "temperature": "warm",
                    "needs_cma": False,
                    "last_interaction": datetime.now() - timedelta(hours=2),
                    "commission_potential": 580000 * 0.75 * 0.06  # $26,100
                }
            ]

            # Q1-Q2 sellers (COLD/WARM - early stage)
            early_stage_sellers = [
                {
                    "id": "seller_5",
                    "name": "Robert Brown",
                    "current_question": 2,
                    "questions_answered": 2,
                    "condition": "move_in_ready",
                    "price_expectation": 425000,
                    "motivation": None,
                    "urgency": None,
                    "offer_accepted": None,
                    "timeline_acceptable": None,
                    "temperature": "warm",
                    "needs_cma": False,
                    "last_interaction": datetime.now() - timedelta(hours=6),
                    "commission_potential": 425000 * 0.75 * 0.06  # $19,125
                },
                {
                    "id": "seller_6",
                    "name": "Jennifer Lee",
                    "current_question": 1,
                    "questions_answered": 1,
                    "condition": "needs_minor_repairs",
                    "price_expectation": None,
                    "motivation": None,
                    "urgency": None,
                    "offer_accepted": None,
                    "timeline_acceptable": None,
                    "temperature": "cold",
                    "needs_cma": False,
                    "last_interaction": datetime.now() - timedelta(hours=12),
                    "commission_potential": 0  # Unknown potential
                }
            ]

            mock_sellers.extend(q4_hot_sellers)
            mock_sellers.extend(q3_warm_sellers)
            mock_sellers.extend(early_stage_sellers)

            return mock_sellers

        except Exception as e:
            logger.error(f"Error loading seller pipeline data: {e}")
            return []

    def _render_q1_q4_funnel(self, pipeline_data: List[Dict]) -> None:
        """Render Q1-Q4 qualification funnel chart"""
        st.markdown("**🎯 Q1-Q4 Qualification Funnel**")

        # Count sellers by question stage
        stage_counts = {
            "Q0 (Greeting)": 0,
            "Q1 (Condition)": 0,
            "Q2 (Price)": 0,
            "Q3 (Motivation)": 0,
            "Q4 (Offer)": 0,
            "Qualified": 0
        }

        for seller in pipeline_data:
            current_q = seller.get("current_question", 0)
            questions_answered = seller.get("questions_answered", 0)

            if questions_answered >= 4 and seller.get("offer_accepted"):
                stage_counts["Qualified"] += 1
            elif current_q == 4:
                stage_counts["Q4 (Offer)"] += 1
            elif current_q == 3:
                stage_counts["Q3 (Motivation)"] += 1
            elif current_q == 2:
                stage_counts["Q2 (Price)"] += 1
            elif current_q == 1:
                stage_counts["Q1 (Condition)"] += 1
            else:
                stage_counts["Q0 (Greeting)"] += 1

        # Create funnel chart
        fig = go.Figure(go.Funnel(
            y=list(stage_counts.keys()),
            x=list(stage_counts.values()),
            textinfo="value+percent initial",
            marker=dict(
                color=["#e5e7eb", "#94a3b8", "#64748b", "#475569", "#334155", "#10b981"]
            ),
            connector=dict(line=dict(color="gray", dash="solid", width=2))
        ))

        fig.update_layout(
            height=350,
            margin=dict(l=0, r=0, t=20, b=0),
            font=dict(size=11)
        )

        st.plotly_chart(fig, use_container_width=True)

        # Add conversion metrics
        total_sellers = len(pipeline_data)
        qualified_count = len([s for s in pipeline_data if s.get("offer_accepted")])
        conversion_rate = (qualified_count / total_sellers * 100) if total_sellers > 0 else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Active", total_sellers, "+2")
        with col2:
            st.metric("Qualified", qualified_count, "+1")
        with col3:
            st.metric("Conversion", f"{conversion_rate:.1f}%", "+5.2%")

    def _render_temperature_distribution(self, pipeline_data: List[Dict]) -> None:
        """Render temperature distribution with CMA triggers"""
        st.markdown("**🌡️ Temperature Breakdown**")

        # Count by temperature
        temp_counts = {
            "🔥 HOT": len([s for s in pipeline_data if s.get("temperature") == "hot"]),
            "🟡 WARM": len([s for s in pipeline_data if s.get("temperature") == "warm"]),
            "🔵 COLD": len([s for s in pipeline_data if s.get("temperature") == "cold"])
        }

        # Create donut chart with CMA indicators
        fig = go.Figure(data=[go.Pie(
            labels=list(temp_counts.keys()),
            values=list(temp_counts.values()),
            hole=0.5,
            marker=dict(
                colors=["#ef4444", "#f59e0b", "#3b82f6"],
                line=dict(color="#FFFFFF", width=2)
            ),
            textinfo='label+value',
            textposition='outside',
            textfont=dict(size=12)
        )])

        # Add CMA ready count in center
        cma_ready_count = len([s for s in pipeline_data if s.get("needs_cma")])

        fig.update_layout(
            height=250,
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=False,
            font=dict(size=11),
            annotations=[dict(
                text=f"<b>{cma_ready_count}</b><br>CMAs Ready",
                x=0.5, y=0.5,
                font_size=14,
                showarrow=False
            )]
        )

        st.plotly_chart(fig, use_container_width=True)

        # CMA automation status
        if cma_ready_count > 0:
            total_commission = sum(s.get("commission_potential", 0) for s in pipeline_data if s.get("needs_cma"))
            st.success(f"💰 ${total_commission/1000:.0f}K potential commission from CMAs")

            if st.button("📊 Generate Priority CMAs", key="generate_priority_cmas", use_container_width=True):
                self._trigger_priority_cma_generation()

    def _render_active_conversations_table(self, pipeline_data: List[Dict]) -> None:
        """Render active conversations management table"""
        st.markdown("**💬 Active Conversations**")

        # Filter active conversations (recent interactions)
        active_conversations = [
            s for s in pipeline_data
            if s.get("last_interaction") and
            (datetime.now() - s.get("last_interaction")) < timedelta(hours=24)
        ]

        if not active_conversations:
            st.info("No active conversations in the last 24 hours")
            return

        # Create interactive table
        conversation_data = []
        for seller in active_conversations:
            # Format last interaction time
            last_interaction = seller.get("last_interaction")
            if last_interaction:
                time_ago = datetime.now() - last_interaction
                if time_ago.seconds < 3600:
                    time_str = f"{time_ago.seconds // 60}m ago"
                else:
                    time_str = f"{time_ago.seconds // 3600}h ago"
            else:
                time_str = "Unknown"

            # Get temperature emoji
            temp_emoji = {
                "hot": "🔥",
                "warm": "🟡",
                "cold": "🔵"
            }.get(seller.get("temperature"), "❓")

            # Get stage
            current_q = seller.get("current_question", 0)
            stage = f"Q{current_q}" if current_q > 0 else "Q0"

            conversation_data.append({
                "Seller": seller.get("name", "Unknown"),
                "Stage": stage,
                "Temp": temp_emoji,
                "Last Activity": time_str,
                "Commission": f"${seller.get('commission_potential', 0)/1000:.0f}K",
                "Action": "CMA Ready" if seller.get("needs_cma") else "Continue Qual"
            })

        # Display as DataFrame
        conv_df = pd.DataFrame(conversation_data)
        st.dataframe(
            conv_df,
            hide_index=True,
            use_container_width=True,
            height=200
        )

        # Add action buttons for top sellers
        st.markdown("**Quick Actions:**")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📞 Call Hot Leads", key="call_hot_leads", use_container_width=True):
                hot_sellers = [s for s in active_conversations if s.get("temperature") == "hot"]
                st.success(f"📞 Calling {len(hot_sellers)} hot sellers...")

        with col2:
            if st.button("📱 Send Follow-ups", key="send_followups", use_container_width=True):
                warm_sellers = [s for s in active_conversations if s.get("temperature") == "warm"]
                st.success(f"📱 Sent follow-ups to {len(warm_sellers)} warm sellers...")

    def _render_commission_tracking(self, pipeline_data: List[Dict]) -> None:
        """Render commission potential tracking"""
        st.markdown("**💰 Commission Pipeline**")

        # Calculate commission metrics
        total_potential = sum(s.get("commission_potential", 0) for s in pipeline_data)
        hot_commission = sum(s.get("commission_potential", 0) for s in pipeline_data if s.get("temperature") == "hot")
        cma_commission = sum(s.get("commission_potential", 0) for s in pipeline_data if s.get("needs_cma"))

        # Display key metrics
        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Total Pipeline",
                f"${total_potential/1000:.0f}K",
                f"+${(total_potential * 0.15)/1000:.0f}K"  # Mock growth
            )

        with col2:
            st.metric(
                "Hot Sellers",
                f"${hot_commission/1000:.0f}K",
                f"+${(hot_commission * 0.25)/1000:.0f}K"
            )

        # Commission breakdown chart
        commission_breakdown = {
            "CMA Ready (Q4)": cma_commission,
            "In Qualification": total_potential - cma_commission,
            "Potential Growth": total_potential * 0.3  # Mock potential
        }

        fig = go.Figure(data=[go.Bar(
            x=list(commission_breakdown.keys()),
            y=list(commission_breakdown.values()),
            marker=dict(
                color=["#10b981", "#3b82f6", "#e5e7eb"],
                opacity=0.8
            ),
            text=[f"${v/1000:.0f}K" for v in commission_breakdown.values()],
            textposition='inside',
            textfont=dict(color='white', size=11)
        )])

        fig.update_layout(
            height=200,
            margin=dict(l=0, r=0, t=20, b=40),
            xaxis_title="",
            yaxis_title="Commission ($)",
            font=dict(size=10),
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)

        # Commission insights
        if cma_commission > 0:
            close_probability = 0.8  # Mock close probability for Q4 sellers
            expected_commission = cma_commission * close_probability
            st.info(f"🎯 Expected commission from CMAs: ${expected_commission/1000:.0f}K (80% close rate)")

    def _trigger_bulk_cma_generation(self) -> None:
        """Trigger bulk CMA generation for all qualified sellers"""
        st.success("🚀 CMA Automation Triggered!")

        # Mock progress
        progress_bar = st.progress(0)
        import time

        sellers_to_process = ["John Smith", "Sarah Johnson"]

        for i, seller in enumerate(sellers_to_process):
            progress_bar.progress((i + 1) / len(sellers_to_process))
            time.sleep(0.5)  # Simulate processing
            st.write(f"✅ Generated CMA for {seller}")

        st.success("🎉 All CMAs generated successfully!")

        # Show results
        with st.expander("📊 CMA Generation Results", expanded=True):
            st.markdown("""
            **Generated CMAs:**
            - John Smith (450 Oak St) - Est. Offer: $337K - Commission: $20K
            - Sarah Johnson (123 Main St) - Est. Offer: $487K - Commission: $29K

            **Total Potential Commission:** $49K
            **Next Steps:** CMAs sent to sellers, schedule follow-up calls
            """)

    def _trigger_priority_cma_generation(self) -> None:
        """Trigger priority CMA generation"""
        st.success("📊 Priority CMAs Generated!")

        with st.expander("🔥 Priority CMA Results", expanded=True):
            st.markdown("""
            **High Priority CMAs:**
            1. Sarah Johnson ($650K property) - $487K offer - $29K commission
            2. John Smith ($450K property) - $337K offer - $20K commission

            **Status:** CMAs generated and sent automatically
            **Follow-up:** Schedule consultation calls within 24 hours
            """)

    def _render_loading_state(self) -> None:
        """Render loading state for seller pipeline"""
        st.markdown("### 🏠 Seller Bot Q1-Q4 Pipeline")
        st.markdown("*Loading seller qualification data...*")

        # Skeleton loading
        col1, col2 = st.columns(2)
        for col in [col1, col2]:
            with col:
                st.markdown("""
                <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin-bottom: 16px;">
                    <div style="background: #e5e7eb; height: 200px; border-radius: 4px;"></div>
                </div>
                """, unsafe_allow_html=True)


# Factory function for component
def render_seller_bot_pipeline(location_id: str) -> None:
    """
    Main function to render seller bot pipeline visualization.

    Args:
        location_id: GHL location ID
    """
    pipeline_viz = SellerBotPipelineViz()
    pipeline_viz.render_seller_pipeline_section(location_id)