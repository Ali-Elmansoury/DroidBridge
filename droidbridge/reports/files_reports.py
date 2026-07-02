# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""File rename and delete reports."""

from droidbridge.reports.generators import Report, ReportSection


def build_files_rename_report(old_path: str, new_path: str) -> Report:
    """Single-section report recording a file rename."""
    section = ReportSection(
        title="Rename Details",
        headers=["Field", "Path"],
        rows=[["Old path", old_path], ["New path", new_path]],
    )
    return Report(title="File Rename", sections=[section])


def build_files_delete_report(paths: list) -> Report:
    """Single-section report recording deleted paths."""
    rows = [[p] for p in paths]
    section = ReportSection(
        title=f"Deleted {len(paths)} file(s)",
        headers=["Path"],
        rows=rows,
    )
    return Report(title="File Deletion", sections=[section])
