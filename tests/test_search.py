# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.modules.search - Module 7: Search & Discovery."""

import shlex
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from droidbridge.modules.search import _build_find_command, search_files, MIME_GROUPS, mime_to_extensions
from droidbridge.modules import search

FIND_OUTPUT = (
    "/sdcard/DCIM/Bills/Bills-11-07-2023_12_50.png\t160704\t1689025803.483978172\n"
    "/sdcard/DCIM/Bills/Bills-05-08-2023_10_56.png\t164115\t1691265386.892539985\n"
    "/sdcard/Download/report.pdf\t52428800\t1577836800.0\n"
    "/sdcard/Download/noext\t100\t1500000000.0\n"
)


def make_fake_client(output):
    client = MagicMock()
    client.shell.return_value = output
    return client


def _ts(value):
    return datetime.fromtimestamp(value)


class TestSearchResult:
    def test_name_and_extension_properties(self):
        result = search.SearchResult(
            path="/sdcard/DCIM/Bills/Bills-11-07-2023_12_50.png",
            size=160704,
            mtime=_ts(1689025803.483978172),
        )

        assert result.name == "Bills-11-07-2023_12_50.png"
        assert result.extension == "png"

    def test_no_extension(self):
        result = search.SearchResult(path="/sdcard/Download/noext", size=100, mtime=_ts(1500000000.0))

        assert result.name == "noext"
        assert result.extension == ""


class TestSearchFiles:
    def test_parses_all_results_with_no_filters(self):
        client = make_fake_client(FIND_OUTPUT)

        results = search.search_files(client, "SERIAL", "/sdcard")

        assert [r.path for r in results] == [
            "/sdcard/DCIM/Bills/Bills-11-07-2023_12_50.png",
            "/sdcard/DCIM/Bills/Bills-05-08-2023_10_56.png",
            "/sdcard/Download/report.pdf",
            "/sdcard/Download/noext",
        ]
        assert results[0].size == 160704
        assert results[0].mtime == _ts(1689025803.483978172)

    def test_default_root_is_sdcard(self):
        client = make_fake_client("")

        search.search_files(client, "SERIAL")

        cmd = client.shell.call_args[0][1]
        assert cmd.startswith("find -L /sdcard -type f")

    def test_quotes_root_path_with_spaces(self):
        client = make_fake_client("")

        search.search_files(client, "SERIAL", "/sdcard/My Folder")

        cmd = client.shell.call_args[0][1]
        assert "'/sdcard/My Folder'" in cmd

    def test_name_pattern_uses_iname(self):
        client = make_fake_client("")

        search.search_files(client, "SERIAL", "/sdcard", name_pattern="*.jpg")

        cmd = client.shell.call_args[0][1]
        assert "-iname '*.jpg'" in cmd

    def test_filter_by_extensions(self):
        client = make_fake_client(FIND_OUTPUT)

        results = search.search_files(client, "SERIAL", "/sdcard", extensions=["pdf"])

        assert [r.path for r in results] == ["/sdcard/Download/report.pdf"]

    def test_filter_by_size_range(self):
        client = make_fake_client(FIND_OUTPUT)

        results = search.search_files(client, "SERIAL", "/sdcard", min_size=100_000, max_size=200_000)

        assert [r.path for r in results] == [
            "/sdcard/DCIM/Bills/Bills-11-07-2023_12_50.png",
            "/sdcard/DCIM/Bills/Bills-05-08-2023_10_56.png",
        ]

    def test_filter_by_date_range(self):
        client = make_fake_client(FIND_OUTPUT)

        results = search.search_files(
            client, "SERIAL", "/sdcard", after=_ts(1600000000), before=_ts(1700000000)
        )

        assert [r.path for r in results] == [
            "/sdcard/DCIM/Bills/Bills-11-07-2023_12_50.png",
            "/sdcard/DCIM/Bills/Bills-05-08-2023_10_56.png",
        ]

    def test_combined_type_date_and_size_filters(self):
        client = make_fake_client(FIND_OUTPUT)

        results = search.search_files(
            client,
            "SERIAL",
            "/sdcard",
            extensions=["png"],
            after=_ts(1690000000),
            min_size=160000,
        )

        assert [r.path for r in results] == ["/sdcard/DCIM/Bills/Bills-05-08-2023_10_56.png"]


class TestSortResults:
    def _results(self):
        return [
            search.SearchResult(path="/b/B.txt", size=200, mtime=_ts(2000)),
            search.SearchResult(path="/a/a.jpg", size=100, mtime=_ts(3000)),
            search.SearchResult(path="/c/c.pdf", size=300, mtime=_ts(1000)),
        ]

    def test_sort_by_name(self):
        result = search.sort_results(self._results(), by="name")
        assert [r.name for r in result] == ["a.jpg", "B.txt", "c.pdf"]

    def test_sort_by_size(self):
        result = search.sort_results(self._results(), by="size")
        assert [r.size for r in result] == [100, 200, 300]

    def test_sort_by_date(self):
        result = search.sort_results(self._results(), by="date")
        assert [r.mtime for r in result] == [_ts(1000), _ts(2000), _ts(3000)]

    def test_sort_by_path_reverse(self):
        result = search.sort_results(self._results(), by="path", reverse=True)
        assert [r.path for r in result] == ["/c/c.pdf", "/b/B.txt", "/a/a.jpg"]


