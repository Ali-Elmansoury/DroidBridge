# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.core.platform.linux - systemd-inhibit sleep inhibitor."""

from unittest.mock import MagicMock

from droidbridge.core.platform import linux


class TestSleepInhibitor:
    def test_starts_systemd_inhibit_on_enter(self, monkeypatch):
        monkeypatch.setattr(linux.shutil, "which", lambda name: "/usr/bin/systemd-inhibit")
        mock_popen = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(linux.subprocess, "Popen", mock_popen)

        with linux.SleepInhibitor("Transferring files"):
            pass

        args = mock_popen.call_args[0][0]
        assert args[0] == "systemd-inhibit"
        assert "--why=Transferring files" in args
        assert "--mode=block" in args

    def test_terminates_process_on_exit(self, monkeypatch):
        monkeypatch.setattr(linux.shutil, "which", lambda name: "/usr/bin/systemd-inhibit")
        mock_process = MagicMock()
        monkeypatch.setattr(linux.subprocess, "Popen", lambda *a, **k: mock_process)

        with linux.SleepInhibitor("Transferring files"):
            pass

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()

    def test_noop_when_systemd_inhibit_unavailable(self, monkeypatch):
        monkeypatch.setattr(linux.shutil, "which", lambda name: None)
        mock_popen = MagicMock()
        monkeypatch.setattr(linux.subprocess, "Popen", mock_popen)

        with linux.SleepInhibitor("Transferring files"):
            pass

        mock_popen.assert_not_called()

    def test_is_available_true_when_binary_present(self, monkeypatch):
        monkeypatch.setattr(linux.shutil, "which", lambda name: "/usr/bin/systemd-inhibit")

        assert linux.SleepInhibitor.is_available() is True

    def test_is_available_false_when_binary_missing(self, monkeypatch):
        monkeypatch.setattr(linux.shutil, "which", lambda name: None)

        assert linux.SleepInhibitor.is_available() is False

    def test_exit_is_noop_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(linux.shutil, "which", lambda name: None)

        inhibitor = linux.SleepInhibitor("Transferring files")
        with inhibitor:
            pass

        assert inhibitor._process is None
