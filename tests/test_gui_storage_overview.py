# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from unittest.mock import MagicMock
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.storage.overview import OverviewViewModel
from droidbridge.gui.pages.storage.overview import OverviewPanel
from tests.test_gui_viewmodels_device import FakeWorker
from PyQt6.QtCore import Qt


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


_RESULT = {
    "total_str": "100.0 GB", "used_str": "40.0 GB", "free_str": "60.0 GB", "percent": 40,
    "categories": [{"label": "Apps", "size_str": "10.0 GB"}, {"label": "Photos", "size_str": "5.0 GB"}],
}


class TestOverviewViewModel:
    def test_refresh_emits_result_changed(self, qtbot, monkeypatch):
        vm = OverviewViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.overview.storage_ops.get_overview",
            lambda *a, **kw: _RESULT,
        )
        results = []
        vm.resultChanged.connect(results.append)
        vm.refresh()
        assert results == [_RESULT]

    def test_refresh_emits_busy_changed(self, qtbot, monkeypatch):
        vm = OverviewViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.overview.storage_ops.get_overview",
            lambda *a, **kw: _RESULT,
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.refresh()
        assert busy == [True, False]

    def test_error_emits_log_message(self, qtbot, monkeypatch):
        vm = OverviewViewModel(_connected_ctx(), worker_factory=FakeWorker)

        def raise_error(*a, **kw):
            raise RuntimeError("boom")

        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.overview.storage_ops.get_overview", raise_error
        )
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))
        vm.refresh()
        assert logs == [("boom", "ERROR")]


class TestOverviewPanel:
    def test_refresh_button_triggers_viewmodel(self, qtbot, monkeypatch):
        panel = OverviewPanel(_connected_ctx())
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "refresh", lambda: calls.append(True))
        qtbot.mouseClick(panel.refresh_button, Qt.MouseButton.LeftButton)
        assert calls == [True]

    def test_result_changed_populates_labels_and_table(self, qtbot):
        panel = OverviewPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        assert panel.total_label.text() == "100.0 GB"
        assert panel.used_label.text() == "40.0 GB"
        assert panel.free_label.text() == "60.0 GB"
        assert panel.usage_bar.value() == 40
        assert panel.categories_table.rowCount() == 2
        assert panel.categories_table.item(0, 0).text() == "Apps"
        assert panel.categories_table.item(0, 1).text() == "10.0 GB"

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = OverviewPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()