class TestPresetNames:
    def test_preset_names_contents(self):
        assert search.PRESET_NAMES == (
            "whatsapp",
            "photos",
            "videos",
            "documents",
            "apks",
            "large",
            "old",
            "no-extension",
        )


class TestPresetFilters:
    def test_photos_preset(self):
        root, kwargs = search.preset_filters("photos")
        assert kwargs["extensions"] == ["jpg", "jpeg", "png", "heic", "raw"]

    def test_videos_preset(self):
        root, kwargs = search.preset_filters("videos")
        assert kwargs["extensions"] == ["mp4", "mov", "mkv"]

    def test_documents_preset(self):
        root, kwargs = search.preset_filters("documents")
        assert kwargs["extensions"] == ["pdf", "docx", "pptx", "xlsx"]

    def test_apks_preset(self):
        root, kwargs = search.preset_filters("apks")
        assert kwargs["extensions"] == ["apk"]

    def test_large_preset(self):
        root, kwargs = search.preset_filters("large")
        assert kwargs["min_size"] == 50 * 1024 * 1024

    def test_old_preset(self):
        now = datetime(2026, 6, 11)
        root, kwargs = search.preset_filters("old", now=now)
        assert kwargs["before"] == now - timedelta(days=365)

    def test_no_extension_preset(self):
        root, kwargs = search.preset_filters("no-extension")
        assert kwargs["extensions"] == [""]

    def test_whatsapp_preset_overrides_root(self):
        root, kwargs = search.preset_filters("whatsapp")
        assert root == search.WHATSAPP_MEDIA_PATH

    def test_unknown_preset_raises(self):
        try:
            search.preset_filters("bogus")
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestRegexSearch:
    def test_build_find_command_with_regex_has_no_regextype(self):
        # BusyBox find (Android) doesn't support -regextype; regex filtering
        # is done in Python, so the find command must not include these flags.
        cmd = _build_find_command("/sdcard", name_regex=".*\\.jpg")
        assert "-regextype" not in cmd
        assert "-iregex" not in cmd
        assert "-iname" not in cmd

    def test_search_files_regex_filtered_in_python(self):
        # find returns two files; only the .jpg should survive the Python regex filter
        client = make_fake_client(
            "/sdcard/photo.jpg\t1000\t1700000000.0\n"
            "/sdcard/notes.txt\t500\t1700000000.0\n"
        )
        results = search_files(client, "serial", name_regex="IMG_.*\\.jpg")
        # no files match IMG_*.jpg pattern
        assert len(results) == 0

    def test_search_files_regex_matches_filename(self):
        client = make_fake_client(
            "/sdcard/IMG_001.jpg\t1000\t1700000000.0\n"
            "/sdcard/notes.txt\t500\t1700000000.0\n"
        )
        results = search_files(client, "serial", name_regex="IMG_.*\\.jpg")
        assert len(results) == 1
        assert results[0].path == "/sdcard/IMG_001.jpg"

    def test_search_files_regex_is_case_insensitive(self):
        client = make_fake_client("/sdcard/img_001.JPG\t1000\t1700000000.0\n")
        results = search_files(client, "serial", name_regex="IMG_.*\\.jpg")
        assert len(results) == 1

    def test_search_files_regex_does_not_appear_in_find_cmd(self):
        client = make_fake_client("")
        search_files(client, "serial", name_regex=".*\\.jpg")
        cmd = client.shell.call_args[0][1]
        assert "-regextype" not in cmd
        assert "-iregex" not in cmd

    def test_search_files_raises_if_both_pattern_and_regex(self):
        client = make_fake_client("")
        with pytest.raises(ValueError, match="Cannot use both"):
            search_files(client, "serial", name_pattern="*.jpg", name_regex=".*\\.jpg")

    def test_no_regex_flags_without_name_regex(self):
        client = make_fake_client("")
        search_files(client, "serial")
        cmd = client.shell.call_args[0][1]
        assert "-regextype" not in cmd
        assert "-iregex" not in cmd


class TestMimeGroups:
    def test_category_name_returns_extension_list(self):
        exts = mime_to_extensions("image")
        assert "jpg" in exts
        assert "png" in exts
        assert "heic" in exts

    def test_full_mime_string_uses_category_only(self):
        exts = mime_to_extensions("video/mp4")
        assert "mp4" in exts
        assert "mkv" in exts

    def test_case_insensitive(self):
        exts = mime_to_extensions("AUDIO")
        assert "mp3" in exts

    def test_unknown_mime_raises(self):
        with pytest.raises(ValueError, match="Unknown MIME category"):
            mime_to_extensions("font/woff")

    def test_all_categories_present(self):
        for cat in ("image", "video", "audio", "document", "archive"):
            assert cat in MIME_GROUPS
            assert len(MIME_GROUPS[cat]) > 0
