# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from unittest.mock import MagicMock
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.storage.cleanup import CleanupViewModel
from droidbridge.gui.pages.storage.cleanup import CleanupPanel
from tests.test_gui_viewmodels_device import FakeWorker
from PyQt6.QtCore import Qt


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


_RESULT = {
    "suggestions": [
        {
            "title": "Clear app caches",
            "description": "12 app(s) have large caches.",
            "estimated_bytes_str": "300.0 MB",
            "item_count": 12,
            "items": ["com.example.app1", "com.example.app2"],
            "item_overflow": 0,
        }
    ],
    "total_str": "300.0 MB",
}


class TestCleanupViewModel:
    def test_refresh_emits_result_changed(self, qtbot, monkeypatch):
        vm = CleanupViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.cleanup.storage_ops.get_cleanup_suggestions",
            lambda *a, **kw: _RESULT,
        )
        results = []
        vm.resultChanged.connect(results.append)
        vm.refresh()
        assert results == [_RESULT]

    def test_refresh_passes_client_and_serial_through(self, qtbot, monkeypatch):
        vm = CleanupViewModel(_connected_ctx(), worker_factory=FakeWorker)
        captured = {}

        def fake_get_cleanup_suggestions(client, serial):
            captured["serial"] = serial
            return _RESULT

        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.cleanup.storage_ops.get_cleanup_suggestions",
            fake_get_cleanup_suggestions,
        )
        vm.refresh()
        assert captured["serial"] == "S1"

    def test_refresh_emits_busy_changed(self, qtbot, monkeypatch):
        vm = CleanupViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.cleanup.storage_ops.get_cleanup_suggestions",
            lambda *a, **kw: _RESULT,
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.refresh()
        assert busy == [True, False]


class TestCleanupPanel:
    def test_refresh_button_triggers_viewmodel(self, qtbot, monkeypatch):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "refresh", lambda: calls.append(True))
        qtbot.mouseClick(panel.refresh_button, Qt.MouseButton.LeftButton)
        assert calls == [True]

    def test_result_changed_populates_table_and_total(self, qtbot):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        assert panel.suggestions_table.rowCount() == 1
        assert panel.suggestions_table.item(0, 0).text() == "Clear app caches"
        assert panel.suggestions_table.item(0, 2).text() == "300.0 MB"
        assert "300.0 MB" in panel.total_label.text()
        assert not panel.empty_label.isVisible()

    def test_selecting_suggestion_populates_items_list(self, qtbot):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        panel.suggestions_table.selectRow(0)
        assert panel.items_list.count() == 2
        items = [panel.items_list.item(i).text() for i in range(2)]
        assert "com.example.app1" in items

    def test_items_overflow_label_shown_when_overflow_present(self, qtbot):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        result = {
            "suggestions": [dict(_RESULT["suggestions"][0], item_overflow=5)],
            "total_str": "300.0 MB",
        }
        panel.viewmodel.resultChanged.emit(result)
        panel.suggestions_table.selectRow(0)
        assert panel.items_overflow_label.isVisible()
        assert "5" in panel.items_overflow_label.text()

    def test_result_changed_shows_empty_label_when_no_suggestions(self, qtbot):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.resultChanged.emit({"suggestions": [], "total_str": "0 B"})
        assert panel.empty_label.isVisible()
        assert panel.empty_label.text() == "No cleanup suggestions found."

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()

    def test_export_button_exists_and_disabled_initially(self, qtbot):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        assert hasattr(panel, "export_button")
        assert not panel.export_button.isEnabled()

    def test_export_button_enabled_after_results(self, qtbot):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        assert panel.export_button.isEnabled()

    def test_export_button_disabled_after_empty_results(self, qtbot):
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        panel.viewmodel.resultChanged.emit({"suggestions": [], "total_str": "0 B"})
        assert not panel.export_button.isEnabled()

    def test_export_writes_csv_with_suggestions(self, qtbot, tmp_path):
        import csv
        from unittest.mock import patch
        panel = CleanupPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        out = str(tmp_path / "out.csv")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=(out, "CSV (*.csv)")):
            with patch("droidbridge.gui.widgets.export_button.QMessageBox.information"):
                panel._on_export_clicked()
        with open(out, newline="", encoding="utf-8") as f:
            all_rows = list(csv.reader(f))
        assert ["Title", "Description", "Estimated Recoverable", "Item Count"] in all_rows
        titles = [r[0] for r in all_rows if r]
        assert "Clear app caches" in titles
