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


class TestWriteReportAutoLogs:
    def test_write_report_logs_report_written_line(self, monkeypatch, tmp_path):
        """_write_report() should call logger.log() so the report path appears in the session log."""
        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)

        client = _make_client(shell_side_effect=["1000"])
        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        logs = list((tmp_path / "session_logs").glob("session_*.log"))
        log_text = logs[0].read_text()
        assert "Report written" in log_text


class TestTransferCommandsLog:
    def test_transfer_pull_logs_start_and_end(self, monkeypatch, tmp_path):
        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)

        client = _make_client(shell_side_effect=["1000"])
        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "transfer pull" in log_text
        assert "Pull complete" in log_text

    def test_transfer_push_logs_start_and_end(self, monkeypatch, tmp_path):
        src = tmp_path / "local.txt"
        src.write_bytes(b"hello")

        # shell calls: _remote_dir_exists for plan_push, mkdir -p in execute_plan,
        # stat for verify_push
        client = _make_client(shell_side_effect=["NO", "", ""])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["transfer", "push", str(src), "/sdcard/"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "transfer push" in log_text
        assert "Push complete" in log_text


class TestWhatsappCommandsLog:
    def test_whatsapp_scan_logs_start(self, monkeypatch, tmp_path):
        client = _make_client(
            shell_side_effect=[
                "package:com.whatsapp",                         # pm list packages
                "/sdcard/Android/media/com.whatsapp/WhatsApp",  # stat media path
                "",                                             # find output (empty)
            ]
        )
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["whatsapp", "scan"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "whatsapp scan" in log_text


class TestBackupCommandsLog:
    def test_backup_run_logs_start_and_end(self, monkeypatch, tmp_path):
        profiles_path = tmp_path / "profiles.json"
        import json as _json
        profiles_path.write_text(_json.dumps({
            "myprofile": {
                "name": "myprofile",
                "sources": ["/sdcard/DCIM"],
                "dest": str(tmp_path / "backup"),
                "conflict": "skip",
                "excludes": [],
            }
        }))

        from droidbridge.modules import backup_manager as bm
        monkeypatch.setattr(bm, "DEFAULT_PROFILES_PATH", str(profiles_path))
        monkeypatch.setattr(bm, "DEFAULT_HISTORY_PATH", str(tmp_path / "history.json"))

        # shell calls: stat /sdcard/DCIM to get source dir size, then verify_pull
        client = _make_client(shell_side_effect=["0", ""])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["backup", "run", "--profile", "myprofile", "--no-verify"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "backup run" in log_text
        assert "Backup complete" in log_text


class TestReportGenerateLog:
    def test_report_generate_logs_start_and_end(self, monkeypatch, tmp_path):
        from droidbridge.modules import backup_manager as bm
        monkeypatch.setattr(bm, "DEFAULT_HISTORY_PATH", str(tmp_path / "history.json"))
        (tmp_path / "history.json").write_text("[]")
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["report", "generate", "--type", "backup-history"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "report generate" in log_text
        assert "Report complete" in log_text
