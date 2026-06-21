from unittest.mock import MagicMock
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.storage.apps import AppsViewModel
from droidbridge.gui.pages.storage.apps import AppsPanel
from tests.test_gui_viewmodels_device import FakeWorker
from PyQt6.QtCore import Qt


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _rows(n):
    return [
        {
            "package": f"com.app{i}", "total_size_str": f"{100 - i}.0 MB",
            "apk_size_str": "10.0 MB", "data_size_str": "5.0 MB", "cache_size_str": "1.0 MB",
            "kind": "system" if i % 2 == 0 else "user",
        }
        for i in range(n)
    ]


class TestAppsViewModel:
    def test_load_emits_results_changed(self, qtbot, monkeypatch):
        vm = AppsViewModel(_connected_ctx(), worker_factory=FakeWorker)
        rows = _rows(3)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.apps.storage_ops.get_apps", lambda *a, **kw: rows
        )
        results = []
        vm.resultsChanged.connect(results.append)
        vm.load()
        assert results == [rows]

    def test_load_passes_filter_kind_through(self, qtbot, monkeypatch):
        vm = AppsViewModel(_connected_ctx(), worker_factory=FakeWorker)
        captured = {}

        def fake_get_apps(client, serial, filter_kind=None):
            captured["filter_kind"] = filter_kind
            return []

        monkeypatch.setattr("droidbridge.gui.viewmodels.storage.apps.storage_ops.get_apps", fake_get_apps)
        vm.load(filter_kind="system")
        assert captured["filter_kind"] == "system"

    def test_load_emits_busy_changed(self, qtbot, monkeypatch):
        vm = AppsViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.apps.storage_ops.get_apps", lambda *a, **kw: []
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.load()
        assert busy == [True, False]


class TestAppsPanel:
    def test_top_spin_defaults_to_twenty(self, qtbot):
        panel = AppsPanel(_connected_ctx())
        qtbot.addWidget(panel)
        assert panel.top_spin.value() == 20

    def test_show_all_checked_disables_top_spin(self, qtbot):
        panel = AppsPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show_all_checkbox.setChecked(True)
        assert not panel.top_spin.isEnabled()
        panel.show_all_checkbox.setChecked(False)
        assert panel.top_spin.isEnabled()

    def test_refresh_button_triggers_viewmodel_with_filter_kind(self, qtbot, monkeypatch):
        panel = AppsPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.filter_combo.setCurrentIndex(1)  # "System apps only"
        calls = []
        monkeypatch.setattr(panel.viewmodel, "load", lambda filter_kind=None: calls.append(filter_kind))
        qtbot.mouseClick(panel.refresh_button, Qt.MouseButton.LeftButton)
        assert calls == ["system"]

    def test_results_changed_populates_table_respecting_top_n(self, qtbot):
        panel = AppsPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.top_spin.setValue(2)
        panel.viewmodel.resultsChanged.emit(_rows(5))
        assert panel.apps_table.rowCount() == 2
        assert panel.apps_table.item(0, 0).text() == "com.app0"

    def test_show_all_checked_shows_every_row(self, qtbot):
        panel = AppsPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.top_spin.setValue(2)
        panel.show_all_checkbox.setChecked(True)
        panel.viewmodel.resultsChanged.emit(_rows(5))
        assert panel.apps_table.rowCount() == 5

    def test_empty_results_shows_empty_label(self, qtbot):
        panel = AppsPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.resultsChanged.emit([])
        assert panel.empty_label.isVisible()
        assert not panel.apps_table.isVisible()

    def test_nonempty_results_hides_empty_label(self, qtbot):
        panel = AppsPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.resultsChanged.emit(_rows(1))
        assert not panel.empty_label.isVisible()
        assert panel.apps_table.isVisible()

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = AppsPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()
