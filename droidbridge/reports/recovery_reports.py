# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Recovery session reports (Module 10): scan summary and backup restore summary."""

from droidbridge.reports.generators import Report, ReportSection
from droidbridge.utils.format import format_bytes


def build_scan_report(scan_results, pulled_count, restored_count, failed_count):
    """Scan session report: paths scanned, files found, recovered, failed."""
    total_size = sum(f.size_bytes for f in scan_results)
    section = ReportSection(
        title="Soft-Delete Scan",
        text=(
            f"Files found:        {len(scan_results)}  ({format_bytes(total_size)})\n"
            f"Saved to PC:        {pulled_count}\n"
            f"Restored to phone:  {restored_count}\n"
            f"Failed:             {failed_count}"
        ),
        headers=["Filename", "Size", "Date Modified", "Type", "Source App", "Restorable"],
        rows=[
            [
                f.filename,
                format_bytes(f.size_bytes),
                f.modified_date,
                f.file_type,
                f.source_app,
                "Yes" if f.is_true_trash else "No",
            ]
            for f in scan_results
        ],
    )
    return Report(title="Recovery Scan Report", sections=[section])


def build_restore_report(backup_info, contacts_result, calls_result):
    """Backup restore session report: contacts and call log restoration summary."""
    sections = []
    sections.append(ReportSection(
        title="Backup Used",
        text=(
            f"Path:               {backup_info.path}\n"
            f"Date:               {backup_info.date}\n"
            f"Contacts in backup: {backup_info.contacts_count}\n"
            f"Calls in backup:    {backup_info.calls_count}"
        ),
    ))
    if contacts_result is not None:
        sections.append(ReportSection(
            title="Contacts Restore",
            text=(
                f"Total:    {contacts_result.total}\n"
                f"Restored: {contacts_result.succeeded}\n"
                f"Failed:   {contacts_result.failed}\n"
                f"Skipped:  {contacts_result.skipped}"
                + (("\nErrors:\n" + "\n".join(contacts_result.errors)) if contacts_result.errors else "")
            ),
        ))
    if calls_result is not None:
        sections.append(ReportSection(
            title="Call Log Restore",
            text=(
                f"Total:    {calls_result.total}\n"
                f"Restored: {calls_result.succeeded}\n"
                f"Failed:   {calls_result.failed}\n"
                f"Skipped:  {calls_result.skipped}"
                + (("\nErrors:\n" + "\n".join(calls_result.errors)) if calls_result.errors else "")
            ),
        ))
    return Report(title="Recovery Restore Report", sections=sections)
