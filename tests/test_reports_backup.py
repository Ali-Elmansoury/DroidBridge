# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.reports.backup_reports (spec §9.3)."""

from droidbridge.core.session import SessionLogger
from droidbridge.modules.backup_manager import BackupRecord
from droidbridge.modules.transfer import VerificationResult
from droidbridge.reports.backup_reports import (
    build_backup_history_report,
    build_backup_summary_report,
    build_backup_verification_report,
    build_session_summary_report,
)


def _record(profile="whatsapp_full", timestamp="2026-06-01T00:00:00+00:00", file_count=10, total_bytes=1_000_000, verified=True):
    return BackupRecord(
        profile=profile,
        timestamp=timestamp,
        file_count=file_count,
        total_bytes=total_bytes,
        duration_seconds=12.5,
        destination="/media/drive/backup",
        verified=verified,
    )


class TestBuildBackupSummaryReport:
    def test_includes_profile_counts_and_duration(self):
        report = build_backup_summary_report(_record())

        text = report.sections[0].text
        assert "whatsapp_full" in text
        assert "10" in text
        assert "/media/drive/backup" in text
        assert "Yes" in text


class TestBuildBackupVerificationReport:
    def test_ok_status_when_counts_match(self):
        result = VerificationResult(expected_files=5, expected_bytes=1000, actual_files=5, actual_bytes=1000)

        report = build_backup_verification_report("whatsapp_full", result)

        section = report.sections[0]
        assert "OK" in section.text
        assert section.headers == ["Metric", "Expected", "Actual"]

    def test_mismatch_status_when_counts_differ(self):
        result = VerificationResult(expected_files=5, expected_bytes=1000, actual_files=4, actual_bytes=900)

        report = build_backup_verification_report("whatsapp_full", result)

        assert "MISMATCH" in report.sections[0].text


class TestBuildBackupHistoryReport:
    def test_lists_all_records(self):
        history = [
            _record(profile="whatsapp_full", timestamp="2026-06-01T00:00:00+00:00"),
            _record(profile="docs", timestamp="2026-06-02T00:00:00+00:00", verified=False),
        ]

        report = build_backup_history_report(history)

        section = report.sections[0]
        profiles = [row[1] for row in section.rows]
        assert profiles == ["whatsapp_full", "docs"]
        verified_flags = [row[-1] for row in section.rows]
        assert verified_flags == ["Yes", "No"]


class TestBuildSessionSummaryReport:
    def test_includes_logged_events(self, tmp_path):
        logger = SessionLogger.start(base_dir=tmp_path, session_id="20260612_000000")
        logger.log("Started backup")
        logger.log("Backup complete")

        report = build_session_summary_report(logger)

        section = report.sections[0]
        messages = [row[2] for row in section.rows]
        assert "Started backup" in messages
        assert "Backup complete" in messages
