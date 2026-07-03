# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Unit tests for droidbridge.modules.recovery — Module 10."""

import csv as _csv
from pathlib import Path
from unittest.mock import MagicMock

from droidbridge.core.adb import AdbError
from droidbridge.modules.recovery import (
    RecoveredFile,
    BackupInfo,
    DiffResult,
    RestoreResult,
    SoftDeleteScanner,
    BackupRestorer,
)


def make_client(return_value=""):
    client = MagicMock()
    client.shell.return_value = return_value
    return client


class TestRecoveredFileDataclass:
    def test_fields(self):
        f = RecoveredFile(
            remote_path="/sdcard/.trash/photo.jpg",
            filename="photo.jpg",
            size_bytes=1048576,
            modified_date="2026-06-10T12:30",
            file_type="image",
            source_app="Generic",
            is_true_trash=True,
        )
        assert f.remote_path == "/sdcard/.trash/photo.jpg"
        assert f.is_true_trash is True


class TestSoftDeleteScannerScan:
    def test_scan_returns_empty_when_all_paths_empty(self):
        scanner = SoftDeleteScanner()
        results = scanner.scan(make_client(""), "SERIAL")
        assert results == []

    def test_scan_path_parses_image_file(self):
        ls_output = (
            "-rw-rw-r-- 1 u0_a143 u0_a143 1048576 2026-06-10 12:30 photo.jpg\n"
        )
        scanner = SoftDeleteScanner()
        results = scanner._scan_path(
            make_client(ls_output), "SERIAL",
            "/sdcard/.trash/", "Generic", True,
        )
        assert len(results) == 1
        r = results[0]
        assert r.filename == "photo.jpg"
        assert r.remote_path == "/sdcard/.trash/photo.jpg"
        assert r.size_bytes == 1048576
        assert r.modified_date == "2026-06-10T12:30"
        assert r.file_type == "image"
        assert r.source_app == "Generic"
        assert r.is_true_trash is True

    def test_scan_path_parses_video_file(self):
        ls_output = (
            "-rw-rw-r-- 1 u0_a143 u0_a143 5000000 2026-06-11 09:15 clip.mp4\n"
        )
        scanner = SoftDeleteScanner()
        results = scanner._scan_path(
            make_client(ls_output), "SERIAL",
            "/sdcard/.trash/", "Generic", True,
        )
        assert results[0].file_type == "video"

    def test_scan_path_parses_document_file(self):
        ls_output = (
            "-rw-rw-r-- 1 u0_a143 u0_a143 2048 2026-06-12 08:00 report.pdf\n"
        )
        scanner = SoftDeleteScanner()
        results = scanner._scan_path(
            make_client(ls_output), "SERIAL",
            "/sdcard/.trash/", "Generic", True,
        )
        assert results[0].file_type == "document"

    def test_scan_path_skips_directories(self):
        ls_output = (
            "drwxrwxr-x 2 u0_a143 u0_a143 4096 2026-06-10 12:00 subdir\n"
            "-rw-rw-r-- 1 u0_a143 u0_a143 512 2026-06-10 11:00 note.txt\n"
        )
        scanner = SoftDeleteScanner()
        results = scanner._scan_path(
            make_client(ls_output), "SERIAL",
            "/sdcard/.trash/", "Generic", True,
        )
        assert len(results) == 1
        assert results[0].filename == "note.txt"

    def test_scan_path_marks_whatsapp_sent_as_not_true_trash(self):
        ls_output = (
            "-rw-rw-r-- 1 u0_a143 u0_a143 512000 2026-06-10 10:00 sent_img.jpg\n"
        )
        scanner = SoftDeleteScanner()
        results = scanner._scan_path(
            make_client(ls_output), "SERIAL",
            "/sdcard/WhatsApp/Media/WhatsApp Images/Sent/", "WhatsApp", False,
        )
        assert results[0].is_true_trash is False

    def test_scan_path_returns_empty_on_adb_error(self):
        client = MagicMock()
        client.shell.side_effect = AdbError("permission denied")
        scanner = SoftDeleteScanner()
        results = scanner._scan_path(client, "SERIAL", "/sdcard/.trash/", "Generic", True)
        assert results == []

    def test_scan_path_ignores_non_matching_lines(self):
        ls_output = "ls: /sdcard/.trash/: No such file or directory\n"
        scanner = SoftDeleteScanner()
        results = scanner._scan_path(
            make_client(ls_output), "SERIAL",
            "/sdcard/.trash/", "Generic", True,
        )
        assert results == []

    def test_scan_path_classifies_unknown_extension_as_other(self):
        ls_output = (
            "-rw-rw-r-- 1 u0_a143 u0_a143 100 2026-06-10 10:00 data.xyz\n"
        )
        scanner = SoftDeleteScanner()
        results = scanner._scan_path(
            make_client(ls_output), "SERIAL",
            "/sdcard/.trash/", "Generic", True,
        )
        assert results[0].file_type == "other"


