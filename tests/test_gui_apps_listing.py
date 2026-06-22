from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.apps.listing import ListingViewModel
from droidbridge.gui.pages.apps.listing import ListingPanel
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _rows(n):
    return [
        {
            "package": f"com.app{i}", "version_name": "1.0", "version_code": i,
            "installed_str": "2024-01-01 00:00", "updated_str": "2024-01-01 00:00",
            "apk_size": 10, "apk_size_str": "10 B", "data_size": 20, "data_size_str": "20 B",
            "cache_size": 5, "cache_size_str": "5 B", "total_size_str": "35 B",
            "kind": "system" if i % 2 == 0 else "user", "is_system": i % 2 == 0,
            "status": "Enabled", "is_disabled": False,
        }
        for i in range(n)
    ]


class TestListingViewModel:
    def test_load_emits_results_changed(self, qtbot, monkeypatch):
        vm = ListingViewModel(_connected_ctx(), worker_factory=FakeWorker)
        rows = _rows(3)
        monkeypatch.setattr("droidbridge.gui.viewmodels.apps.listing.apps_ops.get_apps", lambda *a, **kw: rows)
        results = []
        vm.resultsChanged.connect(results.append)

        vm.load()

        assert results == [rows]

    def test_load_passes_filter_sort_reverse_through(self, qtbot, monkeypatch):
        vm = ListingViewModel(_connected_ctx(), worker_factory=FakeWorker)
        captured = {}

        def fake_get_apps(client, serial, filter_kind="all", sort_by="name", reverse=False):
            captured["args"] = (filter_kind, sort_by, reverse)
            return []

        monkeypatch.setattr("droidbridge.gui.viewmodels.apps.listing.apps_ops.get_apps", fake_get_apps)

        vm.load(filter_kind="system", sort_by="total", reverse=True)

        assert captured["args"] == ("system", "total", True)

    def test_load_emits_busy_changed(self, qtbot, monkeypatch):
        vm = ListingViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.apps.listing.apps_ops.get_apps", lambda *a, **kw: [])
        busy = []
        vm.busyChanged.connect(busy.append)

        vm.load()

        assert busy == [True, False]

    def test_error_emits_status_and_log_message(self, qtbot, monkeypatch):
        vm = ListingViewModel(_connected_ctx(), worker_factory=FakeWorker)

        def boom(*a, **kw):
            raise RuntimeError("boom")

        monkeypatch.setattr("droidbridge.gui.viewmodels.apps.listing.apps_ops.get_apps", boom)
        statuses = []
        logs = []
        vm.statusChanged.connect(statuses.append)
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))

        vm.load()

        assert statuses == ["boom"]
        assert logs == [("boom", "ERROR")]


class TestListingPanel:
    def test_refresh_button_triggers_load_with_combo_values(self, qtbot, monkeypatch):
        panel = ListingPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.filter_combo.setCurrentIndex(1)  # "System"
        panel.sort_combo.setCurrentIndex(1)  # "Total"
        panel.descending_checkbox.setChecked(True)
        calls = []
        monkeypatch.setattr(
            panel.viewmodel, "load",
            lambda filter_kind="all", sort_by="name", reverse=False: calls.append((filter_kind, sort_by, reverse)),
        )

        panel.refresh_button.click()

        assert calls == [("system", "total", True)]

    def test_refresh_method_triggers_load_with_combo_values(self, qtbot, monkeypatch):
        panel = ListingPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.filter_combo.setCurrentIndex(2)  # "User"
        panel.sort_combo.setCurrentIndex(0)  # "Name"
        calls = []
        monkeypatch.setattr(
            panel.viewmodel, "load",
            lambda filter_kind="all", sort_by="name", reverse=False: calls.append((filter_kind, sort_by, reverse)),
        )

        panel.refresh()

        assert calls == [("user", "name", False)]

    def test_results_changed_populates_table(self, qtbot):
        panel = ListingPanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.resultsChanged.emit(_rows(2))

        assert panel.apps_table.rowCount() == 2
        assert panel.apps_table.item(0, 0).text() == "com.app0"

    def test_selecting_row_emits_app_selected_with_package(self, qtbot):
        panel = ListingPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultsChanged.emit(_rows(2))
        selected = []
        panel.appSelected.connect(selected.append)

        panel.apps_table.selectRow(1)

        assert selected == ["com.app1"]

    def test_clear_selection_emits_empty_string(self, qtbot):
        panel = ListingPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultsChanged.emit(_rows(1))
        panel.apps_table.selectRow(0)
        selected = []
        panel.appSelected.connect(selected.append)

        panel.clear_selection()

        assert selected[-1] == ""

    def test_update_row_status_mutates_table_cell_without_reload(self, qtbot):
        panel = ListingPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultsChanged.emit(_rows(2))

        panel.update_row_status("com.app0", is_disabled=True)

        assert panel.apps_table.item(0, 9).text() == "Disabled"

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = ListingPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()

        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()
