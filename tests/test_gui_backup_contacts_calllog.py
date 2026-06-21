from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.backup.contacts_calllog import ContactsCallLogViewModel
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestContactsCallLogViewModel:
    def test_export_contacts_emits_status_summary(self, qtbot, monkeypatch):
        vm = ContactsCallLogViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.contacts_calllog.phone_data_ops.run_export_contacts",
            lambda *a, **kw: {"phone": {"exported": 5, "skipped": 0}, "sim": {"exported": 0, "skipped": 0}},
        )
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.export_contacts(["phone", "sim"], "/tmp/out")
        assert "phone: 5 exported, 0 skipped" in statuses[-1]
        assert "sim: 0 exported, 0 skipped" in statuses[-1]

    def test_export_call_log_emits_status_summary(self, qtbot, monkeypatch):
        vm = ContactsCallLogViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.contacts_calllog.phone_data_ops.run_export_call_log",
            lambda *a, **kw: {"exported": 7, "skipped": 1},
        )
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.export_call_log("/tmp/out")
        assert "7 exported, 1 skipped" in statuses[-1]

    def test_export_contacts_emits_busy(self, qtbot, monkeypatch):
        vm = ContactsCallLogViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.contacts_calllog.phone_data_ops.run_export_contacts",
            lambda *a, **kw: {},
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.export_contacts(["phone"], "/tmp/out")
        assert busy == [True, False]

    def test_error_is_logged(self, qtbot, monkeypatch):
        vm = ContactsCallLogViewModel(_connected_ctx(), worker_factory=FakeWorker)

        def fake_run(*a, **kw):
            raise RuntimeError("adb shell failed")

        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.contacts_calllog.phone_data_ops.run_export_contacts", fake_run
        )
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))
        vm.export_contacts(["phone"], "/tmp/out")
        assert ("adb shell failed", "ERROR") in logs
