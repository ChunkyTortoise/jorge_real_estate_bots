import importlib
import sys
from pathlib import Path

import pandas as pd

from tests.command_center.streamlit_stub import install_streamlit_stub


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMPONENTS_DIR = ROOT / "command_center" / "components"
if str(COMPONENTS_DIR) not in sys.path:
    sys.path.insert(0, str(COMPONENTS_DIR))


def import_component(monkeypatch, module_name):
    install_streamlit_stub(monkeypatch)
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_mobile_metrics_cards_render(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.mobile_metrics_cards")
    metrics = module.get_sample_metrics()
    module.render_mobile_metrics_cards(metrics, title="Test Metrics", show_refresh=False)


def test_mobile_navigation_render(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.mobile_navigation")
    html = module.render_mobile_navigation(current_tab="overview")
    assert "mobile-nav-item" in html


def test_mobile_responsive_layout_render(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.mobile_responsive_layout")
    module.apply_responsive_layout_system()
    card = module.create_responsive_card("<h4>Test Card</h4>", jorge_branded=True)
    grid = module.create_responsive_grid([card, card], mobile_cols=1, tablet_cols=2, desktop_cols=2)
    container = module.create_responsive_container(grid, max_width="lg")
    assert "responsive-container" in container


def test_touch_optimized_chart_render(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.touch_optimized_charts")
    data = pd.DataFrame(
        {
            "date": pd.date_range(start="2024-01-01", periods=10, freq="D"),
            "leads": list(range(10)),
            "source": ["web"] * 10,
        }
    )
    config = module.ChartConfig(
        chart_type=module.ChartType.LINE,
        title="Test Chart",
        data=data,
        x_column="date",
        y_column="leads",
        color_column="source",
        height=240,
    )
    module.render_touch_optimized_chart(config)


def test_offline_indicator_render(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.offline_indicator")
    sync_items = [
        module.SyncItem(
            id="sync_1",
            item_type="photo_upload",
            timestamp=module.datetime.now(),
            priority=module.SyncPriority.HIGH,
            status=module.SyncItemStatus.PENDING,
            data_size=1500,
        )
    ]
    network = module.NetworkMetrics(latency=120, bandwidth=500, signal_strength=80)
    module.create_offline_indicator(
        connection_status=module.ConnectionStatus.ONLINE,
        sync_queue=sync_items,
        network_metrics=network,
        expanded=True,
    )


def test_field_access_dashboard_render(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.field_access_dashboard")
    module.create_field_access_dashboard(
        current_location=(32.7767, -96.7970),
        address="Dallas, TX",
        gps_accuracy=8.0,
        sync_queue=module.get_sample_sync_queue(),
        online_status=True,
    )


def test_mobile_dashboard_integration_render(monkeypatch):
    module = import_component(monkeypatch, "command_center.components.mobile_dashboard_integration")
    sample_data = module.get_sample_real_estate_data()
    module.render_mobile_dashboard_tab("overview", sample_data)
