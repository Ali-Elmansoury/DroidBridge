# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.reports.recovery_reports."""

from pathlib import Path
from droidbridge.modules.recovery import RecoveredFile, BackupInfo, RestoreResult
from droidbridge.reports.recovery_reports import build_scan_report, build_restore_report
from droidbridge.reports.generators import to_txt, to_json, to_csv, to_html


def _make_file(name="photo.jpg", size=1024, true_trash=True):
    return RecoveredFile(
        remote_path=f"/sdcard/.trash/{name}",
        filename=name,
        size_bytes=size,
        modified_date="2026-06-10T12:30",
        file_type="image",
        source_app="Generic",
        is_true_trash=true_trash,
    )


class TestBuildScanReport:
    def test_report_has_correct_title(self):
        report = build_scan_report([], 0, 0, 0)
        assert "Recovery" in report.title or "Scan" in report.title

    def test_report_contains_file_count(self):
        files = [_make_file("a.jpg"), _make_file("b.jpg")]
        report = build_scan_report(files, pulled_count=1, restored_count=1, failed_count=0)
        txt = to_txt(report)
        assert "2" in txt

    def test_report_contains_pulled_and_restored_counts(self):
        files = [_make_file()]
        report = build_scan_report(files, pulled_count=1, restored_count=0, failed_count=0)
        txt = to_txt(report)
        assert "1" in txt

    def test_report_serializes_to_json(self):
        report = build_scan_report([_make_file()], 1, 0, 0)
        result = to_json(report)
        import json
        data = json.loads(result)
        assert "title" in data

    def test_report_serializes_to_csv(self):
        report = build_scan_report([_make_file()], 1, 0, 0)
        result = to_csv(report)
        assert len(result) > 0

    def test_report_serializes_to_html(self):
        report = build_scan_report([_make_file()], 1, 0, 0)
        result = to_html(report)
        assert "<html" in result.lower()


class TestBuildRestoreReport:
    def test_report_has_backup_path_in_title(self):
        info = BackupInfo(path=Path("/backups/contacts"), date="2026-06-14", contacts_count=50, calls_count=100)
        contacts_result = RestoreResult(total=50, succeeded=48, failed=2, skipped=0, errors=["err1", "err2"])
        calls_result = RestoreResult(total=100, succeeded=100, failed=0, skipped=0)
        report = build_restore_report(info, contacts_result, calls_result)
        txt = to_txt(report)
        assert "48" in txt
        assert "100" in txt

    def test_report_skips_none_results(self):
        info = BackupInfo(path=Path("/backups/contacts"), date="2026-06-14", contacts_count=10, calls_count=0)
        report = build_restore_report(info, contacts_result=RestoreResult(10, 10, 0, 0), calls_result=None)
        txt = to_txt(report)
        assert "10" in txt
