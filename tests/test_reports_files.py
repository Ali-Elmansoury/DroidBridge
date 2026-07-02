# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.reports.files_reports."""

from droidbridge.reports import files_reports
from droidbridge.reports.generators import to_txt


class TestBuildFilesRenameReport:
    def test_contains_both_paths(self):
        report = files_reports.build_files_rename_report(
            "/sdcard/old.jpg", "/sdcard/new.jpg"
        )
        txt = to_txt(report)
        assert "/sdcard/old.jpg" in txt
        assert "/sdcard/new.jpg" in txt

    def test_title_is_file_rename(self):
        report = files_reports.build_files_rename_report("/a", "/b")
        assert report.title == "File Rename"

    def test_has_one_section(self):
        report = files_reports.build_files_rename_report("/a", "/b")
        assert len(report.sections) == 1


class TestBuildFilesDeleteReport:
    def test_contains_all_paths(self):
        paths = ["/sdcard/a.jpg", "/sdcard/b.jpg", "/sdcard/c.jpg"]
        report = files_reports.build_files_delete_report(paths)
        txt = to_txt(report)
        for p in paths:
            assert p in txt

    def test_contains_count(self):
        paths = ["/sdcard/a.jpg", "/sdcard/b.jpg"]
        report = files_reports.build_files_delete_report(paths)
        txt = to_txt(report)
        assert "2" in txt

    def test_title_is_file_deletion(self):
        report = files_reports.build_files_delete_report(["/a"])
        assert report.title == "File Deletion"

    def test_empty_paths_produces_valid_report(self):
        report = files_reports.build_files_delete_report([])
        txt = to_txt(report)
        assert "0" in txt

    def test_has_one_section(self):
        report = files_reports.build_files_delete_report(["/a", "/b"])
        assert len(report.sections) == 1
