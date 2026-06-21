from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.backup.restore import RestoreViewModel
from droidbridge.modules.backup_manager import BackupProfile
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


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
