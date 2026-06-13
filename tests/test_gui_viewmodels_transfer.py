"""Tests for droidbridge.gui.viewmodels.transfer.TransferViewModel (Phase 6.2)."""

from unittest.mock import MagicMock

from droidbridge.gui import transfer_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.transfer import TransferViewModel
from droidbridge.modules import transfer as transfer_module
from tests.test_gui_viewmodels_device import FakeWorker

SAMPLE_PLAN = transfer_module.TransferPlan(
    direction="pull",
    items=[transfer_module.TransferItem(
        source="/sdcard/DCIM/a.jpg", dest="/tmp/out/a.jpg", size=100, action=transfer_module.ACTION_COPY,
    )],
)

SAMPLE_RESULT = transfer_module.TransferProgress(
    total_files=1, total_bytes=100, done_files=1, done_bytes=100, start_time=1000.0
)

SAMPLE_VERIFICATION = transfer_module.VerificationResult(
    expected_files=1, expected_bytes=100, actual_files=1, actual_bytes=100
)


def _connected_context():
    context = DeviceContext()
    context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
    return context


class TestStartPull:
    def test_emits_plan_progress_verification_and_history(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)
        calls = {}

        def fake_plan_pull_many(client, serial, remote_paths, local_dir, conflict):
            calls["plan"] = (remote_paths, local_dir, conflict)
            return [SAMPLE_PLAN]

        def fake_execute_plans(client, serial, plans, progress_callback=None, should_cancel=None):
            progress_callback(SAMPLE_RESULT)
            return SAMPLE_RESULT

        def fake_verify_plans(client, serial, plans, direction, **kwargs):
            calls["verify"] = (direction, kwargs)
            return SAMPLE_VERIFICATION

        monkeypatch.setattr(transfer_ops, "plan_pull_many", fake_plan_pull_many)
        monkeypatch.setattr(transfer_ops, "execute_plans", fake_execute_plans)
        monkeypatch.setattr(transfer_ops, "verify_plans", fake_verify_plans)

        plan_events, progress_events, verification_events, history_events = [], [], [], []
        vm.planChanged.connect(plan_events.append)
        vm.progressChanged.connect(progress_events.append)
        vm.verificationChanged.connect(verification_events.append)
        vm.historyEntryAdded.connect(history_events.append)

        vm.start_pull("/sdcard/DCIM", "/tmp/out", conflict=transfer_module.CONFLICT_SKIP, verify=True)

        assert calls["plan"] == (["/sdcard/DCIM"], "/tmp/out", transfer_module.CONFLICT_SKIP)
        assert plan_events == [{
            "total_files": 1, "total_bytes": 100, "already_present": 0, "conflicts_skipped": 0,
        }]
        assert progress_events[-1]["done_files"] == 1
        assert progress_events[-1]["done_bytes_str"] == "100 B"
        assert progress_events[-1]["total_bytes_str"] == "100 B"
        assert progress_events[-1]["percent"] == 100.0
        assert calls["verify"] == ("pull", {})
        assert verification_events == [{"ok": True, "message": "Verified: 1 file(s), 100 B."}]
        assert history_events == [{
            "direction": "pull", "total_files": 1, "total_bytes": 100, "verification_ok": True,
        }]

    def test_verify_false_skips_verification(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)

        monkeypatch.setattr(transfer_ops, "plan_pull_many", lambda *a, **k: [SAMPLE_PLAN])
        monkeypatch.setattr(transfer_ops, "execute_plans", lambda *a, **k: SAMPLE_RESULT)

        def fail_verify(*a, **k):
            raise AssertionError("verify_plans should not be called when verify=False")

        monkeypatch.setattr(transfer_ops, "verify_plans", fail_verify)

        verification_events, history_events = [], []
        vm.verificationChanged.connect(verification_events.append)
        vm.historyEntryAdded.connect(history_events.append)

        vm.start_pull("/sdcard/DCIM", "/tmp/out", conflict=transfer_module.CONFLICT_SKIP, verify=False)

        assert verification_events == []
        assert history_events == [{
            "direction": "pull", "total_files": 1, "total_bytes": 100, "verification_ok": None,
        }]


class TestStartPush:
    def test_passes_remote_dir_to_verify(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)
        calls = {}

        monkeypatch.setattr(transfer_ops, "plan_push_many", lambda *a, **k: [SAMPLE_PLAN])
        monkeypatch.setattr(transfer_ops, "execute_plans", lambda *a, **k: SAMPLE_RESULT)

        def fake_verify_plans(client, serial, plans, direction, **kwargs):
            calls["verify"] = (direction, kwargs)
            return SAMPLE_VERIFICATION

        monkeypatch.setattr(transfer_ops, "verify_plans", fake_verify_plans)

        vm.start_push("/tmp/a.jpg", "/sdcard/Pictures", conflict=transfer_module.CONFLICT_OVERWRITE, verify=True)

        assert calls["verify"] == ("push", {"remote_dir": "/sdcard/Pictures"})


