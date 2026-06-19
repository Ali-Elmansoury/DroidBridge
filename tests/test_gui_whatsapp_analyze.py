# tests/test_gui_whatsapp_analyze.py
import datetime
from unittest.mock import MagicMock
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.whatsapp.analyze import AnalyzeViewModel
from droidbridge.gui.pages.whatsapp.analyze import AnalyzePanel
from tests.test_gui_viewmodels_device import FakeWorker
from PyQt6.QtCore import Qt

def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestAnalyzeViewModel:
    def test_analyze_emits_results_changed(self, qtbot, monkeypatch):
        vm = AnalyzeViewModel(_connected_ctx(), worker_factory=FakeWorker)
        rows = [{"folder_type": "Images", "pre_count": 2, "pre_size_str": "1 KB",
                 "post_count": 3, "post_size_str": "2 KB", "unknown_count": 0, "unknown_size_str": "0 B"}]
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.analyze.whatsapp_ops.run_analyze",
                            lambda *a, **kw: rows)
        results = []
        vm.resultsChanged.connect(results.append)
        vm.analyze("whatsapp", datetime.date(2024, 9, 1))
        assert results == [rows]

    def test_analyze_emits_busy_changed(self, qtbot, monkeypatch):
        vm = AnalyzeViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.analyze.whatsapp_ops.run_analyze",
                            lambda *a, **kw: [])
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.analyze("whatsapp", datetime.date(2024, 9, 1))
        assert busy == [True, False]


class TestAnalyzePanel:
    def test_default_cutoff_is_2024_09_01(self, qtbot):
        panel = AnalyzePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert panel.cutoff_date.date().toPyDate() == datetime.date(2024, 9, 1)

    def test_analyze_button_triggers_viewmodel(self, qtbot, monkeypatch):
        panel = AnalyzePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "analyze", lambda app, cutoff: calls.append((app, cutoff)))
        qtbot.mouseClick(panel.analyze_button, Qt.MouseButton.LeftButton)
        assert calls[0][0] == "whatsapp"
        assert calls[0][1] == datetime.date(2024, 9, 1)

    def test_results_changed_populates_table(self, qtbot):
        panel = AnalyzePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        rows = [{"folder_type": "Images", "pre_count": 2, "pre_size_str": "1 KB",
                 "post_count": 3, "post_size_str": "2 KB", "unknown_count": 0, "unknown_size_str": "0 B"}]
        panel.viewmodel.resultsChanged.emit(rows)
        assert panel.results_table.rowCount() == 1
        assert panel.results_table.item(0, 0).text() == "Images"

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = AnalyzePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.show()  # isVisible() checks require the top-level widget to be shown
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()
