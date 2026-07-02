# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.core.platform.windows - SetThreadExecutionState sleep inhibitor."""

from unittest.mock import MagicMock

from droidbridge.core.platform import windows


class TestSleepInhibitor:
    def test_sets_execution_state_on_enter(self, monkeypatch):
        mock_kernel32 = MagicMock()
        monkeypatch.setattr(windows.ctypes, "windll", MagicMock(kernel32=mock_kernel32), raising=False)

        with windows.SleepInhibitor("Transferring files"):
            pass

        mock_kernel32.SetThreadExecutionState.assert_any_call(
            windows.ES_CONTINUOUS | windows.ES_SYSTEM_REQUIRED
        )

    def test_restores_execution_state_on_exit(self, monkeypatch):
        mock_kernel32 = MagicMock()
        monkeypatch.setattr(windows.ctypes, "windll", MagicMock(kernel32=mock_kernel32), raising=False)

        with windows.SleepInhibitor("Transferring files"):
            pass

        last_call = mock_kernel32.SetThreadExecutionState.call_args_list[-1]
        assert last_call.args == (windows.ES_CONTINUOUS,)

    def test_noop_when_windll_unavailable(self, monkeypatch):
        monkeypatch.delattr(windows.ctypes, "windll", raising=False)

        with windows.SleepInhibitor("Transferring files"):
            pass

    def test_is_available_true_when_windll_present(self, monkeypatch):
        monkeypatch.setattr(windows.ctypes, "windll", MagicMock(), raising=False)

        assert windows.SleepInhibitor.is_available() is True

    def test_is_available_false_when_windll_missing(self, monkeypatch):
        monkeypatch.delattr(windows.ctypes, "windll", raising=False)

        assert windows.SleepInhibitor.is_available() is False
