# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
# tests/test_gui_whatsapp_scan.py
from unittest.mock import MagicMock, patch
import pytest
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.whatsapp.scan import ScanViewModel
from droidbridge.gui.pages.whatsapp.scan import ScanPanel
from tests.test_gui_viewmodels_device import FakeWorker

def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestScanViewModel:
    def test_scan_emits_results_changed(self, qtbot, monkeypatch):
        vm = ScanViewModel(_connected_ctx(), worker_factory=FakeWorker)
        rows = [{"folder_type": "Images", "section": "Received", "file_count": 3, "total_size_str": "1.0 KB"}]
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.scan.whatsapp_ops.run_scan",
                            lambda *a, **kw: rows)
        results = []
        vm.resultsChanged.connect(results.append)
        vm.scan("whatsapp", "folder")
        assert results == [rows]

    def test_scan_emits_busy_changed(self, qtbot, monkeypatch):
        vm = ScanViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.scan.whatsapp_ops.run_scan",
                            lambda *a, **kw: [])
        busy_events = []
        vm.busyChanged.connect(busy_events.append)
        vm.scan("whatsapp", "folder")
        assert busy_events == [True, False]

    def test_scan_error_emits_status_changed(self, qtbot, monkeypatch):
        vm = ScanViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.scan.whatsapp_ops.run_scan",
                            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("adb fail")))
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.scan("whatsapp", "folder")
        assert any("adb fail" in s for s in statuses)


class TestScanPanel:
    def test_breakdown_combo_has_three_items(self, qtbot):
        panel = ScanPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert panel.breakdown_combo.count() == 3

    def test_scan_button_triggers_viewmodel_scan(self, qtbot, monkeypatch):
        panel = ScanPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "scan", lambda app, breakdown: calls.append((app, breakdown)))
        qtbot.mouseClick(panel.scan_button, __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.MouseButton.LeftButton)
        assert calls == [("whatsapp", "folder")]

    def test_results_changed_populates_table(self, qtbot):
        panel = ScanPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        rows = [{"folder_type": "Images", "section": "Received", "file_count": 5, "total_size_str": "1 KB"}]
        panel.viewmodel.resultsChanged.emit(rows)
        assert panel.results_table.rowCount() == 1
        assert panel.results_table.item(0, 0).text() == "Images"

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = ScanPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.show()  # isVisible() checks require the top-level widget to be shown
        assert not panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()

    def test_status_changed_updates_status_label(self, qtbot):
        panel = ScanPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.viewmodel.statusChanged.emit("Scan complete")
        assert panel.status_label.text() == "Scan complete"
