"""Tests for `droidbridge files browse` (Module 2 CLI)."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import AdbCommandError, Device
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