class TestSoftDeleteScannerTransfer:
    def test_pull_to_pc_returns_true_on_success(self, tmp_path):
        client = MagicMock()
        scanner = SoftDeleteScanner()
        result = scanner.pull_to_pc(client, "SERIAL", "/sdcard/.trash/photo.jpg", str(tmp_path))
        assert result is True
        client.pull.assert_called_once_with(
            "SERIAL", "/sdcard/.trash/photo.jpg",
            str(tmp_path / "photo.jpg"),
        )

    def test_pull_to_pc_returns_false_on_adb_error(self, tmp_path):
        client = MagicMock()
        client.pull.side_effect = AdbError("failed")
        scanner = SoftDeleteScanner()
        result = scanner.pull_to_pc(client, "SERIAL", "/sdcard/.trash/photo.jpg", str(tmp_path))
        assert result is False

    def test_pull_to_pc_creates_dest_dir_if_missing(self, tmp_path):
        client = MagicMock()
        dest = tmp_path / "new_dir"
        scanner = SoftDeleteScanner()
        scanner.pull_to_pc(client, "SERIAL", "/sdcard/.trash/photo.jpg", str(dest))
        assert dest.exists()

    def test_push_back_to_phone_returns_true_on_success(self):
        client = MagicMock()
        scanner = SoftDeleteScanner()
        result = scanner.push_back_to_phone(
            client, "SERIAL",
            "/sdcard/.trash/photo.jpg",
            "/sdcard/DCIM/Camera/photo.jpg",
        )
        assert result is True
        client.push.assert_called_once()

    def test_push_back_to_phone_returns_false_on_adb_error(self):
        client = MagicMock()
        client.push.side_effect = AdbError("failed")
        scanner = SoftDeleteScanner()
        result = scanner.push_back_to_phone(
            client, "SERIAL",
            "/sdcard/.trash/photo.jpg",
            "/sdcard/DCIM/Camera/photo.jpg",
        )
        assert result is False


# ---------------------------------------------------------------------------
# Task 3: BackupRestorer — list_backups, diff_contacts, diff_calls
# ---------------------------------------------------------------------------

