# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Unit tests for droidbridge.modules.recovery — Module 10."""

from unittest.mock import MagicMock

from droidbridge.core.adb import AdbError
from droidbridge.modules.recovery import (
    RecoveredFile,
    BackupInfo,
    DiffResult,
    RestoreResult,
    SoftDeleteScanner,
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
