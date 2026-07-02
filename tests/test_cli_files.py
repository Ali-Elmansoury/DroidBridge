# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for `droidbridge files browse` (Module 2 CLI)."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import AdbCommandError, Device
from droidbridge.modules import search as search_module
from tests.test_files import LS_OUTPUT_DCIM, LS_OUTPUT_EMPTY


def make_fake_client(devices, shell_result=LS_OUTPUT_DCIM):
    client = MagicMock()
    client.devices.return_value = devices

    if isinstance(shell_result, Exception):
        client.shell.side_effect = shell_result
    else:
        client.shell.return_value = shell_result

    return client


READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]


class TestFilesBrowse:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["files", "browse", "/sdcard"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_default_excludes_hidden_and_sorts_by_name(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "browse", "/sdcard/DCIM"])

        assert result.exit_code == 0
        lines = [line for line in result.output.splitlines() if line.strip()]
        names = [line.split()[-1] for line in lines]
        assert names == ["12qj1lm88zmui6jf70yc1wk2u.jpg", "Bills"]

    def test_default_path_is_sdcard(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result=LS_OUTPUT_EMPTY)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        CliRunner().invoke(main.cli, ["files", "browse"])

        client.shell.assert_called_once_with("SERIAL123", "ls -la /sdcard/")

    def test_all_flag_includes_hidden(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "browse", "/sdcard/DCIM", "--all"])

        lines = [line for line in result.output.splitlines() if line.strip()]
        names = [line[33:] for line in lines]
        assert names == [
            ".319e7450d45d5b00.cfg",
            ".Save Stickers",
            "12qj1lm88zmui6jf70yc1wk2u.jpg",
            "Bills",
        ]

    def test_sort_by_size(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "browse", "/sdcard/DCIM", "--all", "--sort", "size"]
        )

        lines = [line for line in result.output.splitlines() if line.strip()]
        names = [line.split()[-1] for line in lines]
        # sizes: cfg=89, Save Stickers=4096, jpg=24647, Bills=4096
        assert names[0] == ".319e7450d45d5b00.cfg"
        assert names[-1] == "12qj1lm88zmui6jf70yc1wk2u.jpg"

    def test_filter_by_extension(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "browse", "/sdcard/DCIM", "--ext", "jpg"]
        )

        lines = [line for line in result.output.splitlines() if line.strip()]
        names = [line.split()[-1] for line in lines]
        assert names == ["12qj1lm88zmui6jf70yc1wk2u.jpg", "Bills"]

    def test_empty_directory_shows_message(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result=LS_OUTPUT_EMPTY)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "browse", "/sdcard/EmptyDir"])

        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    def test_unknown_path_shows_error(self, monkeypatch):
        error = AdbCommandError(
            ["adb", "shell", "ls"], 1, "", "ls: /sdcard/Nope: No such file or directory\n"
        )
        client = make_fake_client(READY_DEVICE, shell_result=error)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "browse", "/sdcard/Nope"])

        assert result.exit_code == 1
        assert "no such file or directory" in result.output.lower()


class TestFilesRename:
    def test_success_prints_confirmation(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result="")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "rename", "/sdcard/old.txt", "/sdcard/new.txt"])

        assert result.exit_code == 0
        assert "Renamed /sdcard/old.txt -> /sdcard/new.txt" in result.output
        client.shell.assert_called_once_with(
            "SERIAL123",
            "if [ -e /sdcard/new.txt ]; then echo EXISTS; "
            "else mv /sdcard/old.txt /sdcard/new.txt; fi",
        )

    def test_existing_target_shows_error_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result="EXISTS\n")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "rename", "/sdcard/old.txt", "/sdcard/new.txt"])

        assert result.exit_code == 1
        assert "already exists" in result.output.lower()


class TestFilesDelete:
    def test_nothing_to_delete_for_empty_directory(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        client.shell.side_effect = ["DIR\n"]
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(search_module, "search_files", lambda c, s, p: [])

        result = CliRunner().invoke(main.cli, ["files", "delete", "/sdcard/EmptyDir"])

        assert result.exit_code == 0
        assert "Nothing to delete." in result.output

    def test_nothing_to_delete_for_nonexistent_path(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        client.shell.side_effect = ["MISSING\n"]
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "delete", "/sdcard/does-not-exist.txt"])

        assert result.exit_code == 0
        assert "Nothing to delete." in result.output

    def test_confirm_deletes_and_reports_result(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        client.shell.side_effect = ["100", "100", "", "NO\n"]
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "delete", "/sdcard/old.jpg"], input="YES DELETE\n"
        )

        assert result.exit_code == 0
        assert "This will permanently delete 1 file, 100 B." in result.output
        assert "Deleted 1 path(s), 100 B." in result.output

    def test_wrong_confirmation_aborts_without_deleting(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        client.shell.side_effect = ["100"]
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "delete", "/sdcard/old.jpg"], input="nope\n"
        )

        assert result.exit_code == 0
        assert "Aborted." in result.output
        assert client.shell.call_count == 1

    def test_yes_flag_skips_prompt(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        client.shell.side_effect = ["100", "100", "", "NO\n"]
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "delete", "/sdcard/old.jpg", "--yes"])

        assert result.exit_code == 0
        assert "Deleted 1 path(s), 100 B." in result.output

    def test_backup_dir_missing_files_blocks_deletion(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE)
        client.shell.side_effect = ["100", "100"]
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "delete", "/sdcard/old.jpg", "--backup-dir", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert "not backed up" in result.output
        assert client.shell.call_count == 2

    def test_remaining_after_delete_warns_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        client.shell.side_effect = ["100", "100", "", "YES\n"]
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "delete", "/sdcard/old.jpg"], input="YES DELETE\n"
        )

        assert result.exit_code == 1
        assert "could not be deleted" in result.output
