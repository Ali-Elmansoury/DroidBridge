"""Integration tests for CLI session logging (sub-project #9)."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]


@contextmanager
def _noop_inhibitor(*args, **kwargs):
    yield


def _make_client(shell_side_effect=None):
    client = MagicMock()
    client.devices.return_value = READY_DEVICE
    if shell_side_effect is not None:
        client.shell.side_effect = shell_side_effect
    return client


class TestSessionLifecycle:
    def test_session_log_is_created(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: _make_client(shell_side_effect=[""]))
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["files", "browse", "/sdcard"])

        logs = list((tmp_path / "session_logs").glob("session_*.log"))
        assert len(logs) == 1

    def test_session_summary_json_is_created(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: _make_client(shell_side_effect=[""]))
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["files", "browse", "/sdcard"])

        summaries = list((tmp_path / "session_logs").glob("session_*_summary.json"))
        assert len(summaries) == 1

    def test_summary_json_has_events_key(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: _make_client(shell_side_effect=[""]))
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["files", "browse", "/sdcard"])

        summaries = list((tmp_path / "session_logs").glob("session_*_summary.json"))
        data = json.loads(summaries[0].read_text())
        assert "events" in data
        assert "session_id" in data

    def test_one_log_per_invocation(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: _make_client(shell_side_effect=["", ""]))
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["files", "browse", "/sdcard"])
        CliRunner().invoke(main.cli, ["files", "browse", "/sdcard"])

        logs = list((tmp_path / "session_logs").glob("session_*.log"))
        assert len(logs) == 2
