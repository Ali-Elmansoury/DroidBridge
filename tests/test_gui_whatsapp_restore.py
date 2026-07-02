# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import functools
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.whatsapp.restore import RestoreViewModel
from droidbridge.gui.pages.whatsapp.restore import RestorePanel
from tests.test_gui_viewmodels_device import FakeWorker
from droidbridge.modules.transfer import TransferProgress

def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestRestoreViewModel:
    def test_restore_emits_status_on_complete(self, qtbot, monkeypatch):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.restore.whatsapp_ops.run_restore",
                            lambda *a, **kw: {"done": 3, "total": 3, "failed": 0, "verified": None})
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.restore("whatsapp", "/src", "skip", False)
        assert any("3" in s for s in statuses)

    def test_restore_emits_progress_changed(self, qtbot, monkeypatch):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        progress_obj = TransferProgress(total_files=5, total_bytes=500)
        progress_obj.done_files = 2

        def fake_run(*args, progress_callback=None, **kwargs):
            if progress_callback:
                progress_callback(progress_obj)
            return {"done": 5, "total": 5, "failed": 0, "verified": None}

        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.restore.whatsapp_ops.run_restore", fake_run)
        events = []
        vm.progressChanged.connect(lambda d, t: events.append((d, t)))
        vm.restore("whatsapp", "/src", "skip", False)
        assert (2, 5) in events

    def test_restore_emits_busy_changed(self, qtbot, monkeypatch):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.restore.whatsapp_ops.run_restore",
                            lambda *a, **kw: {"done": 0, "total": 0, "failed": 0, "verified": None})
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.restore("whatsapp", "/src", "skip", False)
        assert busy == [True, False]


class TestRestorePanel:
    def test_default_verify_checkbox_is_checked(self, qtbot):
        panel = RestorePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert panel.verify_checkbox.isChecked()

    def test_restore_button_triggers_viewmodel(self, qtbot, monkeypatch, tmp_path):
        panel = RestorePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.src_edit.setText(str(tmp_path))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "restore",
                            lambda app, src, conflict, verify: calls.append((app, src)))
        qtbot.mouseClick(panel.restore_button, Qt.MouseButton.LeftButton)
        assert calls[0] == ("whatsapp", str(tmp_path))

    def test_progress_changed_updates_progress_label(self, qtbot):
        panel = RestorePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.viewmodel.progressChanged.emit(2, 5)
        assert "2" in panel.progress_label.text()
        assert "5" in panel.progress_label.text()
