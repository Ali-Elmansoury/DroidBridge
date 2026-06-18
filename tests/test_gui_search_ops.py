"""Tests for droidbridge.gui.search_ops (Phase 6.2) — plain functions, no Qt."""

from datetime import datetime
from unittest.mock import MagicMock

from droidbridge.gui import search_ops
from droidbridge.modules import search as search_module

FIND_OUTPUT = (
    "/sdcard/DCIM/photo1.jpg\t1000\t1700000000.0\n"
    "/sdcard/Download/report.pdf\t52428800\t1577836800.0\n"
    "/sdcard/Download/clip.mp4\t2000\t1690000000.0\n"
)


def make_fake_client(output):
    client = MagicMock()
    client.shell.return_value = output
    return client


class TestBuildSearchKwargs:
    def test_no_filters_defaults_to_default_root(self):
        root, kwargs = search_ops.build_search_kwargs(
            root="", name="", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset=None,
        )

        assert root == search_module.DEFAULT_ROOT
        assert kwargs == {}

    def test_explicit_root_overrides_default(self):
        root, _ = search_ops.build_search_kwargs(
            root="/sdcard/Download", name="", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset=None,
        )

        assert root == "/sdcard/Download"

    def test_name_pattern_gets_wrapped_in_wildcards(self):
        _, kwargs = search_ops.build_search_kwargs(
            root="", name="report", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset=None,
        )

        assert kwargs["name_pattern"] == "*report*"

    def test_name_pattern_with_wildcard_is_not_rewrapped(self):
        _, kwargs = search_ops.build_search_kwargs(
            root="", name="rep*rt", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset=None,
        )

        assert kwargs["name_pattern"] == "rep*rt"

    def test_preset_sets_extensions_and_default_root(self):
        root, kwargs = search_ops.build_search_kwargs(
            root="", name="", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset="photos",
        )

        assert root == search_module.DEFAULT_ROOT
        assert kwargs["extensions"] == search_module.PRESET_EXTENSIONS["photos"]

    def test_preset_root_used_when_root_empty(self):
        root, _ = search_ops.build_search_kwargs(
            root="", name="", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset="whatsapp",
        )

        assert root == search_module.WHATSAPP_MEDIA_PATH

    def test_explicit_root_overrides_preset_root(self):
        root, _ = search_ops.build_search_kwargs(
            root="/sdcard/Download", name="", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset="whatsapp",
        )

        assert root == "/sdcard/Download"

    def test_explicit_extensions_override_preset_extensions(self):
        _, kwargs = search_ops.build_search_kwargs(
            root="", name="", extensions=["mp4"], min_size=None, max_size=None,
            after=None, before=None, preset="photos",
        )

        assert kwargs["extensions"] == ["mp4"]

    def test_min_max_size_and_dates_pass_through(self):
        after = datetime(2023, 1, 1)
        before = datetime(2023, 12, 31)

        _, kwargs = search_ops.build_search_kwargs(
            root="", name="", extensions=None, min_size=1000, max_size=2000,
            after=after, before=before, preset=None,
        )

        assert kwargs["min_size"] == 1000
        assert kwargs["max_size"] == 2000
        assert kwargs["after"] == after
        assert kwargs["before"] == before


class TestRunSearch:
    def test_filters_and_sorts_results(self):
        client = make_fake_client(FIND_OUTPUT)

        results = search_ops.run_search(
            client, "SERIAL", "/sdcard", extensions=["jpg", "pdf"], sort_by="size"
        )

        assert [r.name for r in results] == ["photo1.jpg", "report.pdf"]

    def test_preset_is_applied(self):
        client = make_fake_client(FIND_OUTPUT)

        results = search_ops.run_search(client, "SERIAL", "", preset="videos")

        assert [r.name for r in results] == ["clip.mp4"]
        client.shell.assert_called_once()
        assert "/sdcard" in client.shell.call_args[0][1]


class TestBuildSearchKwargsNameRegex:
    def test_name_regex_included_in_kwargs(self):
        _, kwargs = search_ops.build_search_kwargs(
            root="", name="", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset=None, name_regex="IMG_.*\\.jpg",
        )
        assert kwargs.get("name_regex") == "IMG_.*\\.jpg"
        assert "name_pattern" not in kwargs

    def test_name_regex_none_not_added_to_kwargs(self):
        _, kwargs = search_ops.build_search_kwargs(
            root="", name="", extensions=None, min_size=None, max_size=None,
            after=None, before=None, preset=None, name_regex=None,
        )
        assert "name_regex" not in kwargs


class TestRunSearchNameRegex:
    def test_run_search_with_name_regex_filters_results(self):
        client = make_fake_client(
            "/sdcard/IMG_001.jpg\t1000\t1700000000.0\n"
            "/sdcard/notes.txt\t500\t1700000000.0\n"
        )
        results = search_ops.run_search(client, "SERIAL", "", name_regex="IMG_.*\\.jpg")
        assert len(results) == 1
        assert results[0].path == "/sdcard/IMG_001.jpg"
