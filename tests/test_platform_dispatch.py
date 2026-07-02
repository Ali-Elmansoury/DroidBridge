# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.core.platform.get_sleep_inhibitor - per-OS dispatch."""

from droidbridge.core import platform as platform_module
from droidbridge.core.platform import linux, macos, windows


class TestGetSleepInhibitor:
    def test_returns_linux_inhibitor_on_linux(self):
        inhibitor = platform_module.get_sleep_inhibitor("reason", system="Linux")

        assert isinstance(inhibitor, linux.SleepInhibitor)
        assert inhibitor.reason == "reason"

    def test_returns_windows_inhibitor_on_windows(self):
        inhibitor = platform_module.get_sleep_inhibitor("reason", system="Windows")

        assert isinstance(inhibitor, windows.SleepInhibitor)
        assert inhibitor.reason == "reason"

    def test_returns_macos_inhibitor_on_darwin(self):
        inhibitor = platform_module.get_sleep_inhibitor("reason", system="Darwin")

        assert isinstance(inhibitor, macos.SleepInhibitor)
        assert inhibitor.reason == "reason"

    def test_unknown_platform_falls_back_to_linux(self):
        inhibitor = platform_module.get_sleep_inhibitor("reason", system="FreeBSD")

        assert isinstance(inhibitor, linux.SleepInhibitor)

    def test_defaults_to_platform_system(self, monkeypatch):
        monkeypatch.setattr(platform_module.platform, "system", lambda: "Windows")

        inhibitor = platform_module.get_sleep_inhibitor("reason")

        assert isinstance(inhibitor, windows.SleepInhibitor)
