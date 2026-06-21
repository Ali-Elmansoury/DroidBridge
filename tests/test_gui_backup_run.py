from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.backup.run import RunViewModel
from droidbridge.modules.transfer import TransferProgress
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestRunViewModel:
    def test_run_backup_emits_status_on_complete(self, qtbot, monkeypatch):
        vm = RunViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.run.backup_ops.run_backup",
            lambda *a, **kw: {"done": 3, "total": 3, "failed": 0, "verified": True},
        )
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.run_backup("nightly", False)
        assert any("3" in s for s in statuses)

    def test_run_backup_emits_progress(self, qtbot, monkeypatch):
        vm = RunViewModel(_connected_ctx(), worker_factory=FakeWorker)
        progress_obj = TransferProgress(total_files=4, total_bytes=400)
        progress_obj.done_files = 2

        def fake_run(*args, progress_callback=None, **kwargs):
            if progress_callback:
                progress_callback(progress_obj)
            return {"done": 4, "total": 4, "failed": 0, "verified": None}

        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.run.backup_ops.run_backup", fake_run)
        events = []
        vm.progressChanged.connect(lambda d, t: events.append((d, t)))
        vm.run_backup("nightly", False)
        assert (2, 4) in events

    def test_run_backup_emits_busy(self, qtbot, monkeypatch):
        vm = RunViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.run.backup_ops.run_backup",
            lambda *a, **kw: {"done": 0, "total": 0, "failed": 0, "verified": None},
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.run_backup("nightly", False)
        assert busy == [True, False]

    def test_error_is_logged(self, qtbot, monkeypatch):
        vm = RunViewModel(_connected_ctx(), worker_factory=FakeWorker)

        def fake_run(*a, **kw):
            raise ValueError("Profile 'nightly' not found.")

        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.run.backup_ops.run_backup", fake_run)
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))
        vm.run_backup("nightly", False)
        assert logs == [("Profile 'nightly' not found.", "ERROR")]


from PyQt6.QtCore import Qt

from droidbridge.gui.pages.backup.run import RunPanel


class TestRunPanel:
    def test_run_button_triggers_viewmodel_with_selected_profile(self, qtbot, monkeypatch):
        panel = RunPanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "run_backup", lambda profile, no_verify: calls.append((profile, no_verify)))
        qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)
        assert calls == [("nightly", False)]

    def test_no_verify_checkbox_is_passed_through(self, qtbot, monkeypatch):
        panel = RunPanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        panel.no_verify_checkbox.setChecked(True)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "run_backup", lambda profile, no_verify: calls.append((profile, no_verify)))
        qtbot.mouseClick(panel.run_button, Qt.MouseButton.LeftButton)
        assert calls == [("nightly", True)]

    def test_progress_changed_updates_label(self, qtbot):
        panel = RunPanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        panel.viewmodel.progressChanged.emit(2, 4)
        assert "2" in panel.progress_label.text()
        assert "4" in panel.progress_label.text()

    def test_busy_shows_hides_progress_bar(self, qtbot):
        panel = RunPanel(_connected_ctx(), lambda: "nightly")
        qtbot.addWidget(panel)
        panel.show()
        panel.viewmodel.busyChanged.emit(True)
        assert panel.progress_bar.isVisible()
        panel.viewmodel.busyChanged.emit(False)
        assert not panel.progress_bar.isVisible()
