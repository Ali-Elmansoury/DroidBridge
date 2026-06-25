from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.backup.restore import RestoreViewModel
from droidbridge.modules.backup_manager import BackupProfile
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


_RESTORE_RESULTS = [
    {"source": "/sdcard/DCIM", "done": 5, "total": 5, "failed": 0, "verified": True}
]


class TestRestoreViewModel:
    def test_list_sources_returns_profile_sources(self, qtbot, monkeypatch):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        profile = BackupProfile(name="nightly", sources=["/sdcard/DCIM", "/sdcard/Download"], dest="/d", conflict="skip", excludes=[])
        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.restore.backup_ops.get_profile", lambda name: profile)
        assert vm.list_sources("nightly") == ["/sdcard/DCIM", "/sdcard/Download"]

    def test_list_sources_returns_empty_for_missing_profile(self, qtbot, monkeypatch):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.restore.backup_ops.get_profile", lambda name: None)
        assert vm.list_sources("missing") == []

    def test_run_restore_emits_results_and_status(self, qtbot, monkeypatch):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.restore.backup_ops.run_restore",
            lambda *a, **kw: [{"source": "/sdcard/DCIM", "done": 3, "total": 3, "failed": 0, "verified": True}],
        )
        results = []
        statuses = []
        vm.resultsChanged.connect(results.append)
        vm.statusChanged.connect(statuses.append)
        vm.run_restore("nightly", ["/sdcard/DCIM"], None, None, None, False)
        assert results == [[{"source": "/sdcard/DCIM", "done": 3, "total": 3, "failed": 0, "verified": True}]]
        assert "3" in statuses[-1]

    def test_run_restore_emits_busy(self, qtbot, monkeypatch):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.restore.backup_ops.run_restore", lambda *a, **kw: [])
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.run_restore("nightly", [], None, None, None, False)
        assert busy == [True, False]

    def test_error_is_logged(self, qtbot, monkeypatch):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)

        def fake_run(*a, **kw):
            raise ValueError("Profile 'nightly' not found.")

        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.restore.backup_ops.run_restore", fake_run)
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))
        vm.run_restore("nightly", [], None, None, None, False)
        assert ("Profile 'nightly' not found.", "ERROR") in logs


from PyQt6.QtCore import QDate, Qt

from droidbridge.gui.pages.backup.restore import RestorePanel


class TestRestorePanel:
    def test_refresh_sources_populates_checked_list(self, qtbot, monkeypatch):
        panel = RestorePanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        monkeypatch.setattr(panel.viewmodel, "list_sources", lambda name: ["/sdcard/DCIM", "/sdcard/Download"])
        panel.refresh_sources()
        assert panel.sources_list.count() == 2
        assert panel.sources_list.item(0).checkState() == Qt.CheckState.Checked

    def test_restore_button_passes_selected_sources_only(self, qtbot, monkeypatch):
        panel = RestorePanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        monkeypatch.setattr(panel.viewmodel, "list_sources", lambda name: ["/sdcard/DCIM", "/sdcard/Download"])
        panel.refresh_sources()
        panel.sources_list.item(1).setCheckState(Qt.CheckState.Unchecked)

        calls = []
        monkeypatch.setattr(panel.viewmodel, "run_restore", lambda *a: calls.append(a))
        qtbot.mouseClick(panel.restore_button, Qt.MouseButton.LeftButton)
        assert calls[0][1] == ["/sdcard/DCIM"]

    def test_restore_button_passes_none_dates_when_filter_unchecked(self, qtbot, monkeypatch):
        panel = RestorePanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "run_restore", lambda *a: calls.append(a))
        qtbot.mouseClick(panel.restore_button, Qt.MouseButton.LeftButton)
        assert calls[0][2] is None
        assert calls[0][3] is None

    def test_restore_button_passes_dates_when_filter_checked(self, qtbot, monkeypatch):
        panel = RestorePanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        panel.date_filter_checkbox.setChecked(True)
        panel.after_date_edit.setDate(QDate(2026, 1, 1))
        panel.before_date_edit.setDate(QDate(2026, 6, 1))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "run_restore", lambda *a: calls.append(a))
        qtbot.mouseClick(panel.restore_button, Qt.MouseButton.LeftButton)
        assert calls[0][2].isoformat() == "2026-01-01"
        assert calls[0][3].isoformat() == "2026-06-01"

    def test_results_changed_populates_table(self, qtbot):
        panel = RestorePanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        panel.viewmodel.resultsChanged.emit([{"source": "/sdcard/DCIM", "done": 3, "total": 3, "failed": 0, "verified": True}])
        assert panel.results_table.rowCount() == 1
        assert panel.results_table.item(0, 0).text() == "/sdcard/DCIM"

    def test_export_button_exists_and_disabled_initially(self, qtbot):
        panel = RestorePanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        assert hasattr(panel, "export_button")
        assert not panel.export_button.isEnabled()

    def test_export_button_enabled_after_restore_results(self, qtbot):
        panel = RestorePanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        panel.viewmodel.resultsChanged.emit(_RESTORE_RESULTS)
        assert panel.export_button.isEnabled()

    def test_export_writes_csv_with_result_rows(self, qtbot, tmp_path):
        import csv
        from unittest.mock import patch
        panel = RestorePanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        panel.viewmodel.resultsChanged.emit(_RESTORE_RESULTS)
        out = str(tmp_path / "out.csv")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=(out, "")):
            with patch("droidbridge.gui.widgets.export_button.QMessageBox.information"):
                panel._on_export_clicked()
        with open(out, newline="", encoding="utf-8") as f:
            all_rows = list(csv.reader(f))
        assert ["Source", "Done", "Total", "Failed", "Verified"] in all_rows
        sources = [r[0] for r in all_rows if r and r[0].startswith("/sdcard")]
        assert "/sdcard/DCIM" in sources
