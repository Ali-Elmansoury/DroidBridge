# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.viewmodels.recovery.scanner.ScannerViewModel."""

from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.recovery.scanner import ScannerViewModel
from droidbridge.modules.recovery import RecoveredFile, SoftDeleteScanner
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
    return ctx


def _make_file(name="photo.jpg", true_trash=True):
    return RecoveredFile(
        remote_path=f"/sdcard/.trash/{name}",
        filename=name,
        size_bytes=512000,
        modified_date="2026-06-10T12:30",
        file_type="image",
        source_app="Generic",
        is_true_trash=true_trash,
    )


class TestScannerViewModelScan:
    def test_scan_emits_scan_results_on_success(self, qtbot, monkeypatch):
        vm = ScannerViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(SoftDeleteScanner, "scan", lambda self, c, s: [_make_file("a.jpg"), _make_file("b.jpg")])
        results = []
        vm.scanResultsChanged.connect(results.append)
        vm.scan()
        assert len(results) == 1
        assert len(results[0]) == 2

    def test_scan_emits_busy_true_then_false(self, qtbot, monkeypatch):
        vm = ScannerViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(SoftDeleteScanner, "scan", lambda self, c, s: [])
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.scan()
        assert busy == [True, False]

    def test_scan_emits_status_with_count(self, qtbot, monkeypatch):
        vm = ScannerViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(SoftDeleteScanner, "scan", lambda self, c, s: [_make_file()])
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.scan()
        assert any("1" in s for s in statuses)

    def test_scan_error_emits_error_log(self, qtbot, monkeypatch):
        vm = ScannerViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(SoftDeleteScanner, "scan", lambda self, c, s: (_ for _ in ()).throw(ValueError("adb failed")))
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append((msg, level)))
        vm.scan()
        assert any(level == "ERROR" for _, level in logs)


class TestScannerViewModelPullToPc:
    def test_pull_to_pc_emits_busy(self, qtbot, monkeypatch, tmp_path):
        vm = ScannerViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(SoftDeleteScanner, "pull_to_pc", lambda self, c, s, rp, dd: True)
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.pull_to_pc([_make_file()], str(tmp_path))
        assert busy == [True, False]

    def test_pull_to_pc_emits_status_summary(self, qtbot, monkeypatch, tmp_path):
        vm = ScannerViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(SoftDeleteScanner, "pull_to_pc", lambda self, c, s, rp, dd: True)
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.pull_to_pc([_make_file(), _make_file("b.jpg")], str(tmp_path))
        assert any("2" in s for s in statuses)


class TestScannerViewModelPushToPhone:
    def test_push_to_phone_emits_busy(self, qtbot, monkeypatch):
        vm = ScannerViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(SoftDeleteScanner, "push_back_to_phone", lambda self, c, s, rp, op: True)
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.push_to_phone([_make_file()])
        assert busy == [True, False]
