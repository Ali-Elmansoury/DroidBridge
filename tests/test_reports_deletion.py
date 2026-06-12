"""Tests for droidbridge.reports.deletion_reports (spec §9.4)."""

from datetime import datetime

from droidbridge.modules.storage import StorageOverview
from droidbridge.modules.whatsapp import DeletePlan, DeleteVerification, MediaFile, SECTION_RECEIVED
from droidbridge.reports.deletion_reports import (
    build_deletion_preview_report,
    build_deletion_result_report,
    build_storage_comparison_report,
)


def _media_file(path, size, year):
    return MediaFile(path=path, size=size, mtime=datetime(year, 1, 1), folder_type="Images", section=SECTION_RECEIVED)


class TestBuildDeletionPreviewReport:
    def test_breaks_down_by_year_and_type(self):
        plan = DeletePlan(
            to_delete=[
                _media_file("/m/Images/IMG-20240101-WA0001.jpg", 1000, 2024),
                _media_file("/m/Images/IMG-20250101-WA0001.jpg", 2000, 2025),
            ],
            kept=[_media_file("/m/Images/IMG-20260101-WA0001.jpg", 500, 2026)],
        )

        report = build_deletion_preview_report(plan)

        overview = report.sections[0]
        assert "2" in overview.text  # 2 files to delete
        assert "Kept: 1" in overview.text

        table = report.sections[1]
        assert table.headers == ["Folder", "Year", "Files", "Size"]
        years = [row[1] for row in table.rows]
        assert 2024 in years
        assert 2025 in years


class TestBuildDeletionResultReport:
    def test_reports_deleted_and_failed_counts(self):
        deleted_file = _media_file("/m/Images/IMG-20240101-WA0001.jpg", 1000, 2024)
        failed_file = _media_file("/m/Images/IMG-20250101-WA0001.jpg", 2000, 2025)
        plan = DeletePlan(to_delete=[deleted_file, failed_file], kept=[])
        verification = DeleteVerification(deleted=1, remaining=[failed_file])

        report = build_deletion_result_report(plan, verification)

        text = report.sections[0].text
        assert "Deleted: 1" in text
        assert "Failed: 1" in text
        assert "1000" in text or "1 KB" in text or "1.0 KB" in text  # space freed reflects only the deleted file

        failed_section = report.sections[1]
        assert failed_section.rows[0][0] == "/m/Images/IMG-20250101-WA0001.jpg"

    def test_no_failed_section_when_all_deleted(self):
        deleted_file = _media_file("/m/Images/IMG-20240101-WA0001.jpg", 1000, 2024)
        plan = DeletePlan(to_delete=[deleted_file], kept=[])
        verification = DeleteVerification(deleted=1, remaining=[])

        report = build_deletion_result_report(plan, verification)

        assert len(report.sections) == 1


class TestBuildStorageComparisonReport:
    def test_reports_used_and_free_deltas(self):
        before = StorageOverview(total_kb=1000, used_kb=800, free_kb=200, categories={})
        after = StorageOverview(total_kb=1000, used_kb=600, free_kb=400, categories={})

        report = build_storage_comparison_report(before, after)

        section = report.sections[0]
        used_row = next(row for row in section.rows if row[0] == "Used")
        assert used_row[3].startswith("-")

        free_row = next(row for row in section.rows if row[0] == "Free")
        assert free_row[3].startswith("+")
