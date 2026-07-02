# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""WhatsApp analysis reports (spec §9.1)."""

from droidbridge.modules.whatsapp import (
    DOCUMENT_CATEGORIES,
    SECTION_PRIVATE,
    SECTION_RECEIVED,
    SECTION_SENT,
    summarize_by_cutoff,
    summarize_by_extension,
    summarize_by_folder,
    summarize_by_year_month,
)
from droidbridge.reports.generators import Report, ReportSection
from droidbridge.utils.format import format_bytes

_SECTION_ORDER = (SECTION_RECEIVED, SECTION_SENT, SECTION_PRIVATE)


def _signed_bytes(delta):
    sign = "+" if delta >= 0 else "-"
    return f"{sign}{format_bytes(abs(delta))}"


def build_media_inventory_report(media_files):
    """Full media inventory: all folders, all years/months, file counts, sizes (spec §9.1)."""
    total_count = len(media_files)
    total_size = sum(m.size for m in media_files)

    folder_section = ReportSection(
        title="By Folder",
        headers=["Folder", "Section", "Files", "Size"],
        rows=[[s.folder_type, s.section, s.file_count, format_bytes(s.total_size)] for s in summarize_by_folder(media_files)],
    )
    month_section = ReportSection(
        title="By Month",
        headers=["Month", "Files", "Size"],
        rows=[[s.year_month, s.file_count, format_bytes(s.total_size)] for s in summarize_by_year_month(media_files)],
    )
    overview = ReportSection(
        title="Overview",
        text=f"Total files: {total_count}, Total size: {format_bytes(total_size)}",
    )
    return Report(title="WhatsApp Media Inventory Report", sections=[overview, folder_section, month_section])


def build_cutoff_comparison_report(media_files, cutoff):
    """Pre vs post cutoff comparison report, by folder type (spec §9.1 / §4.7)."""
    rows = [
        [s.folder_type, s.pre_count, format_bytes(s.pre_size), s.post_count, format_bytes(s.post_size), s.unknown_count, format_bytes(s.unknown_size)]
        for s in summarize_by_cutoff(media_files, cutoff)
    ]
    section = ReportSection(
        title=f"Cutoff: {cutoff.isoformat()}",
        headers=["Folder", "Pre Count", "Pre Size", "Post Count", "Post Size", "Unknown Count", "Unknown Size"],
        rows=rows,
    )
    return Report(title="WhatsApp Pre/Post Cutoff Comparison Report", sections=[section])


def build_file_type_breakdown_report(media_files):
    """File type breakdown report: extension, count, total size, sorted by size descending (spec §9.1)."""
    summaries = sorted(summarize_by_extension(media_files), key=lambda s: s.total_size, reverse=True)
    rows = [[s.extension or "(none)", s.file_count, format_bytes(s.total_size)] for s in summaries]
    section = ReportSection(title="File Types", headers=["Extension", "Files", "Size"], rows=rows)
    return Report(title="WhatsApp File Type Breakdown Report", sections=[section])


def build_section_breakdown_report(media_files):
    """Sent vs Received vs Private breakdown report (spec §9.1)."""
    totals = {}
    for media_file in media_files:
        count, size = totals.get(media_file.section, (0, 0))
        totals[media_file.section] = (count + 1, size + media_file.size)

    rows = [[section, totals[section][0], format_bytes(totals[section][1])] for section in _SECTION_ORDER if section in totals]
    report_section = ReportSection(title="By Section", headers=["Section", "Files", "Size"], rows=rows)
    return Report(title="WhatsApp Sent/Received/Private Breakdown Report", sections=[report_section])


def build_documents_categorization_report(media_files):
    """Documents categorization report: PDFs, Archives, Images, Videos, Code, etc. (spec §9.1)."""
    totals = {}
    for media_file in media_files:
        if media_file.folder_type != "Documents":
            continue
        category = DOCUMENT_CATEGORIES.get(media_file.extension, "Other")
        count, size = totals.get(category, (0, 0))
        totals[category] = (count + 1, size + media_file.size)

    rows = sorted([[category, count, format_bytes(size)] for category, (count, size) in totals.items()], key=lambda r: r[0])
    section = ReportSection(title="Documents by Category", headers=["Category", "Files", "Size"], rows=rows)
    return Report(title="WhatsApp Documents Categorization Report", sections=[section])


def build_cleanup_comparison_report(before_files, after_files):
    """Before/after cleanup comparison report, by folder type and section (spec §9.1)."""
    before = {(s.folder_type, s.section): s for s in summarize_by_folder(before_files)}
    after = {(s.folder_type, s.section): s for s in summarize_by_folder(after_files)}

    rows = []
    for key in sorted(set(before) | set(after)):
        before_summary = before.get(key)
        after_summary = after.get(key)
        before_count = before_summary.file_count if before_summary else 0
        after_count = after_summary.file_count if after_summary else 0
        before_size = before_summary.total_size if before_summary else 0
        after_size = after_summary.total_size if after_summary else 0
        rows.append(
            [
                key[0],
                key[1],
                before_count,
                after_count,
                f"{after_count - before_count:+d}",
                format_bytes(before_size),
                format_bytes(after_size),
                _signed_bytes(after_size - before_size),
            ]
        )

    section = ReportSection(
        title="Before vs After",
        headers=["Folder", "Section", "Before Count", "After Count", "Count Δ", "Before Size", "After Size", "Size Δ"],
        rows=rows,
    )
    return Report(title="WhatsApp Cleanup Comparison Report", sections=[section])
