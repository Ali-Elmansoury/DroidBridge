import functools
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.whatsapp.backup import BackupViewModel
from droidbridge.gui.pages.whatsapp.backup import BackupPanel
from tests.test_gui_viewmodels_device import FakeWorker
from droidbridge.modules.transfer import TransferProgress

def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestBackupViewModel:
    def test_backup_emits_status_on_complete(self, qtbot, monkeypatch):
        vm = BackupViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.backup.whatsapp_ops.run_backup",
                            lambda *a, **kw: {"done": 5, "total": 5, "failed": 0, "verified": True})
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.backup("whatsapp", "/dest", None, "skip", True)
        assert any("5" in s for s in statuses)

    def test_backup_emits_progress_changed(self, qtbot, monkeypatch):
        vm = BackupViewModel(_connected_ctx(), worker_factory=FakeWorker)
        progress_obj = TransferProgress(total_files=10, total_bytes=1000)
        progress_obj.done_files = 3

        def fake_run_backup(*args, progress_callback=None, **kwargs):
            if progress_callback:
                progress_callback(progress_obj)
            return {"done": 10, "total": 10, "failed": 0, "verified": None}

        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.backup.whatsapp_ops.run_backup", fake_run_backup)
        progress_events = []
        vm.progressChanged.connect(lambda d, t: progress_events.append((d, t)))
        vm.backup("whatsapp", "/dest", None, "skip", False)
        assert (3, 10) in progress_events

    def test_backup_emits_busy_changed(self, qtbot, monkeypatch):
        vm = BackupViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.backup.whatsapp_ops.run_backup",
                            lambda *a, **kw: {"done": 0, "total": 0, "failed": 0, "verified": None})
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.backup("whatsapp", "/dest", None, "skip", False)
        assert busy == [True, False]


class TestBackupPanel:
    def test_default_verify_checkbox_is_checked(self, qtbot):
        panel = BackupPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert panel.verify_checkbox.isChecked()

    def test_backup_button_triggers_viewmodel(self, qtbot, monkeypatch, tmp_path):
        panel = BackupPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.dest_edit.setText(str(tmp_path))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "backup",
                            lambda app, dest, types, conflict, verify: calls.append((app, dest)))
        qtbot.mouseClick(panel.backup_button, Qt.MouseButton.LeftButton)
        assert calls[0] == ("whatsapp", str(tmp_path))

    def test_progress_changed_updates_progress_label(self, qtbot):
        panel = BackupPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.viewmodel.progressChanged.emit(3, 10)
        assert "3" in panel.progress_label.text()
        assert "10" in panel.progress_label.text()

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = BackupPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.show()  # isVisible() checks require the top-level widget to be shown
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()