class TestPullSelected:
    def test_uses_skip_conflict_and_always_verifies(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)
        calls = {}

        def fake_plan_pull_many(client, serial, remote_paths, local_dir, conflict):
            calls["plan"] = (remote_paths, local_dir, conflict)
            return [SAMPLE_PLAN]

        monkeypatch.setattr(transfer_ops, "plan_pull_many", fake_plan_pull_many)
        monkeypatch.setattr(transfer_ops, "execute_plans", lambda *a, **k: SAMPLE_RESULT)
        monkeypatch.setattr(transfer_ops, "verify_plans", lambda *a, **k: SAMPLE_VERIFICATION)

        verification_events = []
        vm.verificationChanged.connect(verification_events.append)

        vm.pull_selected(["/sdcard/a.jpg", "/sdcard/b.jpg"], "/tmp/out")

        assert calls["plan"] == (["/sdcard/a.jpg", "/sdcard/b.jpg"], "/tmp/out", transfer_module.CONFLICT_SKIP)
        assert verification_events == [{"ok": True, "message": "Verified: 1 file(s), 100 B."}]


class TestCancel:
    def test_sets_should_cancel_true(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)
        captured = {}

        monkeypatch.setattr(transfer_ops, "plan_pull_many", lambda *a, **k: [SAMPLE_PLAN])
        monkeypatch.setattr(transfer_ops, "verify_plans", lambda *a, **k: SAMPLE_VERIFICATION)

        def fake_execute_plans(client, serial, plans, progress_callback=None, should_cancel=None):
            vm.cancel_transfer()
            captured["should_cancel"] = should_cancel()
            return SAMPLE_RESULT

        monkeypatch.setattr(transfer_ops, "execute_plans", fake_execute_plans)

        vm.start_pull("/sdcard/DCIM", "/tmp/out", conflict=transfer_module.CONFLICT_SKIP, verify=True)

        assert captured["should_cancel"] is True

    def test_resets_at_start_of_new_transfer(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)
        vm._cancel_requested = True
        captured = {}

        monkeypatch.setattr(transfer_ops, "plan_pull_many", lambda *a, **k: [SAMPLE_PLAN])
        monkeypatch.setattr(transfer_ops, "verify_plans", lambda *a, **k: SAMPLE_VERIFICATION)

        def fake_execute_plans(client, serial, plans, progress_callback=None, should_cancel=None):
            captured["should_cancel"] = should_cancel()
            return SAMPLE_RESULT

        monkeypatch.setattr(transfer_ops, "execute_plans", fake_execute_plans)

        vm.start_pull("/sdcard/DCIM", "/tmp/out", conflict=transfer_module.CONFLICT_SKIP, verify=True)

        assert captured["should_cancel"] is False


class TestError:
    def test_emits_status_and_log(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)

        def raise_error(*a, **k):
            raise ValueError("adb shell failed")

        monkeypatch.setattr(transfer_ops, "plan_pull_many", raise_error)

        statuses = []
        vm.statusChanged.connect(statuses.append)

        vm.start_pull("/sdcard/DCIM", "/tmp/out", conflict=transfer_module.CONFLICT_SKIP, verify=False)

        assert statuses == ["adb shell failed"]


class TestBusyGuard:
    def test_start_pull_rejects_if_busy(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)
        vm._workers.append(object())  # Simulate already busy

        def fail_plan(*a, **k):
            raise AssertionError("plan_pull_many should not be called when busy")

        monkeypatch.setattr(transfer_ops, "plan_pull_many", fail_plan)

        status_events = []
        log_events = []
        vm.statusChanged.connect(status_events.append)
        vm.logMessage.connect(lambda msg, level: log_events.append((msg, level)))

        vm.start_pull("/sdcard/DCIM", "/tmp/out", conflict=transfer_module.CONFLICT_SKIP, verify=True)

        assert status_events == ["A transfer is already in progress."]
        assert log_events == [("A transfer is already in progress.", "WARNING")]
        assert len(vm._workers) == 1  # No new worker added

    def test_start_push_rejects_if_busy(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)
        vm._workers.append(object())  # Simulate already busy

        def fail_plan(*a, **k):
            raise AssertionError("plan_push_many should not be called when busy")

        monkeypatch.setattr(transfer_ops, "plan_push_many", fail_plan)

        status_events = []
        log_events = []
        vm.statusChanged.connect(status_events.append)
        vm.logMessage.connect(lambda msg, level: log_events.append((msg, level)))

        vm.start_push("/tmp/a.jpg", "/sdcard/Pictures", conflict=transfer_module.CONFLICT_OVERWRITE, verify=True)

        assert status_events == ["A transfer is already in progress."]
        assert log_events == [("A transfer is already in progress.", "WARNING")]
        assert len(vm._workers) == 1  # No new worker added

    def test_pull_selected_rejects_if_busy(self, qtbot, monkeypatch):
        vm = TransferViewModel(_connected_context(), worker_factory=FakeWorker)
        vm._workers.append(object())  # Simulate already busy

        def fail_plan(*a, **k):
            raise AssertionError("plan_pull_many should not be called when busy")

        monkeypatch.setattr(transfer_ops, "plan_pull_many", fail_plan)

        status_events = []
        log_events = []
        vm.statusChanged.connect(status_events.append)
        vm.logMessage.connect(lambda msg, level: log_events.append((msg, level)))

        vm.pull_selected(["/sdcard/a.jpg", "/sdcard/b.jpg"], "/tmp/out")

        assert status_events == ["A transfer is already in progress."]
        assert log_events == [("A transfer is already in progress.", "WARNING")]
        assert len(vm._workers) == 1  # No new worker added
