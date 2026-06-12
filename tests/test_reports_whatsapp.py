"""Tests for droidbridge.reports.whatsapp_reports (spec §9.1)."""

from datetime import date, datetime

from droidbridge.modules.whatsapp import MediaFile, SECTION_PRIVATE, SECTION_RECEIVED, SECTION_SENT
from droidbridge.reports.whatsapp_reports import (
    build_cleanup_comparison_report,
    build_cutoff_comparison_report,
    build_documents_categorization_report,
    build_file_type_breakdown_report,
    build_media_inventory_report,
    build_section_breakdown_report,
)


def _media_files():
    return [
        MediaFile(path="/m/Images/IMG-20260101-WA0001.jpg", size=1000, mtime=datetime(2026, 1, 1), folder_type="Images", section=SECTION_RECEIVED),
        MediaFile(path="/m/Images/Sent/IMG-20260201-WA0002.jpg", size=2000, mtime=datetime(2026, 2, 1), folder_type="Images", section=SECTION_SENT),
        MediaFile(path="/m/Video/VID-20250101-WA0001.mp4", size=5000, mtime=datetime(2025, 1, 1), folder_type="Video", section=SECTION_RECEIVED),
        MediaFile(path="/m/Voice Notes/AUD-20260101-WA0001.opus", size=300, mtime=datetime(2026, 1, 1), folder_type="Voice Notes", section=SECTION_RECEIVED),
    ]


class TestBuildMediaInventoryReport:
    def test_includes_folder_and_month_breakdowns(self):
        report = build_media_inventory_report(_media_files())

        folder_section = next(s for s in report.sections if s.title == "By Folder")
        folders = [row[0] for row in folder_section.rows]
        assert "Images" in folders
        assert "Video" in folders

        month_section = next(s for s in report.sections if s.title == "By Month")
        months = [row[0] for row in month_section.rows]
        assert "2026-01" in months
        assert "2025-01" in months


class TestBuildCutoffComparisonReport:
    def test_splits_pre_and_post_cutoff(self):
        report = build_cutoff_comparison_report(_media_files(), cutoff=date(2026, 1, 15))

        section = report.sections[0]
        images_row = next(row for row in section.rows if row[0] == "Images")
        # Images: one pre-cutoff (Jan 1), one post-cutoff (Feb 1)
        assert images_row[1] == 1  # pre_count
        assert images_row[3] == 1  # post_count


class TestBuildFileTypeBreakdownReport:
    def test_sorted_by_size_descending(self):
        report = build_file_type_breakdown_report(_media_files())

        section = report.sections[0]
        sizes = [row[2] for row in section.rows]
        extensions = [row[0] for row in section.rows]
        assert extensions[0] == "mp4"  # largest single file (5000 bytes)
        assert sizes[0] != sizes[-1]


class TestBuildSectionBreakdownReport:
    def test_groups_by_section(self):
        report = build_section_breakdown_report(_media_files())

        section = report.sections[0]
        sections_seen = [row[0] for row in section.rows]
        assert SECTION_RECEIVED in sections_seen
        assert SECTION_SENT in sections_seen
        assert SECTION_PRIVATE not in sections_seen

        received_row = next(row for row in section.rows if row[0] == SECTION_RECEIVED)
        assert received_row[1] == 3  # 3 received files


class TestBuildDocumentsCategorizationReport:
    def test_groups_documents_by_category(self):
        media_files = [
            MediaFile(path="/m/Documents/report.pdf", size=1000, mtime=datetime(2026, 1, 1), folder_type="Documents", section=SECTION_RECEIVED),
            MediaFile(path="/m/Documents/archive.zip", size=2000, mtime=datetime(2026, 1, 1), folder_type="Documents", section=SECTION_RECEIVED),
            MediaFile(path="/m/Documents/notes.txt", size=300, mtime=datetime(2026, 1, 1), folder_type="Documents", section=SECTION_RECEIVED),
            MediaFile(path="/m/Images/photo.jpg", size=500, mtime=datetime(2026, 1, 1), folder_type="Images", section=SECTION_RECEIVED),
        ]

        report = build_documents_categorization_report(media_files)

        section = report.sections[0]
        categories = {row[0]: row[1] for row in section.rows}
        assert categories["PDFs"] == 1
        assert categories["Archives"] == 1
        assert categories["Other"] == 1
        assert "Images" not in categories or categories.get("Images") != 1  # photo.jpg not counted (not in Documents folder)


class TestBuildCleanupComparisonReport:
    def test_reports_before_after_deltas(self):
        before = _media_files()
        after = [m for m in before if m.folder_type != "Video"]  # Video folder fully cleaned up

        report = build_cleanup_comparison_report(before, after)

        section = report.sections[0]
        video_row = next(row for row in section.rows if row[0] == "Video")
        assert video_row[2] == 1  # before count
        assert video_row[3] == 0  # after count
        assert video_row[4] == "-1"  # count delta
