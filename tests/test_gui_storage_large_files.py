from unittest.mock import MagicMock
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.storage.large_files import LargeFilesViewModel
from droidbridge.gui.pages.storage.large_files import LargeFilesPanel
from tests.test_gui_viewmodels_device import FakeWorker
from PyQt6.QtCore import Qt


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


_RESULTS = [
    {"size_str": "120.0 MB", "path": "/sdcard/movie.mp4", "modified_str": "2024-05-01 10:00"},
    {"size_str": "80.0 MB", "path": "/sdcard/archive.zip", "modified_str": "2024-04-20 09:30"},
]


class TestLargeFilesViewModel:
    def test_scan_emits_results_changed(self, qtbot, monkeypatch):
        vm = LargeFilesViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.large_files.storage_ops.get_large_files",
            lambda *a, **kw: _RESULTS,
        )
        results = []
        vm.resultsChanged.connect(results.append)
        vm.scan("/sdcard")
        assert results == [_RESULTS]

    def test_scan_passes_root_and_threshold_through(self, qtbot, monkeypatch):
        vm = LargeFilesViewModel(_connected_ctx(), worker_factory=FakeWorker)
        captured = {}

        def fake_get_large_files(client, serial, root, threshold=None):
            captured["root"] = root
            captured["threshold"] = threshold
            return _RESULTS

        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.large_files.storage_ops.get_large_files",
            fake_get_large_files,
        )
        vm.scan("/sdcard/Movies", threshold=104857600)
        assert captured["root"] == "/sdcard/Movies"
        assert captured["threshold"] == 104857600

    def test_scan_emits_busy_changed(self, qtbot, monkeypatch):
        vm = LargeFilesViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.large_files.storage_ops.get_large_files",
            lambda *a, **kw: _RESULTS,
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.scan("/sdcard")
        assert busy == [True, False]


class TestLargeFilesPanel:
    def test_root_edit_defaults_to_sdcard(self, qtbot):
        panel = LargeFilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        assert panel.root_edit.text() == "/sdcard"

    def test_min_size_edit_has_placeholder(self, qtbot):
        panel = LargeFilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        assert panel.min_size_edit.placeholderText() == "e.g. 50MB"

    def test_scan_button_triggers_viewmodel_with_blank_min_size(self, qtbot, monkeypatch):
        panel = LargeFilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "scan", lambda root, threshold=None: calls.append((root, threshold)))
        qtbot.mouseClick(panel.scan_button, Qt.MouseButton.LeftButton)
        assert calls == [("/sdcard", None)]

    def test_scan_button_parses_min_size(self, qtbot, monkeypatch):
        panel = LargeFilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.min_size_edit.setText("10MB")
        calls = []
        monkeypatch.setattr(panel.viewmodel, "scan", lambda root, threshold=None: calls.append((root, threshold)))
        qtbot.mouseClick(panel.scan_button, Qt.MouseButton.LeftButton)
        assert calls == [("/sdcard", 10 * 1024 * 1024)]

    def test_scan_button_rejects_invalid_min_size_without_calling_viewmodel(self, qtbot, monkeypatch):
        panel = LargeFilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.min_size_edit.setText("not-a-size")
        calls = []
        monkeypatch.setattr(panel.viewmodel, "scan", lambda root, threshold=None: calls.append((root, threshold)))
        warnings = []
        panel.viewmodel.logMessage.connect(lambda msg, level: warnings.append((msg, level)))
        qtbot.mouseClick(panel.scan_button, Qt.MouseButton.LeftButton)
        assert calls == []
        assert warnings and warnings[0][1] == "WARNING"

    def test_results_changed_populates_table(self, qtbot):
        panel = LargeFilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultsChanged.emit(_RESULTS)
        assert panel.results_table.rowCount() == 2
        assert panel.results_table.item(0, 1).text() == "/sdcard/movie.mp4"
        assert not panel.empty_label.isVisible()

    def test_results_changed_shows_empty_label_when_no_results(self, qtbot):
        panel = LargeFilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.resultsChanged.emit([])
        assert panel.empty_label.isVisible()
        assert panel.empty_label.text() == "No large files found."

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = LargeFilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()
