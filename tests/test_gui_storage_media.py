# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import datetime
from unittest.mock import MagicMock
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.storage.media import MediaViewModel
from droidbridge.gui.pages.storage.media import MediaPanel
from tests.test_gui_viewmodels_device import FakeWorker
from PyQt6.QtCore import Qt


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


_RESULT = {
    "total_count": 3,
    "total_size_str": "1.5 KB",
    "categories": [{"type": "photos", "count": 2, "size_str": "600 B"}],
    "largest_files": [{"size_str": "900 B", "path": "/sdcard/big.mp4"}],
    "duplicate_groups": [
        {"name": "a.jpg", "size_str": "300 B", "count": 2, "paths": ["/sdcard/a.jpg", "/sdcard/b/a.jpg"]}
    ],
    "duplicate_overflow": 0,
}


class TestMediaViewModel:
    def test_scan_emits_result_changed(self, qtbot, monkeypatch):
        vm = MediaViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.media.storage_ops.get_media",
            lambda *a, **kw: _RESULT,
        )
        results = []
        vm.resultChanged.connect(results.append)
        vm.scan("/sdcard")
        assert results == [_RESULT]

    def test_scan_passes_root_and_before_through(self, qtbot, monkeypatch):
        vm = MediaViewModel(_connected_ctx(), worker_factory=FakeWorker)
        captured = {}

        def fake_get_media(client, serial, root, before=None):
            captured["root"] = root
            captured["before"] = before
            return _RESULT

        monkeypatch.setattr("droidbridge.gui.viewmodels.storage.media.storage_ops.get_media", fake_get_media)
        before = datetime.datetime(2024, 6, 1)
        vm.scan("/sdcard/DCIM", before=before)
        assert captured["root"] == "/sdcard/DCIM"
        assert captured["before"] == before

    def test_scan_emits_busy_changed(self, qtbot, monkeypatch):
        vm = MediaViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.storage.media.storage_ops.get_media",
            lambda *a, **kw: _RESULT,
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.scan("/sdcard")
        assert busy == [True, False]


class TestMediaPanel:
    def test_root_edit_defaults_to_sdcard(self, qtbot):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        assert panel.root_edit.text() == "/sdcard"

    def test_before_date_edit_disabled_until_checkbox_checked(self, qtbot):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        assert not panel.before_date_edit.isEnabled()
        panel.before_checkbox.setChecked(True)
        assert panel.before_date_edit.isEnabled()

    def test_scan_button_triggers_viewmodel_without_before_when_unchecked(self, qtbot, monkeypatch):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "scan", lambda root, before=None: calls.append((root, before)))
        qtbot.mouseClick(panel.scan_button, Qt.MouseButton.LeftButton)
        assert calls == [("/sdcard", None)]

    def test_scan_button_passes_before_when_checked(self, qtbot, monkeypatch):
        import datetime
        from PyQt6.QtCore import QDate

        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.before_checkbox.setChecked(True)
        panel.before_date_edit.setDate(QDate(2024, 6, 1))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "scan", lambda root, before=None: calls.append((root, before)))
        qtbot.mouseClick(panel.scan_button, Qt.MouseButton.LeftButton)
        assert calls[0][0] == "/sdcard"
        assert calls[0][1] == datetime.datetime(2024, 6, 1)

    def test_result_changed_populates_summary_and_tables(self, qtbot):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        assert "3" in panel.summary_label.text()
        assert "1.5 KB" in panel.summary_label.text()
        assert panel.categories_table.rowCount() == 1
        assert panel.categories_table.item(0, 0).text() == "photos"
        assert panel.largest_files_table.rowCount() == 1
        assert panel.largest_files_table.item(0, 1).text() == "/sdcard/big.mp4"
        assert panel.duplicates_table.rowCount() == 1
        assert panel.duplicates_table.item(0, 0).text() == "a.jpg"
        assert not panel.duplicates_overflow_label.isVisible()

    def test_selecting_duplicate_group_populates_paths_list(self, qtbot):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        panel.duplicates_table.selectRow(0)
        assert panel.duplicates_paths_list.count() == 2
        items = [panel.duplicates_paths_list.item(i).text() for i in range(2)]
        assert "/sdcard/a.jpg" in items
        assert "/sdcard/b/a.jpg" in items

    def test_overflow_label_shown_when_overflow_present(self, qtbot):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        result = dict(_RESULT, duplicate_overflow=4)
        panel.viewmodel.resultChanged.emit(result)
        assert panel.duplicates_overflow_label.isVisible()
        assert "4" in panel.duplicates_overflow_label.text()

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()

    def test_export_button_exists_and_disabled_initially(self, qtbot):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        assert hasattr(panel, "export_button")
        assert not panel.export_button.isEnabled()

    def test_export_button_enabled_after_scan(self, qtbot):
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        assert panel.export_button.isEnabled()

    def test_export_writes_csv_with_all_three_sections(self, qtbot, tmp_path):
        import csv
        from unittest.mock import patch
        panel = MediaPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(_RESULT)
        out = str(tmp_path / "out.csv")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=(out, "CSV (*.csv)")):
            with patch("droidbridge.gui.widgets.export_button.QMessageBox.information"):
                panel._on_export_clicked()
        with open(out, newline="", encoding="utf-8") as f:
            all_rows = list(csv.reader(f))
        flat = [cell for row in all_rows for cell in row]
        assert "Categories" in flat
        assert "Largest Files" in flat
        assert "Duplicate Groups" in flat
        assert "photos" in flat
        assert "/sdcard/big.mp4" in flat
        assert "a.jpg" in flat
