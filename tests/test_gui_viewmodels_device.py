# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.viewmodels.device.DeviceViewModel (Phase 6.1).

Uses a synchronous FakeWorker (no real QThread) so these tests are fast and
deterministic, per the spec's "TDD for logic, no Qt thread needed" approach.
"""

from unittest.mock import MagicMock

from PyQt6.QtCore import QObject, pyqtSignal

from droidbridge.gui import device_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.device import DeviceViewModel
from droidbridge.modules import device as device_module
from droidbridge.modules.device import DeviceInfo, StorageInfo


class FakeWorker(QObject):
    """Synchronous stand-in for gui.workers.Worker: runs fn immediately on start().

    Mirrors gui.workers.Worker's report_progress kwarg: if True, fn is called with
    a progress_callback that emits the `progress` signal synchronously.
    """

    finished = pyqtSignal(object)
    error = pyqtSignal(object)
    progress = pyqtSignal(object)

    def __init__(self, fn, *args, report_progress=False, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._report_progress = report_progress

    def start(self):
        if self._report_progress:
            self._kwargs["progress_callback"] = self.progress.emit
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(exc)
        else:
            self.finished.emit(result)

    def wait(self):
        pass


SAMPLE_INFO = DeviceInfo(
    serial="SERIAL123",
    model="Pixel 7",
    manufacturer="Google",
    android_version="14",
    sdk_version="34",
    build_number="UQ1A.240205.004",
    battery_level=85,
    battery_status="charging",
    storage=StorageInfo(total_kb=1000, used_kb=500, free_kb=500),
)


class TestConnectDevice:
    def test_success_updates_context_and_refreshes_info(self, qtbot, monkeypatch):
        context = DeviceContext()
        vm = DeviceViewModel(context, worker_factory=FakeWorker)

        fake_client = MagicMock()
        monkeypatch.setattr(
            device_ops, "connect",
            lambda: (fake_client, "SERIAL123", "Pixel 7", ["SERIAL123: Device connected and ready."]),
        )
        monkeypatch.setattr(device_ops, "refresh_info", lambda client, serial: SAMPLE_INFO)

        connection_events = []
        context.connectionChanged.connect(lambda *a: connection_events.append(a))
        info_events = []
        vm.infoChanged.connect(info_events.append)
        busy_events = []
        vm.busyChanged.connect(busy_events.append)

        vm.connect_device()

        assert connection_events == [(True, "SERIAL123", "Pixel 7")]
        assert context.client is fake_client
        assert info_events[0]["serial"] == "SERIAL123"
        assert info_events[0]["android"] == "14 (SDK 34)"
        assert info_events[0]["battery"] == "85% (charging)"
        assert info_events[0]["storage_used_percent"] == 50.0
        assert busy_events[0] is True
        assert busy_events[-1] is False

    def test_error_emits_status_and_log(self, qtbot, monkeypatch):
        context = DeviceContext()
        vm = DeviceViewModel(context, worker_factory=FakeWorker)

        def raise_no_device():
            raise device_module.DeviceSelectionError("no device message")

        monkeypatch.setattr(device_ops, "connect", raise_no_device)

        statuses = []
        vm.statusChanged.connect(statuses.append)
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))

        vm.connect_device()

        assert statuses == ["no device message"]
        assert ("no device message", "ERROR") in logs
        assert context.is_connected is False


class TestRefresh:
    def test_success_emits_formatted_info(self, qtbot, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context, worker_factory=FakeWorker)
        monkeypatch.setattr(device_ops, "refresh_info", lambda client, serial: SAMPLE_INFO)

        info_events = []
        vm.infoChanged.connect(info_events.append)

        vm.refresh()

        assert info_events[0]["manufacturer"] == "Google"
        assert info_events[0]["storage_total"] == "1000.0 KB"
        assert info_events[0]["storage_used"] == "500.0 KB"
        assert info_events[0]["storage_free"] == "500.0 KB"

    def test_error_sets_offline_status_and_logs_warning(self, qtbot, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context, worker_factory=FakeWorker)

        def raise_value_error(client, serial):
            raise ValueError("adb shell failed")

        monkeypatch.setattr(device_ops, "refresh_info", raise_value_error)

        statuses = []
        vm.statusChanged.connect(statuses.append)
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))

        vm.refresh()

        assert statuses == ["Device disconnected. Waiting to reconnect..."]
        assert vm._device_offline is True
        assert any(level == "WARNING" and "Device disconnected" in msg for msg, level in logs)

    def test_success_after_error_clears_offline_status_and_logs_reconnect(self, qtbot, monkeypatch):
        """A transient auto-refresh failure (e.g. a momentary USB drop reported as
        "device not found") sets the offline status - once a later refresh succeeds,
        the status should clear and a "Device reconnected." message logged.
        """
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context, worker_factory=FakeWorker)

        statuses = []
        vm.statusChanged.connect(statuses.append)
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))

        monkeypatch.setattr(
            device_ops, "refresh_info",
            lambda client, serial: (_ for _ in ()).throw(ValueError("device not found")),
        )
        vm.refresh()
        assert statuses == ["Device disconnected. Waiting to reconnect..."]
        assert vm._device_offline is True

        monkeypatch.setattr(device_ops, "refresh_info", lambda client, serial: SAMPLE_INFO)
        vm.refresh()
        assert statuses == ["Device disconnected. Waiting to reconnect...", ""]
        assert vm._device_offline is False
        assert ("Device reconnected.", "INFO") in logs


class TestWorkerLifecycle:
    """Regression tests for the real Worker/QThread path (FakeWorker is synchronous and
    has no QThread, so it can't catch worker-lifetime bugs).
    """

    def test_real_worker_completes_and_is_released(self, qtbot, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context)  # real Worker (default factory)
        monkeypatch.setattr(device_ops, "refresh_info", lambda client, serial: SAMPLE_INFO)

        info_events = []
        vm.infoChanged.connect(info_events.append)

        with qtbot.waitSignal(vm.infoChanged, timeout=2000):
            vm.refresh()

        assert info_events[0]["manufacturer"] == "Google"
        assert vm._workers == []

    def test_busy_stays_true_until_chained_refresh_completes(self, qtbot, monkeypatch):
        context = DeviceContext()
        vm = DeviceViewModel(context)  # real Worker (default factory)
        fake_client = MagicMock()
        monkeypatch.setattr(
            device_ops, "connect",
            lambda: (fake_client, "SERIAL123", "Pixel 7", []),
        )
        monkeypatch.setattr(device_ops, "refresh_info", lambda client, serial: SAMPLE_INFO)

        info_events = []
        vm.infoChanged.connect(info_events.append)

        with qtbot.waitSignal(
            vm.busyChanged, timeout=2000, check_params_cb=lambda busy: busy is False
        ):
            vm.connect_device()

        assert info_events, "infoChanged must fire before busyChanged(False)"
        assert vm._workers == []


class TestPoll:
    def test_connected_and_online_calls_refresh(self, qtbot, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context, worker_factory=FakeWorker)
        monkeypatch.setattr(device_ops, "refresh_info", lambda client, serial: SAMPLE_INFO)

        info_events = []
        vm.infoChanged.connect(info_events.append)

        vm.poll()

        assert info_events[0]["serial"] == "SERIAL123"

    def test_not_connected_does_nothing(self, qtbot, monkeypatch):
        context = DeviceContext()
        vm = DeviceViewModel(context, worker_factory=FakeWorker)

        calls = []
        monkeypatch.setattr(device_ops, "refresh_info", lambda c, s: calls.append(True))

        vm.poll()

        assert calls == []

    def test_busy_does_nothing(self, qtbot, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context, worker_factory=FakeWorker)
        vm._workers.append(object())

        calls = []
        monkeypatch.setattr(device_ops, "refresh_info", lambda c, s: calls.append(True))

        vm.poll()

        assert calls == []

    def test_offline_and_device_ready_reconnects(self, qtbot, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context, worker_factory=FakeWorker)
        vm._device_offline = True

        monkeypatch.setattr(device_ops, "is_device_ready", lambda client, serial: True)
        monkeypatch.setattr(device_ops, "refresh_info", lambda client, serial: SAMPLE_INFO)

        info_events = []
        vm.infoChanged.connect(info_events.append)
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))

        vm.poll()

        assert vm._device_offline is False
        assert info_events[0]["serial"] == "SERIAL123"
        assert ("Device reconnected.", "INFO") in logs
        assert vm._workers == []

    def test_offline_and_device_not_ready_stays_offline(self, qtbot, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context, worker_factory=FakeWorker)
        vm._device_offline = True

        monkeypatch.setattr(device_ops, "is_device_ready", lambda client, serial: False)
        refresh_calls = []
        monkeypatch.setattr(device_ops, "refresh_info", lambda c, s: refresh_calls.append(True))

        vm.poll()

        assert vm._device_offline is True
        assert refresh_calls == []
        assert vm._workers == []

    def test_offline_and_presence_check_errors_stays_offline(self, qtbot, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = DeviceViewModel(context, worker_factory=FakeWorker)
        vm._device_offline = True

        def raise_error(client, serial):
            raise ValueError("adb hiccup")

        monkeypatch.setattr(device_ops, "is_device_ready", raise_error)

        vm.poll()

        assert vm._device_offline is True
        assert vm._workers == []
