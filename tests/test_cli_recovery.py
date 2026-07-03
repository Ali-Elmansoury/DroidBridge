# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for `droidbridge recovery` CLI group (Module 10)."""

import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device
from droidbridge.modules.recovery import RecoveredFile, SoftDeleteScanner, BackupRestorer, BackupInfo, RestoreResult, DiffResult

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]


def make_client(devices=None, shell=""):
    client = MagicMock()
    client.devices.return_value = READY_DEVICE if devices is None else devices
    client.shell.return_value = shell
    return client


def _write_vcf(path: Path, count: int):
    lines = []
    for i in range(count):
        lines += ["BEGIN:VCARD", "VERSION:3.0", f"FN:Person {i}", f"TEL:555-{i:04d}", "END:VCARD"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_call_csv(path: Path, count: int):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "number", "timestamp", "duration_seconds", "call_type"])
        for i in range(count):
            w.writerow([f"P{i}", f"555-{i:04d}", "2026-06-01T10:00:00+00:00", "30", "incoming"])


class TestRecoveryScanCLI:
    def test_scan_prints_disclaimer(self, tmp_path):
        with patch.object(main, "_build_client", return_value=make_client()):
            with patch.object(SoftDeleteScanner, "scan", return_value=[]):
                result = CliRunner().invoke(main.cli, ["recovery", "scan", "--output", str(tmp_path)])
        assert result.exit_code == 0
        assert "cannot recover" in result.output.lower() or "not guaranteed" in result.output.lower()

    def test_scan_prints_found_count(self, tmp_path):
        found = [RecoveredFile(
            remote_path="/sdcard/.trash/img.jpg",
            filename="img.jpg",
            size_bytes=512000,
            modified_date="2026-06-10T12:30",
            file_type="image",
            source_app="Generic",
            is_true_trash=True,
        )]
        with patch.object(main, "_build_client", return_value=make_client()):
            with patch.object(SoftDeleteScanner, "scan", return_value=found):
                result = CliRunner().invoke(main.cli, ["recovery", "scan", "--output", str(tmp_path)])
        assert "1" in result.output

    def test_scan_exits_gracefully_when_no_device(self, tmp_path):
        with patch.object(main, "_build_client", return_value=make_client(devices=[])):
            result = CliRunner().invoke(main.cli, ["recovery", "scan", "--output", str(tmp_path)])
        assert result.exit_code != 0


class TestRecoveryRestoreCLI:
    def test_restore_prints_disclaimer(self, tmp_path):
        _write_vcf(tmp_path / "contacts_phone.vcf", 2)
        with patch.object(main, "_build_client", return_value=make_client()):
            with patch.object(BackupRestorer, "restore_contacts", return_value=RestoreResult(2, 2, 0, 0)):
                with patch.object(BackupRestorer, "diff_contacts", return_value=DiffResult(2, 0, 2)):
                    result = CliRunner().invoke(main.cli, [
                        "recovery", "restore",
                        "--backup", str(tmp_path),
                        "--contacts", "--dest", "pc", "--output", str(tmp_path / "out"),
                    ])
        assert "not guaranteed" in result.output.lower() or "cannot recover" in result.output.lower()

    def test_restore_requires_backup_flag(self, tmp_path):
        result = CliRunner().invoke(main.cli, ["recovery", "restore", "--contacts"])
        assert result.exit_code != 0

    def test_restore_contacts_to_pc_reports_success(self, tmp_path):
        _write_vcf(tmp_path / "contacts_phone.vcf", 5)
        out_dir = tmp_path / "out"
        with patch.object(main, "_build_client", return_value=make_client()):
            with patch.object(BackupRestorer, "restore_contacts", return_value=RestoreResult(5, 5, 0, 0)) as mock_restore:
                with patch.object(BackupRestorer, "diff_contacts", return_value=DiffResult(5, 3, 2)):
                    result = CliRunner().invoke(main.cli, [
                        "recovery", "restore",
                        "--backup", str(tmp_path),
                        "--contacts", "--dest", "pc", "--output", str(out_dir),
                    ])
        assert result.exit_code == 0
        assert "5" in result.output
