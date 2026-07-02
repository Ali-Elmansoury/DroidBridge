# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Backup reports (spec §9.3): summary, verification, history log, session summary."""

from droidbridge.reports.generators import Report, ReportSection
from droidbridge.utils.format import format_bytes, format_duration


def build_backup_summary_report(record):
    """Backup summary report for a single `BackupRecord` (spec §9.3)."""
    section = ReportSection(
        title="Backup Summary",
        text=(
            f"Profile: {record.profile}\n"
            f"Destination: {record.destination}\n"
            f"Files: {record.file_count}\n"
            f"Size: {format_bytes(record.total_bytes)}\n"
            f"Duration: {format_duration(record.duration_seconds)}\n"
            f"Verified: {'Yes' if record.verified else 'No'}"
        ),
    )
    return Report(title=f"Backup Summary — {record.profile}", sections=[section], generated_at=record.timestamp)


def build_backup_verification_report(profile_name, result):
    """Backup verification report: expected vs actual files/bytes (spec §9.3)."""
    status = "OK" if result.ok else "MISMATCH"
    section = ReportSection(
        title="Verification",
        text=f"Status: {status}",
        headers=["Metric", "Expected", "Actual"],
        rows=[
            ["Files", result.expected_files, result.actual_files],
            ["Bytes", format_bytes(result.expected_bytes), format_bytes(result.actual_bytes)],
        ],
    )
    return Report(title=f"Backup Verification — {profile_name}", sections=[section])


def build_backup_history_report(history):
    """Backup history log report: all recorded backup runs (spec §9.3 / §6.4)."""
    rows = [
        [
            record.timestamp,
            record.profile,
            record.file_count,
            format_bytes(record.total_bytes),
            format_duration(record.duration_seconds),
            record.destination,
            "Yes" if record.verified else "No",
        ]
        for record in history
    ]
    section = ReportSection(
        title="Backup History",
        headers=["Timestamp", "Profile", "Files", "Size", "Duration", "Destination", "Verified"],
        rows=rows,
    )
    return Report(title="Backup History Report", sections=[section])


def build_session_summary_report(session_logger):
    """Session summary report: all operations performed during a session (spec §9.3 / §9.6)."""
    rows = [[event["timestamp"], event["level"], event["message"]] for event in session_logger.events]
    section = ReportSection(
        title=f"Session {session_logger.session_id}",
        headers=["Timestamp", "Level", "Message"],
        rows=rows,
    )
    return Report(title="Session Summary Report", sections=[section])
