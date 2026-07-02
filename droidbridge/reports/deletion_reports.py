# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Deletion reports (spec §9.4)."""

from collections import Counter

from droidbridge.reports.generators import Report, ReportSection
from droidbridge.utils.format import format_bytes


def _signed_bytes(delta):
    sign = "+" if delta >= 0 else "-"
    return f"{sign}{format_bytes(abs(delta))}"


def build_deletion_preview_report(plan):
    """Pre-deletion preview report: what will be deleted, by year and type (spec §9.4 / §4.6)."""
    totals = {}
    for media_file in plan.to_delete:
        year = media_file.date.year if media_file.date else "Unknown"
        key = (media_file.folder_type, year)
        count, size = totals.get(key, (0, 0))
        totals[key] = (count + 1, size + media_file.size)

    rows = [
        [folder_type, year, count, format_bytes(size)]
        for (folder_type, year), (count, size) in sorted(totals.items(), key=lambda item: (item[0][0], str(item[0][1])))
    ]
    table = ReportSection(title="Files to Delete", headers=["Folder", "Year", "Files", "Size"], rows=rows)
    overview = ReportSection(
        title="Overview",
        text=f"To delete: {plan.total_files} file(s), {format_bytes(plan.total_bytes)}. Kept: {len(plan.kept)} file(s).",
    )
    return Report(title="Pre-Deletion Preview Report", sections=[overview, table])


def build_deletion_result_report(plan, verification):
    """Post-deletion report: files deleted, failed, and space freed (spec §9.4 / §4.6)."""
    failed = verification.remaining
    failed_paths = {media_file.path for media_file in failed}
    freed_bytes = sum(media_file.size for media_file in plan.to_delete if media_file.path not in failed_paths)

    result = ReportSection(
        title="Result",
        text=(
            f"Deleted: {verification.deleted} file(s)\n"
            f"Failed: {len(failed)} file(s)\n"
            f"Space freed: {format_bytes(freed_bytes)}"
        ),
    )

    plan_by_month = Counter(f.year_month for f in plan.to_delete)
    remaining_by_month = Counter(f.year_month for f in verification.remaining)

    month_lines = []
    for month in sorted(plan_by_month):
        planned = plan_by_month[month]
        rem = remaining_by_month.get(month, 0)
        if rem == 0:
            status = "Done"
        elif rem < planned:
            status = "Partial"
        else:
            status = "Pending"
        month_lines.append(
            f"  {month:<12} {planned:>6} planned  {rem:>6} remaining  {status}"
        )
    if not month_lines:
        month_lines = ["  (no dated files in deletion plan)"]

    monthly_section = ReportSection(title="Monthly Status", text="\n".join(month_lines))

    sections = [result, monthly_section]
    if failed:
        sections.append(
            ReportSection(
                title="Failed Files",
                headers=["Path", "Size"],
                rows=[[media_file.path, format_bytes(media_file.size)] for media_file in failed],
            )
        )
    return Report(title="Post-Deletion Report", sections=sections)


def build_storage_comparison_report(before, after):
    """Phone storage before vs after comparison (spec §9.4)."""
    section = ReportSection(
        title="Storage Comparison",
        headers=["Metric", "Before", "After", "Change"],
        rows=[
            [
                "Used",
                format_bytes(before.used_kb * 1024),
                format_bytes(after.used_kb * 1024),
                _signed_bytes((after.used_kb - before.used_kb) * 1024),
            ],
            [
                "Free",
                format_bytes(before.free_kb * 1024),
                format_bytes(after.free_kb * 1024),
                _signed_bytes((after.free_kb - before.free_kb) * 1024),
            ],
        ],
    )
    return Report(title="Storage Before/After Comparison Report", sections=[section])
