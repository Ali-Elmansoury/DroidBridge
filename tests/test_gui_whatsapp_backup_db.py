# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import functools
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.whatsapp.backup_db import BackupDbViewModel
from droidbridge.gui.pages.whatsapp.backup_db import BackupDbPanel
from tests.test_gui_viewmodels_device import FakeWorker
from droidbridge.modules.transfer import TransferProgress
from droidbridge.modules.whatsapp import MSGSTORE_WARNING

def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestBackupDbViewModel:
    def test_backup_db_emits_status_on_complete(self, qtbot, monkeypatch):
        vm = BackupDbViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.whatsapp.backup_db.whatsapp_ops.run_backup_db",
            lambda *a, **kw: {"done": 4, "total": 4, "failed": 0, "verified": True},
        )
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.backup_db("whatsapp", "/dest", "skip", True)
        assert any("4" in s for s in statuses)

    def test_backup_db_emits_progress(self, qtbot, monkeypatch):
        vm = BackupDbViewModel(_connected_ctx(), worker_factory=FakeWorker)
        progress_obj = TransferProgress(total_files=4, total_bytes=400)
        progress_obj.done_files = 2

        def fake_run(*args, progress_callback=None, **kwargs):
            if progress_callback:
                progress_callback(progress_obj)
            return {"done": 4, "total": 4, "failed": 0, "verified": None}

        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.backup_db.whatsapp_ops.run_backup_db", fake_run)
        events = []
        vm.progressChanged.connect(lambda d, t: events.append((d, t)))
        vm.backup_db("whatsapp", "/dest", "skip", False)
        assert (2, 4) in events

    def test_backup_db_emits_busy(self, qtbot, monkeypatch):
        vm = BackupDbViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.whatsapp.backup_db.whatsapp_ops.run_backup_db",
            lambda *a, **kw: {"done": 0, "total": 0, "failed": 0, "verified": None},
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.backup_db("whatsapp", "/dest", "skip", False)
        assert busy == [True, False]


class TestBackupDbPanel:
    def test_default_verify_checkbox_is_checked(self, qtbot):
        panel = BackupDbPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert panel.verify_checkbox.isChecked()

    def test_backup_db_button_triggers_viewmodel(self, qtbot, monkeypatch, tmp_path):
        panel = BackupDbPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.dest_edit.setText(str(tmp_path))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "backup_db",
                            lambda app, dest, conflict, verify: calls.append((app, dest)))
        qtbot.mouseClick(panel.backup_db_button, Qt.MouseButton.LeftButton)
        assert calls[0] == ("whatsapp", str(tmp_path))

    def test_progress_changed_updates_label(self, qtbot):
        panel = BackupDbPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.viewmodel.progressChanged.emit(2, 4)
        assert "2" in panel.progress_label.text()
        assert "4" in panel.progress_label.text()

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = BackupDbPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.show()  # isVisible() checks require the top-level widget to be shown
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()

    def test_scope_note_discloses_backed_up_folders_and_msgstore_warning(self, qtbot):
        # Real-device validation surfaced that "Backup Databases" silently
        # pulls Databases/, Backups/, and accounts/ (DB_BACKUP_FOLDERS) -
        # Backups/ can include sticker-pack files and balloon the file
        # count far past what "databases" implies. The panel must disclose
        # this scope and the CLI's MSGSTORE_WARNING up front.
        panel = BackupDbPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert "Databases" in panel.scope_label.text()
        assert "Backups" in panel.scope_label.text()
        assert "accounts" in panel.scope_label.text()
        assert MSGSTORE_WARNING in panel.scope_label.text()
