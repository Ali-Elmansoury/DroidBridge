# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
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
from droidbridge.modules import transfer as transfer_module

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]

_WA_MEDIA = "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"
# detect_installs issues one compound shell command checking 4 [ -d ] paths (2 apps × 2 paths each).
_DETECT_WA_ONLY = "1\n0\n0\n0\n"   # modern WhatsApp path present, all others absent
_DETECT_NONE    = "0\n0\n0\n0\n"   # no WhatsApp installations found
_SCAN_OUTPUT = f"{_WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg\t1000\t1672531200.0\n"
_DELETE_SCAN_OUTPUT = (
    f"{_WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg\t1000\t1672531200.0\n"
    f"{_WA_MEDIA}/WhatsApp Images/IMG-20250101-WA0002.jpg\t2000\t1735689600.0\n"
)
_DELETE_RESCAN_OUTPUT = f"{_WA_MEDIA}/WhatsApp Images/IMG-20250101-WA0002.jpg\t2000\t1735689600.0\n"
_DF_OUTPUT = (
    "Filesystem     1K-blocks     Used Available Use% Mounted on\n"
    "/dev/fuse      120000000 80000000  40000000  67% /storage/emulated/0\n"
)


def _write_wa_backup_file(backup_dir, rel_path, size):
    path = backup_dir / "WhatsApp" / "Media" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


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
        # detect_installs makes one compound shell call; _DETECT_NONE → no installs → sys.exit(1)
        # but START log is written before the detect call, so "whatsapp scan" is always recorded.
        client = _make_client(shell_side_effect=[_DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["whatsapp", "scan"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "whatsapp scan" in log_text

    def test_whatsapp_scan_logs_scan_complete(self, monkeypatch, tmp_path):
        client = _make_client(shell_side_effect=[_DETECT_WA_ONLY, _SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["whatsapp", "scan"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "whatsapp scan" in log_text
        assert "Scan complete" in log_text

    def test_whatsapp_analyze_logs_start_and_end(self, monkeypatch, tmp_path):
        client = _make_client(shell_side_effect=[_DETECT_WA_ONLY, _SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["whatsapp", "analyze"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "whatsapp analyze" in log_text
        assert "Analysis complete" in log_text

    def test_whatsapp_backup_logs_start_and_end(self, monkeypatch, tmp_path):
        client = _make_client(shell_side_effect=[_DETECT_WA_ONLY, _SCAN_OUTPUT])

        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["whatsapp", "backup", "--dest", str(tmp_path / "backup")])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "whatsapp backup" in log_text
        assert "Backup complete" in log_text

    def test_whatsapp_delete_logs_start_and_end(self, monkeypatch, tmp_path):
        backup_dir = tmp_path / "backup"
        _write_wa_backup_file(backup_dir, "WhatsApp Images/IMG-20230101-WA0001.jpg", 1000)

        shell_outputs = [
            _DETECT_WA_ONLY,        # detect_installs
            _DELETE_SCAN_OUTPUT,    # scan_media
            _DF_OUTPUT,             # before_storage (get_storage_breakdown)
            "",                     # execute_delete_plan (rm)
            _DELETE_RESCAN_OUTPUT,  # verify_delete (rescan)
            _DF_OUTPUT,             # after_storage (get_storage_breakdown)
        ]
        client = _make_client(shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(
            main.cli,
            ["whatsapp", "delete", "--before", "2024-09-01", "--backup-dir", str(backup_dir)],
            input="YES DELETE\n",
        )

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "whatsapp delete" in log_text
        assert "Deletion complete" in log_text


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

    def test_backup_verify_logs_start_and_end(self, monkeypatch, tmp_path):
        from droidbridge.modules import backup_manager as bm
        profiles_path = tmp_path / "profiles.json"
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(bm, "DEFAULT_PROFILES_PATH", str(profiles_path))
        monkeypatch.setattr(bm, "DEFAULT_HISTORY_PATH", str(history_path))
        monkeypatch.chdir(tmp_path)

        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a.jpg").write_bytes(b"x" * 1000)

        bm.save_profile(profiles_path, bm.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(dest)))
        bm.append_history(
            history_path,
            bm.BackupRecord("test", "2026-06-01T00:00:00+00:00", 1, 1000, 1.0, str(dest), True),
        )

        CliRunner().invoke(main.cli, ["backup", "verify", "--profile", "test"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "backup verify" in log_text
        assert "Verification" in log_text


class TestTransferMirrorCommandsLog:
    def test_transfer_mirror_pull_logs_start_and_end(self, monkeypatch, tmp_path):
        local_camera = tmp_path / "Camera"

        def fake_plan_mirror_pull(client_, serial, remote_path, local_dir):
            local_camera.mkdir(exist_ok=True)
            (local_camera / "photo.jpg").write_bytes(b"x" * 1000)
            return transfer_module.TransferPlan(
                direction="pull",
                items=[transfer_module.TransferItem(
                    source="/sdcard/Camera/photo.jpg",
                    dest=str(local_camera / "photo.jpg"),
                    size=1000,
                    action=transfer_module.ACTION_COPY,
                )],
            )

        def fake_execute_mirror(client_, serial, plan, **kwargs):
            return transfer_module.MirrorResult(
                progress=transfer_module.TransferProgress(1, 1000, 1, 1000),
            )

        client = _make_client()
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.setattr(transfer_module, "plan_mirror_pull", fake_plan_mirror_pull)
        monkeypatch.setattr(transfer_module, "execute_mirror", fake_execute_mirror)
        monkeypatch.setattr(
            transfer_module, "verify_pull",
            lambda p: transfer_module.VerificationResult(1, 1000, 1, 1000),
        )
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["transfer", "mirror", "pull", "/sdcard/Camera", str(tmp_path)])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "transfer mirror pull" in log_text
        assert "Mirror complete" in log_text

    def test_transfer_mirror_push_logs_start_and_end(self, monkeypatch, tmp_path):
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        (local_dir / "photo.jpg").write_bytes(b"x" * 1000)

        def fake_plan_mirror_push(client_, serial, local_path, remote_dir):
            return transfer_module.TransferPlan(
                direction="push",
                items=[transfer_module.TransferItem(
                    source=str(local_dir / "photo.jpg"),
                    dest="/sdcard/Backup/photo.jpg",
                    size=1000,
                    action=transfer_module.ACTION_COPY,
                )],
            )

        def fake_execute_mirror(client_, serial, plan, **kwargs):
            return transfer_module.MirrorResult(
                progress=transfer_module.TransferProgress(1, 1000, 1, 1000),
            )

        client = _make_client()
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.setattr(transfer_module, "plan_mirror_push", fake_plan_mirror_push)
        monkeypatch.setattr(transfer_module, "execute_mirror", fake_execute_mirror)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(
            main.cli,
            ["transfer", "mirror", "push", str(local_dir), "/sdcard/Backup", "--no-verify"],
        )

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "transfer mirror push" in log_text
        assert "Mirror complete" in log_text


class TestReportGenerateLog:
    def test_report_generate_logs_start_and_end(self, monkeypatch, tmp_path):
        from droidbridge.modules import backup_manager as bm
        monkeypatch.setattr(bm, "DEFAULT_HISTORY_PATH", str(tmp_path / "history.json"))
        (tmp_path / "history.json").write_text("[]")
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["report", "generate", "--type", "backup-history"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "report generate" in log_text
        assert "Report written" in log_text
        assert "Report complete" in log_text


class TestFilesRenameLog:
    def test_files_rename_logs_start_and_end(self, monkeypatch, tmp_path):
        client = _make_client(shell_side_effect=[""])  # shell for rename
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["files", "rename", "/sdcard/old.jpg", "/sdcard/new.jpg"])

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "files rename" in log_text
        assert "Rename complete" in log_text

    def test_files_rename_writes_report(self, monkeypatch, tmp_path):
        client = _make_client(shell_side_effect=[""])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["files", "rename", "/sdcard/old.jpg", "/sdcard/new.jpg"])

        reports = list((tmp_path / "session_logs" / "reports").glob("files-rename_*.txt"))
        assert len(reports) == 1
        content = reports[0].read_text()
        assert "/sdcard/old.jpg" in content
        assert "/sdcard/new.jpg" in content


class TestFilesDeleteLog:
    def test_files_delete_logs_start_and_end(self, monkeypatch, tmp_path):
        # shell returns: stat (build_delete_plan), stat again (delete_paths), rm, verify
        client = _make_client(shell_side_effect=["100", "100", "", "NO"])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(
            main.cli,
            ["files", "delete", "/sdcard/a.jpg", "--yes"],
        )

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "files delete" in log_text
        assert "Deletion complete" in log_text

    def test_files_delete_writes_report(self, monkeypatch, tmp_path):
        client = _make_client(shell_side_effect=["100", "100", "", "NO"])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(
            main.cli,
            ["files", "delete", "/sdcard/a.jpg", "--yes"],
        )

        reports = list((tmp_path / "session_logs" / "reports").glob("files-delete_*.txt"))
        assert len(reports) == 1
        content = reports[0].read_text()
        assert "/sdcard/a.jpg" in content


class TestFilesSearchPullToLog:
    def test_files_search_pull_to_writes_transfer_report(self, monkeypatch, tmp_path):
        dest = tmp_path / "out"
        dest.mkdir()

        find_output = "/sdcard/photo.jpg\t1000\t1700000000.0\n"
        client = _make_client(shell_side_effect=[find_output])

        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(
            main.cli,
            ["files", "search", "/sdcard", "--pull-to", str(dest)],
        )

        reports = list((tmp_path / "session_logs" / "reports").glob("search-pull_*.txt"))
        assert len(reports) == 1

    def test_files_search_pull_to_logs_start_and_end(self, monkeypatch, tmp_path):
        dest = tmp_path / "out"
        dest.mkdir()

        find_output = "/sdcard/photo.jpg\t1000\t1700000000.0\n"
        client = _make_client(shell_side_effect=[find_output])

        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(
            main.cli,
            ["files", "search", "/sdcard", "--pull-to", str(dest)],
        )

        log_text = next((tmp_path / "session_logs").glob("session_*.log")).read_text()
        assert "files search --pull-to" in log_text
        assert "Pull complete" in log_text