def _write_vcf(path: Path, count: int):
    lines = []
    for i in range(count):
        lines += ["BEGIN:VCARD", "VERSION:3.0", f"FN:Person {i}", f"TEL:555-{i:04d}", "END:VCARD"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_call_log_csv(path: Path, count: int):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = _csv.writer(f)
        writer.writerow(["name", "number", "timestamp", "duration_seconds", "call_type"])
        for i in range(count):
            writer.writerow([f"Person {i}", f"555-{i:04d}", "2026-06-01T10:00:00+00:00", "30", "incoming"])


class TestBackupRestorerListBackups:
    def test_finds_vcf_and_csv_in_flat_dir(self, tmp_path):
        _write_vcf(tmp_path / "contacts_phone.vcf", 5)
        _write_call_log_csv(tmp_path / "call_log.csv", 10)
        restorer = BackupRestorer()
        results = restorer.list_backups(tmp_path)
        assert len(results) == 1
        assert results[0].contacts_count == 5
        assert results[0].calls_count == 10
        assert results[0].path == tmp_path

    def test_finds_backups_in_subdirectory(self, tmp_path):
        sub = tmp_path / "2026-06-14_backup"
        sub.mkdir()
        _write_vcf(sub / "contacts_phone.vcf", 3)
        restorer = BackupRestorer()
        results = restorer.list_backups(tmp_path)
        assert any(r.path == sub for r in results)
        assert results[0].contacts_count == 3

    def test_returns_empty_for_dir_with_no_backup_files(self, tmp_path):
        restorer = BackupRestorer()
        results = restorer.list_backups(tmp_path)
        assert results == []

    def test_contacts_count_sums_all_vcf_files(self, tmp_path):
        _write_vcf(tmp_path / "contacts_phone.vcf", 4)
        _write_vcf(tmp_path / "contacts_accounts.vcf", 6)
        restorer = BackupRestorer()
        results = restorer.list_backups(tmp_path)
        assert results[0].contacts_count == 10

    def test_calls_count_excludes_header_row(self, tmp_path):
        _write_call_log_csv(tmp_path / "call_log.csv", 8)
        restorer = BackupRestorer()
        results = restorer.list_backups(tmp_path)
        assert results[0].calls_count == 8


class TestBackupRestorerDiff:
    def test_diff_contacts_returns_correct_counts(self, tmp_path):
        vcf = tmp_path / "contacts_phone.vcf"
        _write_vcf(vcf, 50)
        # Phone returns 40 contacts (raw_contacts query)
        client = MagicMock()
        client.shell.return_value = "\n".join(
            f"Row: {i} _id={i}, account_type=NULL" for i in range(40)
        )
        restorer = BackupRestorer()
        result = restorer.diff_contacts(client, "SERIAL", vcf)
        assert result.backup_count == 50
        assert result.phone_count == 40
        assert result.estimated_missing == 10

    def test_diff_calls_returns_correct_counts(self, tmp_path):
        csv_path = tmp_path / "call_log.csv"
        _write_call_log_csv(csv_path, 100)
        # Phone returns 80 call entries
        client = MagicMock()
        client.shell.return_value = "\n".join(
            f"Row: {i} number=555-{i:04d}, date=1718123456000, duration=30, type=1, name="
            for i in range(80)
        )
        restorer = BackupRestorer()
        result = restorer.diff_calls(client, "SERIAL", csv_path)
        assert result.backup_count == 100
        assert result.phone_count == 80
        assert result.estimated_missing == 20


# ---------------------------------------------------------------------------
# Task 4: BackupRestorer — restore_contacts, restore_calls
# ---------------------------------------------------------------------------

class TestBackupRestorerRestoreContacts:
    def test_restore_contacts_to_pc_copies_vcf(self, tmp_path):
        vcf = tmp_path / "contacts_phone.vcf"
        _write_vcf(vcf, 3)
        dest_dir = tmp_path / "output"
        dest_dir.mkdir()
        restorer = BackupRestorer()
        result = restorer.restore_contacts(MagicMock(), "SERIAL", vcf, str(dest_dir))
        assert (dest_dir / "contacts_phone.vcf").exists()
        assert result.succeeded == 3
        assert result.failed == 0

    def test_restore_contacts_to_phone_pushes_vcf_and_launches_intent(self, tmp_path):
        vcf = tmp_path / "contacts_phone.vcf"
        _write_vcf(vcf, 5)
        client = MagicMock()
        restorer = BackupRestorer()
        result = restorer.restore_contacts(client, "SERIAL", vcf, "phone")
        client.push.assert_called_once()
        push_args = client.push.call_args[0]
        assert push_args[2] == "/sdcard/droidbridge_restore.vcf"
        # am start called
        assert client.shell.call_count >= 1
        am_call = any(
            "am start" in str(call) for call in client.shell.call_args_list
        )
        assert am_call
        assert result.total == 5


class TestBackupRestorerRestoreCalls:
    def test_restore_calls_to_pc_copies_csv(self, tmp_path):
        csv_path = tmp_path / "call_log.csv"
        _write_call_log_csv(csv_path, 10)
        dest_dir = tmp_path / "output"
        dest_dir.mkdir()
        restorer = BackupRestorer()
        result = restorer.restore_calls(MagicMock(), "SERIAL", csv_path, str(dest_dir))
        assert (dest_dir / "call_log.csv").exists()
        assert result.succeeded == 10
        assert result.failed == 0

    def test_restore_calls_to_phone_inserts_rows(self, tmp_path):
        csv_path = tmp_path / "call_log.csv"
        _write_call_log_csv(csv_path, 3)
        client = MagicMock()
        restorer = BackupRestorer()
        result = restorer.restore_calls(client, "SERIAL", csv_path, "phone")
        # 3 content insert calls
        assert client.shell.call_count == 3
        assert result.total == 3
        assert result.succeeded == 3

    def test_restore_calls_to_phone_counts_failed_inserts(self, tmp_path):
        csv_path = tmp_path / "call_log.csv"
        _write_call_log_csv(csv_path, 2)
        client = MagicMock()
        client.shell.side_effect = [AdbError("denied"), ""]
        restorer = BackupRestorer()
        result = restorer.restore_calls(client, "SERIAL", csv_path, "phone")
        assert result.failed == 1
        assert result.succeeded == 1
        assert len(result.errors) == 1
