"""
Global Filters Component for Jorge Real Estate AI Dashboard

Provides advanced filtering and search capabilities across the dashboard:
- Date range filtering
- Lead temperature filtering
- Seller bot stage filtering
- Budget range filtering
- Timeline filtering
- Filter presets (save/load)
- Clear all filters functionality
"""

import streamlit as st
from datetime import date, timedelta, datetime
from typing import Dict, List, Any, Optional
import json

from bots.shared.logger import get_logger

logger = get_logger(__name__)


class GlobalFilters:
    """
    Global filters component for Jorge's dashboard.

    Features:
    - Date range selection
    - Lead qualification filters (temperature, stage, budget, timeline)
    - Filter presets (save/load/manage)
    - Clear all functionality
    - Filter state persistence
    - Export filter configurations
    """

    def __init__(self):
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize filter session state"""
        if 'global_filters' not in st.session_state:
            st.session_state.global_filters = {
                'date_from': date.today() - timedelta(days=30),
                'date_to': date.today(),
                'temperatures': ['HOT', 'WARM'],
                'stages': ['Q0', 'Q1', 'Q2', 'Q3', 'Q4'],
                'budget_min': 200000,
                'budget_max': 800000,
                'timelines': ['Immediate', '1 Month', '2 Months'],
                'active': True
            }

        if 'filter_presets' not in st.session_state:
            st.session_state.filter_presets = {
                'Hot Leads Only': {
                    'temperatures': ['HOT'],
                    'stages': ['Q3', 'Q4', 'Qualified'],
                    'budget_min': 400000,
                    'budget_max': 1000000,
                    'timelines': ['Immediate', '1 Month']
                },
                'All Prospects': {
                    'temperatures': ['HOT', 'WARM', 'COLD'],
                    'stages': ['Q0', 'Q1', 'Q2', 'Q3', 'Q4'],
                    'budget_min': 100000,
                    'budget_max': 1000000,
                    'timelines': ['Immediate', '1 Month', '2 Months', '3-6 Months']
                },
                'Quick Closers': {
                    'temperatures': ['HOT', 'WARM'],
                    'stages': ['Q2', 'Q3', 'Q4'],
                    'budget_min': 300000,
                    'budget_max': 800000,
                    'timelines': ['Immediate', '1 Month']
                }
            }

    def render_sidebar_filters(self):
        """Render filters in the sidebar"""
        with st.sidebar:
            st.title("🔍 Global Filters")

            # Filter active toggle
            active = st.toggle(
                "Enable Filters",
                value=st.session_state.global_filters.get('active', True),
                help="Toggle global filters on/off"
            )
            st.session_state.global_filters['active'] = active

            if not active:
                st.info("Filters are disabled. All data will be shown.")
                return

            st.divider()

            # Date range filter
            self._render_date_filter()

            st.divider()

            # Lead qualification filters
            self._render_lead_filters()

            st.divider()

            # Action buttons
            self._render_filter_actions()

            st.divider()

            # Filter presets
            self._render_filter_presets()

    def _render_date_filter(self):
        """Render date range filter"""
        st.subheader("📅 Date Range")

        col1, col2 = st.columns(2)

        with col1:
            date_from = st.date_input(
                "From",
                value=st.session_state.global_filters['date_from'],
                max_value=date.today(),
                help="Start date for filtering"
            )

        with col2:
            date_to = st.date_input(
                "To",
                value=st.session_state.global_filters['date_to'],
                min_value=date_from,
                max_value=date.today(),
                help="End date for filtering"
            )

        # Quick date range buttons
        st.caption("Quick ranges:")
        quick_ranges = {
            "Last 7 days": 7,
            "Last 30 days": 30,
            "Last 90 days": 90
        }

        cols = st.columns(len(quick_ranges))
        for i, (label, days) in enumerate(quick_ranges.items()):
            with cols[i]:
                if st.button(label, key=f"date_range_{days}"):
                    date_from = date.today() - timedelta(days=days)
                    date_to = date.today()
                    st.rerun()

        # Update session state
        st.session_state.global_filters.update({
            'date_from': date_from,
            'date_to': date_to
        })

    def _render_lead_filters(self):
        """Render lead qualification filters"""

        # Temperature filter
        st.subheader("🌡️ Lead Temperature")
        temperatures = st.multiselect(
            "Select temperatures",
            ["HOT", "WARM", "COLD"],
            default=st.session_state.global_filters.get('temperatures', ['HOT', 'WARM']),
            help="Filter by lead temperature classification"
        )

        # Seller bot stage filter
        st.subheader("🎯 Seller Bot Stage")
        stages = st.multiselect(
            "Select stages",
            ["Q0", "Q1", "Q2", "Q3", "Q4", "Qualified"],
            default=st.session_state.global_filters.get('stages', ['Q0', 'Q1', 'Q2', 'Q3', 'Q4']),
            help="Filter by seller bot qualification stage"
        )

        # Budget range filter
        st.subheader("💰 Budget Range")
        col1, col2 = st.columns(2)

        with col1:
            budget_min = st.number_input(
                "Min ($)",
                value=st.session_state.global_filters.get('budget_min', 200000),
                min_value=0,
                max_value=5000000,
                step=50000,
                format="%d",
                help="Minimum budget threshold"
            )

        with col2:
            budget_max = st.number_input(
                "Max ($)",
                value=st.session_state.global_filters.get('budget_max', 800000),
                min_value=budget_min,
                max_value=5000000,
                step=50000,
                format="%d",
                help="Maximum budget threshold"
            )

        # Timeline filter
        st.subheader("⏰ Timeline")
        timelines = st.multiselect(
            "Select timelines",
            ["Immediate", "1 Month", "2 Months", "3-6 Months", "6+ Months", "No Rush"],
            default=st.session_state.global_filters.get('timelines', ['Immediate', '1 Month']),
            help="Filter by buying/selling timeline"
        )

        # Update session state
        st.session_state.global_filters.update({
            'temperatures': temperatures,
            'stages': stages,
            'budget_min': budget_min,
            'budget_max': budget_max,
            'timelines': timelines
        })

    def _render_filter_actions(self):
        """Render filter action buttons"""
        st.subheader("⚡ Actions")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🔄 Apply Filters", type="primary"):
                st.success("Filters applied!")
                st.rerun()

        with col2:
            if st.button("🗑️ Clear All"):
                self.clear_filters()
                st.success("Filters cleared!")
                st.rerun()

        # Export current filters
        if st.button("📤 Export Config"):
            self._export_filter_config()

    def _render_filter_presets(self):
        """Render filter presets management"""
        st.subheader("💾 Filter Presets")

        # Load preset dropdown
        preset_names = list(st.session_state.filter_presets.keys())
        if preset_names:
            selected_preset = st.selectbox(
                "Load preset",
                [""] + preset_names,
                help="Select a saved filter preset to load"
            )

            if selected_preset and st.button(f"Load '{selected_preset}'"):
                self.load_preset(selected_preset)
                st.success(f"Loaded preset: {selected_preset}")
                st.rerun()

        # Save new preset
        st.caption("Save current filters:")
        new_preset_name = st.text_input(
            "Preset name",
            placeholder="Enter preset name...",
            help="Name for saving current filter configuration"
        )

        if new_preset_name and st.button("💾 Save Preset"):
            self.save_preset(new_preset_name)
            st.success(f"Saved preset: {new_preset_name}")
            st.rerun()

        # Manage presets
        if preset_names:
            st.caption("Manage presets:")
            preset_to_delete = st.selectbox(
                "Delete preset",
                [""] + preset_names,
                key="delete_preset_select",
                help="Select a preset to delete"
            )

            if preset_to_delete and st.button("🗑️ Delete Preset"):
                self.delete_preset(preset_to_delete)
                st.success(f"Deleted preset: {preset_to_delete}")
                st.rerun()

    def clear_filters(self):
        """Clear all filters to default values"""
        st.session_state.global_filters = {
            'date_from': date.today() - timedelta(days=30),
            'date_to': date.today(),
            'temperatures': ['HOT', 'WARM', 'COLD'],
            'stages': ['Q0', 'Q1', 'Q2', 'Q3', 'Q4'],
            'budget_min': 100000,
            'budget_max': 1000000,
            'timelines': ['Immediate', '1 Month', '2 Months', '3-6 Months'],
            'active': True
        }

        logger.info("Global filters cleared")

    def save_preset(self, name: str):
        """Save current filter configuration as preset"""
        current_filters = st.session_state.global_filters.copy()

        # Remove date range and active status from presets
        preset_data = {
            'temperatures': current_filters.get('temperatures', []),
            'stages': current_filters.get('stages', []),
            'budget_min': current_filters.get('budget_min', 200000),
            'budget_max': current_filters.get('budget_max', 800000),
            'timelines': current_filters.get('timelines', [])
        }

        st.session_state.filter_presets[name] = preset_data
        logger.info(f"Filter preset saved: {name}")

    def load_preset(self, name: str):
        """Load filter preset"""
        if name not in st.session_state.filter_presets:
            st.error(f"Preset '{name}' not found")
            return

        preset_data = st.session_state.filter_presets[name]

        # Update current filters (preserve date range)
        st.session_state.global_filters.update({
            'temperatures': preset_data.get('temperatures', []),
            'stages': preset_data.get('stages', []),
            'budget_min': preset_data.get('budget_min', 200000),
            'budget_max': preset_data.get('budget_max', 800000),
            'timelines': preset_data.get('timelines', [])
        })

        logger.info(f"Filter preset loaded: {name}")

    def delete_preset(self, name: str):
        """Delete filter preset"""
        if name in st.session_state.filter_presets:
            del st.session_state.filter_presets[name]
            logger.info(f"Filter preset deleted: {name}")

    def get_active_filters(self) -> Dict[str, Any]:
        """Get current active filter configuration"""
        if not st.session_state.global_filters.get('active', True):
            return {'active': False}

        return st.session_state.global_filters.copy()

    def is_lead_filtered(self, lead_data: Dict[str, Any]) -> bool:
        """
        Check if a lead passes the current filter criteria.

        Args:
            lead_data: Dictionary containing lead information

        Returns:
            True if lead passes filters, False otherwise
        """
        if not st.session_state.global_filters.get('active', True):
            return True  # No filtering when disabled

        filters = st.session_state.global_filters

        # Check temperature
        lead_temp = lead_data.get('temperature', '').upper()
        if lead_temp and lead_temp not in filters.get('temperatures', []):
            return False

        # Check stage
        lead_stage = lead_data.get('stage', '')
        if lead_stage and lead_stage not in filters.get('stages', []):
            return False

        # Check budget
        lead_budget = lead_data.get('budget', 0)
        if isinstance(lead_budget, (int, float)):
            budget_min = filters.get('budget_min', 0)
            budget_max = filters.get('budget_max', float('inf'))
            if not (budget_min <= lead_budget <= budget_max):
                return False

        # Check timeline
        lead_timeline = lead_data.get('timeline', '')
        if lead_timeline and lead_timeline not in filters.get('timelines', []):
            return False

        # Check date range (if lead has a date field)
        lead_date = lead_data.get('date')
        if lead_date:
            try:
                if isinstance(lead_date, str):
                    lead_date = datetime.strptime(lead_date, '%Y-%m-%d').date()

                date_from = filters.get('date_from')
                date_to = filters.get('date_to')

                if date_from and lead_date < date_from:
                    return False
                if date_to and lead_date > date_to:
                    return False

            except (ValueError, TypeError):
                pass  # Skip date filtering if date parsing fails

        return True

    def get_filter_summary(self) -> str:
        """Get human-readable filter summary"""
        if not st.session_state.global_filters.get('active', True):
            return "No filters active"

        filters = st.session_state.global_filters
        summary_parts = []

        # Date range
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        if date_from and date_to:
            summary_parts.append(f"Date: {date_from} to {date_to}")

        # Temperatures
        temps = filters.get('temperatures', [])
        if temps:
            summary_parts.append(f"Temperature: {', '.join(temps)}")

        # Budget
        budget_min = filters.get('budget_min')
        budget_max = filters.get('budget_max')
        if budget_min is not None and budget_max is not None:
            summary_parts.append(f"Budget: ${budget_min:,} - ${budget_max:,}")

        # Stages
        stages = filters.get('stages', [])
        if stages:
            summary_parts.append(f"Stages: {', '.join(stages)}")

        # Timelines
        timelines = filters.get('timelines', [])
        if timelines:
            summary_parts.append(f"Timeline: {', '.join(timelines)}")

        return "; ".join(summary_parts) if summary_parts else "No specific filters"

    def _export_filter_config(self):
        """Export current filter configuration as JSON"""
        config = {
            'filters': st.session_state.global_filters,
            'presets': st.session_state.filter_presets,
            'exported_at': datetime.now().isoformat()
        }

        config_json = json.dumps(config, indent=2, default=str)

        st.download_button(
            label="📥 Download Filter Config",
            data=config_json,
            file_name=f"jorge_filter_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            help="Download current filter configuration as JSON file"
        )