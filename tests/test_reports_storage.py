# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.reports.storage_reports (spec §9.2)."""

from datetime import datetime

from droidbridge.modules.search import SearchResult
from droidbridge.modules.storage import AppStorageInfo, StorageOverview
from droidbridge.reports.storage_reports import (
    StorageSnapshot,
    build_large_files_report,
    build_storage_overview_report,
    build_storage_trend_report,
    build_top_apps_report,
    load_storage_history,
    record_storage_snapshot,
)


class TestBuildStorageOverviewReport:
    def test_includes_totals_and_categories(self):
        overview = StorageOverview(
            total_kb=100_000_000,
            used_kb=80_000_000,
            free_kb=20_000_000,
            categories={"Apps": 1_000_000_000, "Photos": 2_000_000_000},
        )

        report = build_storage_overview_report(overview)

        overview_section = report.sections[0]
        assert "80%" in overview_section.text

        categories_section = report.sections[1]
        assert categories_section.headers == ["Category", "Size"]
        rows_by_category = dict(categories_section.rows)
        assert "Apps" in rows_by_category
        assert "Photos" in rows_by_category

    def test_omits_zero_byte_categories(self):
        overview = StorageOverview(
            total_kb=100_000_000,
            used_kb=80_000_000,
            free_kb=20_000_000,
            categories={"Apps": 1_000_000_000, "Downloads": 0},
        )

        report = build_storage_overview_report(overview)

        categories_section = report.sections[1]
        rows_by_category = dict(categories_section.rows)
        assert "Apps" in rows_by_category
        assert "Downloads" not in rows_by_category

    def test_omits_categories_section_when_all_zero(self):
        overview = StorageOverview(
            total_kb=100_000_000, used_kb=80_000_000, free_kb=20_000_000, categories={"Downloads": 0}
        )

        report = build_storage_overview_report(overview)

        assert len(report.sections) == 1


class TestBuildTopAppsReport:
    def test_sorts_by_total_size_descending(self):
        apps = [
            AppStorageInfo(package="small.app", apk_size=10, data_size=10, cache_size=10, is_system=False),
            AppStorageInfo(package="big.app", apk_size=1000, data_size=2000, cache_size=3000, is_system=False),
        ]

        report = build_top_apps_report(apps, top=5)

        section = report.sections[0]
        assert section.headers == ["Package", "APK", "Data", "Cache", "Total"]
        assert section.rows[0][0] == "big.app"
        assert section.rows[1][0] == "small.app"

    def test_limits_to_top_n(self):
        apps = [
            AppStorageInfo(package=f"app{i}", apk_size=i, data_size=0, cache_size=0, is_system=False)
            for i in range(10)
        ]

        report = build_top_apps_report(apps, top=3)

        assert len(report.sections[0].rows) == 3


class TestBuildLargeFilesReport:
    def test_lists_files_with_size_and_date(self):
        results = [
            SearchResult(path="/sdcard/movie.mp4", size=200_000_000, mtime=datetime(2026, 1, 1)),
            SearchResult(path="/sdcard/photo.jpg", size=5_000_000, mtime=datetime(2026, 2, 1)),
        ]

        report = build_large_files_report(results)

        section = report.sections[0]
        assert section.headers == ["Path", "Size", "Modified"]
        assert section.rows[0][0] == "/sdcard/movie.mp4"
        assert "2026-01-01" in section.rows[0][2]


class TestStorageTrendHistory:
    def test_record_and_load_round_trip(self, tmp_path):
        path = tmp_path / "storage_history.json"
        overview = StorageOverview(total_kb=1000, used_kb=400, free_kb=600, categories={})

        record_storage_snapshot(overview, path=path, timestamp="2026-06-01T00:00:00+00:00")

        history = load_storage_history(path=path)

        assert history == [
            StorageSnapshot(timestamp="2026-06-01T00:00:00+00:00", total_kb=1000, used_kb=400, free_kb=600)
        ]

    def test_load_missing_file_returns_empty(self, tmp_path):
        path = tmp_path / "does_not_exist.json"

        assert load_storage_history(path=path) == []


class TestBuildStorageTrendReport:
    def test_reports_growth_and_shrinkage(self):
        history = [
            StorageSnapshot(timestamp="2026-06-01T00:00:00+00:00", total_kb=1000, used_kb=400, free_kb=600),
            StorageSnapshot(timestamp="2026-06-08T00:00:00+00:00", total_kb=1000, used_kb=500, free_kb=500),
            StorageSnapshot(timestamp="2026-06-15T00:00:00+00:00", total_kb=1000, used_kb=450, free_kb=550),
        ]

        report = build_storage_trend_report(history)

        section = report.sections[0]
        assert section.headers == ["Date", "Used", "Free", "Change"]
        assert section.rows[0][3] == ""
        assert section.rows[1][3].startswith("+")
        assert section.rows[2][3].startswith("-")
