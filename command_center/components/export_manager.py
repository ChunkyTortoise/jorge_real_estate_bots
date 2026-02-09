"""
Export Manager for Jorge Real Estate AI Dashboard

Provides comprehensive export functionality:
- Export metrics to CSV/Excel
- Export charts as PNG/SVG/PDF
- Generate PDF reports with charts and data
- Scheduled automated reports (future)
- Multiple export formats and customization
"""

import io
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# PDF generation (install: pip install reportlab)
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

from bots.shared.logger import get_logger

logger = get_logger(__name__)


class ExportManager:
    """
    Export manager for Jorge's dashboard.

    Features:
    - Data export (CSV, Excel, JSON)
    - Chart export (PNG, SVG, PDF)
    - PDF report generation
    - Filtered data export
    - Custom report templates
    - Automated report scheduling (future)
    """

    def __init__(self):
        self.supported_formats = {
            'data': ['CSV', 'Excel', 'JSON'],
            'charts': ['PNG', 'SVG', 'PDF'],
            'reports': ['PDF', 'HTML']
        }

    def render_export_controls(self, data: Optional[Dict[str, Any]] = None):
        """Render export controls in sidebar or main area"""
        with st.sidebar:
            st.markdown("---")
            st.subheader("📥 Export Dashboard")

            # Export type selection
            export_type = st.selectbox(
                "Export Type",
                ["Dashboard Data", "Charts Only", "Full Report", "Activity Feed"],
                help="Choose what to export"
            )

            # Format selection based on export type
            if export_type == "Dashboard Data":
                format_options = self.supported_formats['data']
            elif export_type == "Charts Only":
                format_options = self.supported_formats['charts']
            else:
                format_options = self.supported_formats['reports']

            export_format = st.selectbox(
                "Format",
                format_options,
                help="Select export format"
            )

            # Date range for exports
            st.caption("Export Date Range:")
            col1, col2 = st.columns(2)
            with col1:
                date_from = st.date_input(
                    "From",
                    value=datetime.now().date() - timedelta(days=30),
                    key="export_date_from"
                )
            with col2:
                date_to = st.date_input(
                    "To",
                    value=datetime.now().date(),
                    key="export_date_to"
                )

            # Include filters toggle
            include_filters = st.checkbox(
                "Apply Current Filters",
                value=True,
                help="Apply dashboard filters to export"
            )

            # Custom options based on export type
            custom_options = self._render_custom_options(export_type, export_format)

            # Export button
            if st.button("📤 Generate Export", type="primary"):
                with st.spinner("Generating export..."):
                    self._handle_export(
                        export_type=export_type,
                        format=export_format,
                        date_from=date_from,
                        date_to=date_to,
                        include_filters=include_filters,
                        options=custom_options,
                        data=data
                    )

            # Quick export buttons
            st.caption("Quick Exports:")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 CSV Data"):
                    self._quick_export_csv(data, include_filters)

            with col2:
                if st.button("🖼️ PNG Charts"):
                    self._quick_export_charts("PNG")

    def _render_custom_options(self, export_type: str, export_format: str) -> Dict[str, Any]:
        """Render custom options based on export type and format"""
        options = {}

        if export_type == "Full Report":
            st.caption("Report Options:")

            options['include_summary'] = st.checkbox(
                "Include Executive Summary",
                value=True,
                help="Add executive summary to report"
            )

            options['include_charts'] = st.checkbox(
                "Include Charts",
                value=True,
                help="Add charts and visualizations"
            )

            options['include_data_tables'] = st.checkbox(
                "Include Data Tables",
                value=False,
                help="Add raw data tables to report"
            )

            options['chart_quality'] = st.selectbox(
                "Chart Quality",
                ["Standard", "High", "Print Quality"],
                index=1,
                help="Quality level for embedded charts"
            )

        elif export_type == "Charts Only":
            st.caption("Chart Options:")

            options['resolution'] = st.selectbox(
                "Resolution",
                ["800x600", "1200x900", "1920x1080", "Custom"],
                index=1,
                help="Chart resolution for export"
            )

            if options['resolution'] == "Custom":
                col1, col2 = st.columns(2)
                with col1:
                    options['width'] = st.number_input("Width", value=1200, min_value=400)
                with col2:
                    options['height'] = st.number_input("Height", value=900, min_value=300)

            options['include_title'] = st.checkbox(
                "Include Chart Titles",
                value=True,
                help="Include titles on exported charts"
            )

        elif export_type == "Dashboard Data":
            st.caption("Data Options:")

            options['include_metadata'] = st.checkbox(
                "Include Metadata",
                value=True,
                help="Add export metadata and filter information"
            )

            if export_format == "Excel":
                options['separate_sheets'] = st.checkbox(
                    "Separate Sheets",
                    value=True,
                    help="Create separate sheets for different data types"
                )

        return options

    def _handle_export(self, export_type: str, format: str, date_from, date_to,
                      include_filters: bool, options: Dict, data: Optional[Dict] = None):
        """Handle the export request based on type and format"""

        try:
            if export_type == "Dashboard Data":
                self._export_dashboard_data(format, date_from, date_to, include_filters, options, data)

            elif export_type == "Charts Only":
                self._export_charts(format, options)

            elif export_type == "Full Report":
                self._export_full_report(format, date_from, date_to, include_filters, options, data)

            elif export_type == "Activity Feed":
                self._export_activity_feed(format, date_from, date_to, include_filters, options)

            st.success(f"✅ Export completed: {export_type} ({format})")

        except Exception as e:
            logger.error(f"Export failed: {e}")
            st.error(f"❌ Export failed: {str(e)}")

    def _export_dashboard_data(self, format: str, date_from, date_to,
                              include_filters: bool, options: Dict, data: Optional[Dict]):
        """Export dashboard data in specified format"""

        # Generate sample data (in production, this would come from actual data)
        export_data = self._generate_sample_export_data(date_from, date_to, include_filters)

        if format == "CSV":
            self._export_csv(export_data, options)
        elif format == "Excel":
            self._export_excel(export_data, options)
        elif format == "JSON":
            self._export_json(export_data, options)

    def _export_csv(self, data: Dict[str, pd.DataFrame], options: Dict):
        """Export data as CSV"""
        # Combine all data into single DataFrame or provide multiple files
        if len(data) == 1:
            # Single CSV file
            df = list(data.values())[0]
            csv_data = df.to_csv(index=False)

            filename = f"jorge_dashboard_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            st.download_button(
                "📥 Download CSV",
                csv_data,
                filename,
                "text/csv",
                help=f"Download {len(df)} records as CSV"
            )
        else:
            # Multiple CSV files (zip them)
            self._export_multiple_csv_as_zip(data, options)

    def _export_excel(self, data: Dict[str, pd.DataFrame], options: Dict):
        """Export data as Excel file"""
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if options.get('separate_sheets', True):
                # Separate sheets for each data type
                for sheet_name, df in data.items():
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)  # Excel sheet name limit
            else:
                # Single sheet with all data
                combined_df = pd.concat(data.values(), ignore_index=True)
                combined_df.to_excel(writer, sheet_name='Dashboard_Data', index=False)

            # Add metadata sheet if requested
            if options.get('include_metadata', True):
                metadata_df = self._generate_metadata_sheet()
                metadata_df.to_excel(writer, sheet_name='Export_Info', index=False)

        excel_data = output.getvalue()
        filename = f"jorge_dashboard_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        st.download_button(
            "📥 Download Excel",
            excel_data,
            filename,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Download as Excel file with multiple sheets"
        )

    def _export_json(self, data: Dict[str, pd.DataFrame], options: Dict):
        """Export data as JSON"""
        # Convert DataFrames to dictionaries
        json_data = {}
        for key, df in data.items():
            json_data[key] = df.to_dict('records')

        # Add metadata if requested
        if options.get('include_metadata', True):
            json_data['export_metadata'] = {
                'exported_at': datetime.now().isoformat(),
                'record_counts': {key: len(df) for key, df in data.items()},
                'filters_applied': st.session_state.get('global_filters', {}),
                'dashboard_version': '1.0.0'
            }

        json_string = json.dumps(json_data, indent=2, default=str)
        filename = f"jorge_dashboard_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        st.download_button(
            "📥 Download JSON",
            json_string,
            filename,
            "application/json",
            help="Download as structured JSON file"
        )

    def _export_charts(self, format: str, options: Dict):
        """Export charts in specified format"""
        # Get current charts from session state or generate sample charts
        charts = self._get_dashboard_charts()

        if format == "PNG":
            self._export_charts_png(charts, options)
        elif format == "SVG":
            self._export_charts_svg(charts, options)
        elif format == "PDF":
            self._export_charts_pdf(charts, options)

    def _export_charts_png(self, charts: List[go.Figure], options: Dict):
        """Export charts as PNG files"""
        resolution = options.get('resolution', '1200x900')

        if resolution != "Custom":
            width, height = map(int, resolution.split('x'))
        else:
            width = options.get('width', 1200)
            height = options.get('height', 900)

        # Export each chart
        for i, fig in enumerate(charts):
            img_bytes = fig.to_image(
                format="png",
                width=width,
                height=height,
                engine="orca"  # or "kaleido"
            )

            filename = f"jorge_chart_{i+1}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

            st.download_button(
                f"📥 Download Chart {i+1} (PNG)",
                img_bytes,
                filename,
                "image/png",
                key=f"chart_png_{i}"
            )

    def _export_full_report(self, format: str, date_from, date_to,
                           include_filters: bool, options: Dict, data: Optional[Dict]):
        """Export full dashboard report"""

        if format == "PDF" and PDF_AVAILABLE:
            self._export_pdf_report(date_from, date_to, include_filters, options, data)
        elif format == "HTML":
            self._export_html_report(date_from, date_to, include_filters, options, data)
        else:
            st.error("PDF export requires reportlab package. Install with: pip install reportlab")

    def _export_pdf_report(self, date_from, date_to, include_filters: bool,
                          options: Dict, data: Optional[Dict]):
        """Generate comprehensive PDF report"""

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1  # Center
        )
        story.append(Paragraph("Jorge's Real Estate AI Dashboard Report", title_style))
        story.append(Spacer(1, 12))

        # Report metadata
        meta_data = [
            ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Date Range:', f"{date_from} to {date_to}"],
            ['Filters Applied:', "Yes" if include_filters else "No"]
        ]

        meta_table = Table(meta_data)
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 12))

        # Executive Summary (if requested)
        if options.get('include_summary', True):
            story.append(Paragraph("Executive Summary", styles['Heading2']))
            summary_text = self._generate_executive_summary(data)
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 12))

        # Charts (if requested)
        if options.get('include_charts', True):
            story.append(Paragraph("Performance Charts", styles['Heading2']))
            # Add chart images here (would need to generate and embed)
            story.append(Paragraph("Charts would be embedded here in production version.", styles['Normal']))
            story.append(Spacer(1, 12))

        # Data Tables (if requested)
        if options.get('include_data_tables', False):
            story.append(Paragraph("Data Tables", styles['Heading2']))
            # Add data tables here
            sample_data = [['Lead ID', 'Score', 'Temperature', 'Stage']]
            for i in range(5):  # Sample data
                sample_data.append([f"L{1000+i}", f"{85+i}", "HOT", "Q3"])

            data_table = Table(sample_data)
            data_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(data_table)

        # Build PDF
        doc.build(story)
        pdf_data = buffer.getvalue()
        buffer.close()

        filename = f"jorge_dashboard_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        st.download_button(
            "📥 Download PDF Report",
            pdf_data,
            filename,
            "application/pdf",
            help="Download comprehensive dashboard report as PDF"
        )

    def _quick_export_csv(self, data: Optional[Dict], include_filters: bool):
        """Quick CSV export with minimal options"""
        export_data = self._generate_sample_export_data(
            datetime.now().date() - timedelta(days=30),
            datetime.now().date(),
            include_filters
        )

        # Use the main data table
        main_data = list(export_data.values())[0] if export_data else pd.DataFrame()
        csv_data = main_data.to_csv(index=False)

        filename = f"jorge_quick_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        st.download_button(
            "📥 Download Quick CSV",
            csv_data,
            filename,
            "text/csv",
            help="Quick export of current dashboard data"
        )

    def _quick_export_charts(self, format: str):
        """Quick chart export with default options"""
        st.info(f"Quick {format} chart export would be generated here")

    def _generate_sample_export_data(self, date_from, date_to, include_filters: bool) -> Dict[str, pd.DataFrame]:
        """Generate sample data for export (replace with actual data in production)"""

        # Sample lead data
        leads_data = {
            'lead_id': [f"L{1000+i}" for i in range(50)],
            'name': [f"Contact {i+1}" for i in range(50)],
            'score': [75 + (i % 26) for i in range(50)],
            'temperature': ['HOT' if i % 3 == 0 else 'WARM' if i % 3 == 1 else 'COLD' for i in range(50)],
            'stage': [f"Q{i % 5}" for i in range(50)],
            'budget': [200000 + (i * 15000) for i in range(50)],
            'timeline': ['Immediate' if i % 4 == 0 else '1 Month' if i % 4 == 1 else '2 Months' for i in range(50)],
            'date_created': [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(50)]
        }

        # Sample activity data
        activity_data = {
            'timestamp': [(datetime.now() - timedelta(hours=i)).isoformat() for i in range(100)],
            'event_type': ['lead.analyzed', 'ghl.tag_added', 'cache.hit'] * 34,
            'contact_id': [f"L{1000 + (i % 50)}" for i in range(100)],
            'details': [f"Event details {i+1}" for i in range(100)]
        }

        return {
            'leads': pd.DataFrame(leads_data),
            'activity': pd.DataFrame(activity_data)
        }

    def _generate_metadata_sheet(self) -> pd.DataFrame:
        """Generate export metadata information"""
        metadata = {
            'Property': ['Export Date', 'Dashboard Version', 'Total Records', 'Filters Applied', 'Export Format'],
            'Value': [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '1.0.0',
                '150',  # Example count
                str(st.session_state.get('global_filters', {}).get('active', False)),
                'Excel'
            ]
        }
        return pd.DataFrame(metadata)

    def _generate_executive_summary(self, data: Optional[Dict]) -> str:
        """Generate executive summary text"""
        return """
        This dashboard report provides a comprehensive overview of Jorge's Real Estate AI performance.
        The system has processed multiple leads with high efficiency, maintaining strong conversion rates
        and rapid response times. Key highlights include improved lead qualification accuracy and
        streamlined workflow automation.
        """

    def _get_dashboard_charts(self) -> List[go.Figure]:
        """Get current dashboard charts (sample implementation)"""
        # Sample charts - in production, these would come from the actual dashboard
        fig1 = px.bar(x=['Hot', 'Warm', 'Cold'], y=[25, 45, 30], title="Lead Temperature Distribution")
        fig2 = px.line(x=list(range(7)), y=[10, 12, 8, 15, 18, 22, 20], title="Daily Lead Volume")

        return [fig1, fig2]