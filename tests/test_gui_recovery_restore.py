# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.viewmodels.recovery.restore.RestoreViewModel."""

from pathlib import Path
from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.recovery.restore import RestoreViewModel
from droidbridge.modules.recovery import BackupInfo, BackupRestorer, DiffResult, RestoreResult
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
    return ctx


def _make_info(path="/backups", contacts=10, calls=20):
    return BackupInfo(path=Path(path), date="2026-06-14", contacts_count=contacts, calls_count=calls)


class TestRestoreViewModelLoadBackups:
    def test_load_backups_emits_backups_changed(self, qtbot, monkeypatch, tmp_path):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        fake_info = _make_info(str(tmp_path))
        monkeypatch.setattr(BackupRestorer, "list_backups", lambda self, d: [fake_info])
        results = []
        vm.backupsChanged.connect(results.append)
        vm.load_backups(str(tmp_path))
        assert len(results) == 1
        assert results[0] == [fake_info]

    def test_load_backups_emits_busy(self, qtbot, monkeypatch, tmp_path):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(BackupRestorer, "list_backups", lambda self, d: [])
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.load_backups(str(tmp_path))
        assert busy == [True, False]


class TestRestoreViewModelComputeDiff:
    def test_compute_diff_emits_diff_changed(self, qtbot, monkeypatch, tmp_path):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        vcf = tmp_path / "contacts_phone.vcf"
        vcf.write_text("BEGIN:VCARD\nEND:VCARD\n", encoding="utf-8")
        csv_path = tmp_path / "call_log.csv"
        csv_path.write_text("name,number,timestamp,duration_seconds,call_type\n", encoding="utf-8")
        info = _make_info(str(tmp_path))
        monkeypatch.setattr(BackupRestorer, "diff_contacts", lambda self, c, s, p: DiffResult(10, 8, 2))
        monkeypatch.setattr(BackupRestorer, "diff_calls", lambda self, c, s, p: DiffResult(20, 15, 5))
        diffs = []
        vm.diffChanged.connect(diffs.append)
        vm.compute_diff(info)
        assert len(diffs) == 1
        assert diffs[0]["contacts"].estimated_missing == 2
        assert diffs[0]["calls"].estimated_missing == 5


class TestRestoreViewModelRestore:
    def test_restore_emits_status_on_success(self, qtbot, monkeypatch, tmp_path):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        vcf = tmp_path / "contacts_phone.vcf"
        vcf.write_text("BEGIN:VCARD\nEND:VCARD\n", encoding="utf-8")
        info = _make_info(str(tmp_path), contacts=1, calls=0)
        monkeypatch.setattr(BackupRestorer, "restore_contacts", lambda self, c, s, p, d: RestoreResult(1, 1, 0, 0))
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.restore(info, restore_contacts=True, restore_calls=False, dest="pc", output_dir=str(tmp_path))
        assert any("1" in s for s in statuses)

    def test_restore_emits_busy(self, qtbot, monkeypatch, tmp_path):
        vm = RestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        vcf = tmp_path / "contacts_phone.vcf"
        vcf.write_text("BEGIN:VCARD\nEND:VCARD\n", encoding="utf-8")
        info = _make_info(str(tmp_path), contacts=1, calls=0)
        monkeypatch.setattr(BackupRestorer, "restore_contacts", lambda self, c, s, p, d: RestoreResult(1, 1, 0, 0))
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.restore(info, restore_contacts=True, restore_calls=False, dest="pc", output_dir=str(tmp_path))
        assert busy == [True, False]
