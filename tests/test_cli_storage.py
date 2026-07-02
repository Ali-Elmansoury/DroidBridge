# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for `droidbridge storage` (Module 5 CLI)."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device
from droidbridge.modules import storage as storage_module
from droidbridge.modules.search import SearchResult
from tests.test_search import FIND_OUTPUT
from tests.test_storage import DF_OUTPUT, DISKSTATS_OUTPUT, PM_LIST_SYSTEM_OUTPUT, _ts

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]

EMPTY_DISKSTATS_OUTPUT = (
    "App Size: 0\n"
    "App Data Size: 0\n"
    "App Cache Size: 0\n"
    "Photos Size: 0\n"
    "Videos Size: 0\n"
    "Audio Size: 0\n"
    "Downloads Size: 0\n"
    "System Size: 0\n"
    "Other Size: 0\n"
    'Package Names: []\n'
    "App Sizes: []\n"
    "App Data Sizes: []\n"
    "Cache Sizes: []\n"
)


def make_fake_client(devices, shell):
    client = MagicMock()
    client.devices.return_value = devices
    if callable(shell):
        client.shell.side_effect = shell
    else:
        client.shell.return_value = shell
    return client


class TestStorageAnalyze:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "analyze"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_shows_totals_bar_and_categories(self, monkeypatch):
        def fake_shell(serial, command, timeout=None):
            if command[0] == "df":
                return DF_OUTPUT
            if command[:2] == ["dumpsys", "diskstats"]:
                return DISKSTATS_OUTPUT
            raise AssertionError(command)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "analyze"])

        assert result.exit_code == 0
        assert "Total:" in result.output
        assert "Used:" in result.output
        assert "Free:" in result.output
        assert "[" in result.output and "%" in result.output
        assert "Photos" in result.output
        assert "System" in result.output


def _apps_fake_shell(serial, command, timeout=None):
    if command[:2] == ["dumpsys", "diskstats"]:
        return DISKSTATS_OUTPUT
    if command[:3] == ["pm", "list", "packages"]:
        return PM_LIST_SYSTEM_OUTPUT
    raise AssertionError(command)


class TestStorageApps:
    def test_lists_apps_by_total_size_descending(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "apps"])

        assert result.exit_code == 0
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert lines[0].startswith("com.whatsapp")
        assert "com.android.chrome" in result.output

    def test_top_limits_results(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "apps", "--top", "1"])

        lines = [line for line in result.output.splitlines() if line.strip()]
        assert len(lines) == 1
        assert "com.whatsapp" in lines[0]

    def test_system_filter(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "apps", "--system"])

        assert "com.android.chrome" in result.output
        assert "com.whatsapp" not in result.output

    def test_user_filter(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "apps", "--user"])

        assert "com.whatsapp" in result.output
        assert "com.android.chrome" not in result.output


class TestStorageMedia:
    def test_shows_category_breakdown_and_largest_files(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, FIND_OUTPUT)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "media"])

        assert result.exit_code == 0
        assert "photos" in result.output
        assert "videos" in result.output
        assert "documents" in result.output
        assert "report.pdf" in result.output

    def test_caps_duplicate_groups_shown(self, monkeypatch):
        groups = [
            [
                SearchResult(path=f"/sdcard/a{i}.jpg", size=1000 + i, mtime=_ts(2024)),
                SearchResult(path=f"/sdcard/b{i}.jpg", size=1000 + i, mtime=_ts(2024)),
            ]
            for i in range(15)
        ]
        breakdown = storage_module.MediaBreakdown(
            categories={"photos": (30, 30000), "videos": (0, 0), "audio": (0, 0), "documents": (0, 0)},
            largest_files=[],
            duplicates=groups,
            total_count=30,
            total_size=30000,
        )
        monkeypatch.setattr(storage_module, "analyze_media", lambda *a, **k: breakdown)

        client = make_fake_client(READY_DEVICE, "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "media"])

        assert result.exit_code == 0
        assert "Duplicates: 15 group(s)" in result.output
        assert len([line for line in result.output.splitlines() if "x2" in line]) == 10
        assert "5 more group" in result.output


class TestStorageLargeFiles:
    def test_lists_files_at_or_above_default_threshold(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, FIND_OUTPUT)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "large-files"])

        assert result.exit_code == 0
        assert "report.pdf" in result.output
        assert "Bills-11-07-2023_12_50.png" not in result.output

    def test_custom_min_size(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, FIND_OUTPUT)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "large-files", "--min-size", "100KB"])

        assert "Bills-11-07-2023_12_50.png" in result.output
        assert "Bills-05-08-2023_10_56.png" in result.output
        assert "report.pdf" in result.output
        assert "noext" not in result.output

    def test_no_results_message(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "large-files"])

        assert "no large files found" in result.output.lower()


class TestStorageSuggestCleanup:
    def test_shows_suggestions_with_estimates(self, monkeypatch):
        def fake_shell(serial, command, timeout=None):
            if isinstance(command, str):
                if command.startswith("find -L /sdcard/Download"):
                    return "/sdcard/Download/app.apk\t5000000\t1700000000.0\n"
                if command.startswith("find -L /sdcard "):
                    return "/sdcard/old.log\t1000\t1000000000.0\n"
                if command.startswith("[ -d"):
                    return "0\n"
                raise AssertionError(command)
            if command[:2] == ["dumpsys", "diskstats"]:
                return DISKSTATS_OUTPUT
            if command[:3] == ["pm", "list", "packages"]:
                return PM_LIST_SYSTEM_OUTPUT
            raise AssertionError(command)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "suggest-cleanup"])

        assert result.exit_code == 0
        assert "Clear app caches" in result.output
        assert "com.android.chrome" in result.output
        assert "APK installer files in Downloads" in result.output
        assert "/sdcard/Download/app.apk" in result.output
        assert "Old log files" in result.output
        assert "Total estimated recoverable" in result.output

    def test_no_suggestions_message(self, monkeypatch):
        def fake_shell(serial, command, timeout=None):
            if isinstance(command, str):
                if command.startswith("find"):
                    return ""
                if command.startswith("[ -d"):
                    return "0\n"
                raise AssertionError(command)
            if command[:2] == ["dumpsys", "diskstats"]:
                return EMPTY_DISKSTATS_OUTPUT
            if command[:3] == ["pm", "list", "packages"]:
                return ""
            raise AssertionError(command)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["storage", "suggest-cleanup"])

        assert result.exit_code == 0
        assert "no cleanup suggestions" in result.output.lower()
