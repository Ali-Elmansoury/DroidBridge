# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from droidbridge.gui.viewmodels.backup.verify import VerifyViewModel
from tests.test_gui_viewmodels_device import FakeWorker


class TestVerifyViewModel:
    def test_run_verify_emits_result_and_ok_status(self, qtbot, monkeypatch):
        vm = VerifyViewModel(worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.verify.backup_ops.run_verify",
            lambda profile_name: {"ok": True, "expected_files": 1, "expected_bytes": 100, "actual_files": 1, "actual_bytes": 100},
        )
        results = []
        statuses = []
        vm.resultChanged.connect(results.append)
        vm.statusChanged.connect(statuses.append)
        vm.run_verify("nightly")
        assert results == [{"ok": True, "expected_files": 1, "expected_bytes": 100, "actual_files": 1, "actual_bytes": 100}]
        assert "OK" in statuses[-1]

    def test_run_verify_emits_mismatch_status_and_error_log(self, qtbot, monkeypatch):
        vm = VerifyViewModel(worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.verify.backup_ops.run_verify",
            lambda profile_name: {"ok": False, "expected_files": 2, "expected_bytes": 200, "actual_files": 1, "actual_bytes": 100},
        )
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append(level))
        vm.run_verify("nightly")
        assert "ERROR" in logs

    def test_run_verify_emits_busy(self, qtbot, monkeypatch):
        vm = VerifyViewModel(worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.verify.backup_ops.run_verify",
            lambda profile_name: {"ok": True, "expected_files": 0, "expected_bytes": 0, "actual_files": 0, "actual_bytes": 0},
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.run_verify("nightly")
        assert busy == [True, False]

    def test_error_is_logged(self, qtbot, monkeypatch):
        vm = VerifyViewModel(worker_factory=FakeWorker)

        def fake_run(profile_name):
            raise ValueError("Profile 'nightly' not found.")

        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.verify.backup_ops.run_verify", fake_run)
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))
        vm.run_verify("nightly")
        assert ("Profile 'nightly' not found.", "ERROR") in logs


from PyQt6.QtCore import Qt

from droidbridge.gui.pages.backup.verify import VerifyPanel


class TestVerifyPanel:
    def test_verify_button_calls_viewmodel_with_selected_profile(self, qtbot, monkeypatch):
        panel = VerifyPanel(lambda: "nightly")
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "run_verify", calls.append)
        qtbot.mouseClick(panel.verify_button, Qt.MouseButton.LeftButton)
        assert calls == ["nightly"]

    def test_result_changed_updates_result_label(self, qtbot):
        panel = VerifyPanel(lambda: "nightly")
        qtbot.addWidget(panel)
        panel.viewmodel.resultChanged.emit(
            {"ok": True, "expected_files": 1, "expected_bytes": 100, "actual_files": 1, "actual_bytes": 100}
        )
        assert "1" in panel.result_label.text()

    def test_status_changed_updates_status_label(self, qtbot):
        panel = VerifyPanel(lambda: "nightly")
        qtbot.addWidget(panel)
        panel.viewmodel.statusChanged.emit("Verification OK")
        assert panel.status_label.text() == "Verification OK"
