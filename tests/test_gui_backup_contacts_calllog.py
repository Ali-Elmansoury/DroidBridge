# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
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


from PyQt6.QtCore import Qt

from droidbridge.gui.pages.backup.contacts_calllog import ContactsCallLogPanel


class TestContactsCallLogPanel:
    def test_all_sources_checked_by_default(self, qtbot):
        panel = ContactsCallLogPanel(_connected_ctx())
        qtbot.addWidget(panel)
        assert panel.phone_checkbox.isChecked()
        assert panel.accounts_checkbox.isChecked()
        assert panel.sim_checkbox.isChecked()

    def test_export_contacts_button_excludes_unchecked_sources(self, qtbot, monkeypatch):
        panel = ContactsCallLogPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.dest_edit.setText("/tmp/out")
        panel.sim_checkbox.setChecked(False)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "export_contacts", lambda sources, dest: calls.append((sources, dest)))
        qtbot.mouseClick(panel.export_contacts_button, Qt.MouseButton.LeftButton)
        assert calls == [(["phone", "accounts"], "/tmp/out")]

    def test_export_call_log_button_passes_dest(self, qtbot, monkeypatch):
        panel = ContactsCallLogPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.dest_edit.setText("/tmp/out")
        calls = []
        monkeypatch.setattr(panel.viewmodel, "export_call_log", calls.append)
        qtbot.mouseClick(panel.export_call_log_button, Qt.MouseButton.LeftButton)
        assert calls == ["/tmp/out"]

    def test_busy_disables_both_export_buttons(self, qtbot):
        panel = ContactsCallLogPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.busyChanged.emit(True)
        assert not panel.export_contacts_button.isEnabled()
        assert not panel.export_call_log_button.isEnabled()
        panel.viewmodel.busyChanged.emit(False)
        assert panel.export_contacts_button.isEnabled()
        assert panel.export_call_log_button.isEnabled()
