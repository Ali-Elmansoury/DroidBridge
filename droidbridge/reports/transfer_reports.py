"""Transfer reports (spec §9.5/§3.5): success/failure summary for pull, push, and mirror operations."""

from droidbridge.reports.generators import Report, ReportSection
from droidbridge.utils.format import format_bytes

_TITLES = {
    "pull": "Transfer Report — Pull",
    "push": "Transfer Report — Push",
    "mirror-pull": "Transfer Report — Mirror Pull",
    "mirror-push": "Transfer Report — Mirror Push",
}


def build_transfer_report(direction, plan, progress, verification=None, mirror_result=None):
    """Build a Report summarizing a transfer/mirror run.

    direction is one of 'pull', 'push', 'mirror-pull', 'mirror-push'.
    verification is a VerificationResult or None (omit section when None).
    mirror_result is a MirrorResult or None (omit mirror sections when None).
    """
    sections = [ReportSection(
        title="Transfer Summary",
        text=f"Direction: {direction}",
        headers=["Metric", "Value"],
        rows=[
            ["Planned files", plan.total_files],
            ["Planned bytes", format_bytes(plan.total_bytes)],
            ["Transferred files", progress.done_files],
            ["Transferred bytes", format_bytes(progress.done_bytes)],
            ["Already present (skipped)", len(plan.already_present)],
            ["Conflicts skipped", len(plan.conflicts_skipped)],
            ["Failed", len(progress.failed)],
        ],
    )]

    if progress.failed:
        sections.append(ReportSection(
            title="Failed Items",
            headers=["Source", "Destination", "Error"],
            rows=[[f.item.source, f.item.dest, f.error] for f in progress.failed],
        ))

    if verification is not None:
        status = "OK" if verification.ok else "MISMATCH"
        sections.append(ReportSection(
            title="Verification",
            text=f"Status: {status}",
            headers=["Metric", "Expected", "Actual"],
            rows=[
                ["Files", verification.expected_files, verification.actual_files],
                ["Bytes", format_bytes(verification.expected_bytes), format_bytes(verification.actual_bytes)],
            ],
        ))

    if mirror_result is not None:
        sections.append(ReportSection(
            title="Mirror Extras",
            headers=["Metric", "Value"],
            rows=[
                ["Extra files found", plan.extra_files],
                ["Extra bytes found", format_bytes(plan.extra_bytes)],
                ["Deleted files", mirror_result.deleted_files],
                ["Deleted bytes", format_bytes(mirror_result.deleted_bytes)],
                ["Failed deletions", len(mirror_result.failed_deletions)],
            ],
        ))
        if mirror_result.failed_deletions:
            sections.append(ReportSection(
                title="Failed Deletions",
                headers=["Path", "Error"],
                rows=[[f.item.path, f.error] for f in mirror_result.failed_deletions],
            ))

    return Report(title=_TITLES[direction], sections=sections)
