import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from tests.command_center.streamlit_stub import install_streamlit_stub


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def import_component(monkeypatch, module_name):
    install_streamlit_stub(monkeypatch)
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_activity_feed_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.activity_feed")
    feed = module.ActivityFeed()
    with patch.object(feed, "_handle_polling_fallback", return_value=None):
        feed.render()


def test_commission_tracking_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.commission_tracking")
    component = module.CommissionTrackingComponent()
    with patch.object(component, "_fetch_commission_data", return_value={"ok": True}), \
         patch.object(component, "_render_overview_metrics") as overview, \
         patch.object(component, "_render_commission_pipeline") as pipeline, \
         patch.object(component, "_render_commission_forecasts") as forecasts, \
         patch.object(component, "_render_commission_trends") as trends, \
         patch.object(component, "_render_performance_analysis") as performance:
        component.render()
        assert overview.called
        assert pipeline.called
        assert forecasts.called
        assert trends.called
        assert performance.called


def test_performance_analytics_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.performance_analytics")
    component = module.PerformanceAnalyticsComponent()
    with patch.object(component, "_fetch_performance_data", return_value={"ok": True}), \
         patch.object(component, "_render_overview_metrics") as overview, \
         patch.object(component, "_render_performance_overview") as perf, \
         patch.object(component, "_render_cache_analytics") as cache, \
         patch.object(component, "_render_cost_savings_analytics") as savings, \
         patch.object(component, "_render_performance_trends") as trends:
        component.render()
        assert overview.called
        assert perf.called
        assert cache.called
        assert savings.called
        assert trends.called


def test_export_manager_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.export_manager")
    manager = module.ExportManager()
    with patch.object(manager, "_handle_export") as handle_export, \
         patch.object(manager, "_quick_export_csv") as quick_csv, \
         patch.object(manager, "_quick_export_charts") as quick_charts:
        manager.render_export_controls(data={"sample": True})
        assert handle_export.call_count == 0
        assert quick_csv.call_count == 0
        assert quick_charts.call_count == 0


def test_seller_bot_pipeline_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.seller_bot_pipeline")
    component = module.SellerBotPipelineViz()
    with patch.object(component, "_load_seller_pipeline_data", return_value=[{"id": "s1"}]), \
         patch.object(component, "_render_q1_q4_funnel") as funnel, \
         patch.object(component, "_render_temperature_distribution") as temps, \
         patch.object(component, "_render_active_conversations_table") as table, \
         patch.object(component, "_render_commission_tracking") as commissions:
        component.render_seller_pipeline_section("loc_1")
        assert funnel.called
        assert temps.called
        assert table.called
        assert commissions.called


def test_auth_component_password_change_render(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.auth_component")
    dummy_user = SimpleNamespace(user_id="user_1")
    assert module.render_password_change_form(dummy_user) is False


def test_global_filters_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.global_filters")
    component = module.GlobalFilters()
    component.render_sidebar_filters()


def test_lead_intelligence_dashboard_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.lead_intelligence_dashboard")
    component = module.LeadIntelligenceDashboard()
    with patch.object(component, "_load_lead_intelligence_data", return_value=[{"id": "lead"}]), \
         patch.object(component, "_render_score_distribution_chart") as score, \
         patch.object(component, "_render_budget_analysis_chart") as budget, \
         patch.object(component, "_render_timeline_classification_chart") as timeline, \
         patch.object(component, "_render_geographic_heatmap") as geo, \
         patch.object(component, "_render_source_performance_chart") as source, \
         patch.object(component, "_render_predictive_insights_section") as insights:
        component.render_lead_intelligence_section("loc_1")
        assert score.called
        assert budget.called
        assert timeline.called
        assert geo.called
        assert source.called
        assert insights.called


def test_active_conversations_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.active_conversations")
    component = module.ActiveConversationsComponent()
    conversations = SimpleNamespace(total_count=1, conversations=[])
    with patch.object(component, "_render_filter_controls", return_value=None), \
         patch.object(component, "_fetch_conversations", return_value=conversations), \
         patch.object(component, "_render_summary_metrics") as summary, \
         patch.object(component, "_render_conversations_table") as table, \
         patch.object(component, "_render_pagination_controls") as pagination, \
         patch.object(component, "_render_stage_distribution_chart") as chart:
        component.render()
        assert summary.called
        assert table.called
        assert pagination.called
        assert chart.called


def test_ghl_status_ui_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.ghl_status_ui")
    component = module.GHLStatusUI()
    with patch.object(component, "_load_status_data", return_value=SimpleNamespace()), \
         patch.object(component, "_render_alerts") as alerts, \
         patch.object(component, "_render_status_overview") as overview, \
         patch.object(component, "_render_automation_controls") as controls, \
         patch.object(component, "_render_performance_metrics") as metrics:
        component.render_ghl_status_section("loc_1")
        assert alerts.called
        assert overview.called
        assert controls.called
        assert metrics.called


def test_hero_metrics_ui_render_smoke(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.hero_metrics_ui")
    component = module.HeroMetricsUI()
    with patch.object(component, "_load_metrics_data", return_value=[SimpleNamespace()]), \
         patch.object(component, "_render_metric_cards") as cards, \
         patch.object(component, "_render_action_buttons_section") as actions:
        component.render_hero_metrics_section("loc_1")
        assert cards.called
        assert actions.called
