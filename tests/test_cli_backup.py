"""Tests for `droidbridge backup` (Module 6 CLI)."""

import os
from datetime import datetime
from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device
from droidbridge.modules import backup_manager

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]


def make_fake_client(devices, shell):
    client = MagicMock()
    client.devices.return_value = devices
    if callable(shell):
        client.shell.side_effect = shell
    else:
        client.shell.return_value = shell
    return client


class TestBackupProfileAdd:
    def test_adds_profile(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(
            main.cli,
            [
                "backup", "profile", "add", "whatsapp_full",
                "--source", "/sdcard/WhatsApp/Media",
                "--dest", "/backups/whatsapp",
            ],
        )

        assert result.exit_code == 0
        profiles = backup_manager.load_profiles(path)
        assert profiles["whatsapp_full"].sources == ["/sdcard/WhatsApp/Media"]
        assert profiles["whatsapp_full"].dest == "/backups/whatsapp"
        assert profiles["whatsapp_full"].conflict == "skip"

    def test_multiple_sources_and_conflict_option(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(
            main.cli,
            [
                "backup", "profile", "add", "full_media",
                "--source", "/sdcard/DCIM",
                "--source", "/sdcard/Download",
                "--dest", "/backups/media",
                "--conflict", "rename",
            ],
        )

        assert result.exit_code == 0
        profile = backup_manager.load_profiles(path)["full_media"]
        assert profile.sources == ["/sdcard/DCIM", "/sdcard/Download"]
        assert profile.conflict == "rename"

    def test_requires_at_least_one_source(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(
            main.cli, ["backup", "profile", "add", "empty", "--dest", "/backups/empty"]
        )

        assert result.exit_code != 0
        assert "source" in result.output.lower()


class TestBackupProfileList:
    def test_empty_list_message(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(main.cli, ["backup", "profile", "list"])

        assert result.exit_code == 0
        assert "no backup profiles" in result.output.lower()

    def test_lists_saved_profiles(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)
        backup_manager.save_profile(
            path,
            backup_manager.BackupProfile(name="whatsapp_full", sources=["/sdcard/WhatsApp/Media"], dest="/backups/wa"),
        )

        result = CliRunner().invoke(main.cli, ["backup", "profile", "list"])

        assert result.exit_code == 0
        assert "whatsapp_full" in result.output
        assert "/backups/wa" in result.output


class TestBackupProfileShow:
    def test_shows_profile_details(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)
        backup_manager.save_profile(
            path,
            backup_manager.BackupProfile(
                name="whatsapp_full",
                sources=["/sdcard/WhatsApp/Media", "/sdcard/WhatsApp Business/Media"],
                dest="/backups/wa",
                conflict="overwrite",
            ),
        )

        result = CliRunner().invoke(main.cli, ["backup", "profile", "show", "whatsapp_full"])

        assert result.exit_code == 0
        assert "/sdcard/WhatsApp/Media" in result.output
        assert "/sdcard/WhatsApp Business/Media" in result.output
        assert "/backups/wa" in result.output
        assert "overwrite" in result.output

    def test_shows_excludes_when_set(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)
        backup_manager.save_profile(
            path,
            backup_manager.BackupProfile(
                name="media_backup",
                sources=["/sdcard/DCIM"],
                dest="/backups/dcim",
                conflict="skip",
                excludes=["/sdcard/DCIM/thumbnails", "/sdcard/DCIM/.trash"],
            ),
        )

        result = CliRunner().invoke(main.cli, ["backup", "profile", "show", "media_backup"])

        assert result.exit_code == 0
        assert "/sdcard/DCIM/thumbnails" in result.output
        assert "/sdcard/DCIM/.trash" in result.output

    def test_shows_none_when_excludes_empty(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)
        backup_manager.save_profile(
            path,
            backup_manager.BackupProfile(
                name="simple",
                sources=["/sdcard/Documents"],
                dest="/backups/docs",
            ),
        )

        result = CliRunner().invoke(main.cli, ["backup", "profile", "show", "simple"])

        assert result.exit_code == 0
        assert "Excludes" in result.output
        assert "(none)" in result.output

    def test_unknown_profile_errors(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(main.cli, ["backup", "profile", "show", "nope"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestBackupRun:
    def test_unknown_profile_errors(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(main.cli, ["backup", "run", "--profile", "nope"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_no_device_shows_guidance(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(tmp_path / "dest")),
        )

        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["backup", "run", "--profile", "test"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_runs_backup_pulls_files_verifies_and_records_history(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", history_path)

        dest = tmp_path / "backup_dest"
        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(dest)),
        )

        def fake_shell(serial, command, timeout=None):
            if isinstance(command, str) and command.startswith("if [ -d"):
                return "1000"
            raise AssertionError(command)

        def fake_pull(serial, remote, local):
            os.makedirs(os.path.dirname(local), exist_ok=True)
            with open(local, "wb") as f:
                f.write(b"x" * 1000)

        client = make_fake_client(READY_DEVICE, fake_shell)
        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["backup", "run", "--profile", "test"])

        assert result.exit_code == 0
        assert "Verified: 1 file" in result.output

        history = backup_manager.load_history(history_path)
        assert len(history) == 1
        assert history[0].profile == "test"
        assert history[0].file_count == 1
        assert history[0].total_bytes == 1000
        assert history[0].verified is True


class TestBackupHistory:
    def test_empty_history_message(self, tmp_path, monkeypatch):
        path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", path)

        result = CliRunner().invoke(main.cli, ["backup", "history"])

        assert result.exit_code == 0
        assert "no backup history" in result.output.lower()

    def test_lists_all_records(self, tmp_path, monkeypatch):
        path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", path)
        backup_manager.append_history(
            path,
            backup_manager.BackupRecord("whatsapp_full", "2026-06-01T00:00:00+00:00", 10, 1000, 5.0, "/backups/wa", True),
        )
        backup_manager.append_history(
            path,
            backup_manager.BackupRecord("docs", "2026-06-02T00:00:00+00:00", 3, 300, 1.0, "/backups/docs", False),
        )

        result = CliRunner().invoke(main.cli, ["backup", "history"])

        assert result.exit_code == 0
        assert "whatsapp_full" in result.output
        assert "docs" in result.output

    def test_profile_filter_shows_outdated_status(self, tmp_path, monkeypatch):
        path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", path)
        backup_manager.append_history(
            path,
            backup_manager.BackupRecord("docs", "2020-01-01T00:00:00+00:00", 3, 300, 1.0, "/backups/docs", True),
        )

        result = CliRunner().invoke(main.cli, ["backup", "history", "--profile", "docs", "--max-age-days", "7"])

        assert result.exit_code == 0
        assert "docs" in result.output
        assert "outdated" in result.output.lower()

    def test_profile_filter_shows_comparison(self, tmp_path, monkeypatch):
        path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", path)
        backup_manager.append_history(
            path,
            backup_manager.BackupRecord("docs", "2026-06-01T00:00:00+00:00", 10, 1000, 1.0, "/backups/docs", True),
        )
        backup_manager.append_history(
            path,
            backup_manager.BackupRecord("docs", "2026-06-10T00:00:00+00:00", 15, 1500, 1.0, "/backups/docs", True),
        )

        result = CliRunner().invoke(main.cli, ["backup", "history", "--profile", "docs"])

        assert result.exit_code == 0
        assert "+5" in result.output

    def test_unknown_profile_no_records(self, tmp_path, monkeypatch):
        path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", path)

        result = CliRunner().invoke(main.cli, ["backup", "history", "--profile", "nope"])

        assert result.exit_code == 0
        assert "no backups recorded" in result.output.lower()


class TestBackupRestore:
    def test_unknown_profile_errors(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(main.cli, ["backup", "restore", "--profile", "nope"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_no_device_shows_guidance(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(tmp_path)),
        )

        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["backup", "restore", "--profile", "test"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_restores_pushes_files_and_verifies(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        (tmp_path / "a.jpg").write_bytes(b"x" * 1000)
        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(tmp_path)),
        )

        dir_checks = {"count": 0}

        def fake_shell(serial, command, timeout=None):
            if command.startswith("[ -d"):
                dir_checks["count"] += 1
                return "DIR" if dir_checks["count"] > 1 else "NO"
            if command.startswith("mkdir -p"):
                return ""
            if command.startswith("find -L"):
                return "/sdcard/a.jpg\t1000\t1700000000\n"
            raise AssertionError(command)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["backup", "restore", "--profile", "test"])

        assert result.exit_code == 0
        assert "Verified: 1 file" in result.output
        client.push.assert_called_once()

    def test_source_filter_skips_other_sources(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        (tmp_path / "a.jpg").write_bytes(b"x" * 100)
        (tmp_path / "b.jpg").write_bytes(b"x" * 100)
        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg", "/sdcard/b.jpg"], dest=str(tmp_path)),
        )

        def fake_shell(serial, command, timeout=None):
            if command.startswith("[ -d"):
                return "NO"
            if command.startswith("mkdir -p"):
                return ""
            raise AssertionError(command)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["backup", "restore", "--profile", "test", "--source", "/sdcard/b.jpg", "--no-verify"]
        )

        assert result.exit_code == 0
        assert "/sdcard/a.jpg" not in result.output
        assert "/sdcard/b.jpg" in result.output

    def test_date_filter_excludes_old_files(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        f = tmp_path / "a.jpg"
        f.write_bytes(b"x" * 100)
        os.utime(f, (datetime(2020, 1, 1).timestamp(),) * 2)
        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(tmp_path)),
        )

        def fake_shell(serial, command, timeout=None):
            if command.startswith("[ -d"):
                return "NO"
            raise AssertionError(command)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli,
            ["backup", "restore", "--profile", "test", "--after", "2026-01-01", "--no-verify"],
        )

        assert result.exit_code == 0
        assert "Nothing to transfer" in result.output


class TestBackupProfileRemove:
    def test_removes_profile(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)
        backup_manager.save_profile(
            path, backup_manager.BackupProfile(name="docs", sources=["/sdcard/Documents"], dest="/backups/docs")
        )

        result = CliRunner().invoke(main.cli, ["backup", "profile", "remove", "docs"])

        assert result.exit_code == 0
        assert backup_manager.load_profiles(path) == {}

    def test_unknown_profile_errors(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(main.cli, ["backup", "profile", "remove", "nope"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()


class TestBackupProfileCreateExclude:
    def test_single_exclude_saved(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(
            main.cli,
            [
                "backup", "profile", "add", "myprofile",
                "--source", "/sdcard/DCIM",
                "--dest", "/tmp/backup",
                "--exclude", "/sdcard/DCIM/thumbnails",
            ],
        )

        assert result.exit_code == 0
        profiles = backup_manager.load_profiles(path)
        assert profiles["myprofile"].excludes == ["/sdcard/DCIM/thumbnails"]

    def test_multiple_excludes_saved(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(
            main.cli,
            [
                "backup", "profile", "add", "myprofile",
                "--source", "/sdcard/DCIM",
                "--dest", "/tmp/backup",
                "--exclude", "/sdcard/DCIM/thumbnails",
                "--exclude", "/sdcard/DCIM/.trashed",
            ],
        )

        assert result.exit_code == 0
        profiles = backup_manager.load_profiles(path)
        assert profiles["myprofile"].excludes == ["/sdcard/DCIM/thumbnails", "/sdcard/DCIM/.trashed"]

    def test_no_exclude_defaults_to_empty(self, tmp_path, monkeypatch):
        path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", path)

        result = CliRunner().invoke(
            main.cli,
            [
                "backup", "profile", "add", "myprofile",
                "--source", "/sdcard/DCIM",
                "--dest", "/tmp/backup",
            ],
        )

        assert result.exit_code == 0
        profiles = backup_manager.load_profiles(path)
        assert profiles["myprofile"].excludes == []


class TestBackupVerify:
    def test_unknown_profile_errors(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", history_path)

        result = CliRunner().invoke(main.cli, ["backup", "verify", "--profile", "nope"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_no_backup_history_errors(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", history_path)
        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(tmp_path / "dest")),
        )

        result = CliRunner().invoke(main.cli, ["backup", "verify", "--profile", "test"])

        assert result.exit_code == 1
        assert "no backups recorded" in result.output.lower()

    def test_matching_destination_passes_and_writes_report(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", history_path)
        monkeypatch.chdir(tmp_path)

        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a.jpg").write_bytes(b"x" * 1000)

        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(dest)),
        )
        backup_manager.append_history(
            history_path,
            backup_manager.BackupRecord("test", "2026-06-01T00:00:00+00:00", 1, 1000, 1.0, str(dest), True),
        )

        result = CliRunner().invoke(main.cli, ["backup", "verify", "--profile", "test"])

        assert result.exit_code == 0
        assert "Status: OK" in result.output

        reports = list((tmp_path / "session_logs" / "reports").glob("backup-verification_test_*.txt"))
        assert len(reports) == 1

    def test_mismatched_destination_fails(self, tmp_path, monkeypatch):
        profiles_path = tmp_path / "profiles.json"
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", history_path)
        monkeypatch.chdir(tmp_path)

        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a.jpg").write_bytes(b"x" * 500)

        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="test", sources=["/sdcard/a.jpg"], dest=str(dest)),
        )
        backup_manager.append_history(
            history_path,
            backup_manager.BackupRecord("test", "2026-06-01T00:00:00+00:00", 1, 1000, 1.0, str(dest), True),
        )

        result = CliRunner().invoke(main.cli, ["backup", "verify", "--profile", "test"])

        assert result.exit_code == 1
        assert "Status: MISMATCH" in result.output
