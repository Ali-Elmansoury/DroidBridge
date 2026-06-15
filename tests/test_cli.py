"""Tests for droidbridge.cli.main - the Click CLI entry point."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import AdbNotFoundError, Device
from tests.test_device import BATTERY_OUTPUT_CHARGING, DF_OUTPUT, PROP_VALUES


def make_fake_client(devices):
    client = MagicMock()
    client.devices.return_value = devices

    def fake_shell(serial, command, timeout=None):
        if command[0] == "getprop":
            return PROP_VALUES[command[1]]
        if command[:2] == ["dumpsys", "battery"]:
            return BATTERY_OUTPUT_CHARGING
        if command[0] == "df":
            return DF_OUTPUT
        if command[0] == "cat":
            return ""
        raise AssertionError(f"Unexpected shell command: {command}")

    client.shell.side_effect = fake_shell
    return client


class TestDeviceConnect:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["device", "connect"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_ready_device_shows_connected_and_exits_zero(self, monkeypatch):
        client = make_fake_client([Device(serial="SERIAL123", state="device", model="Pixel_7")])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["device", "connect"])

        assert result.exit_code == 0
        assert "SERIAL123" in result.output
        assert "connected" in result.output.lower()

    def test_unauthorized_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([Device(serial="SERIAL123", state="unauthorized")])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["device", "connect"])

        assert result.exit_code == 1
        assert "allow" in result.output.lower()

    def test_adb_not_found_shows_error(self, monkeypatch):
        def raise_not_found():
            raise AdbNotFoundError("adb not found")

        monkeypatch.setattr(main, "_build_client", raise_not_found)

        result = CliRunner().invoke(main.cli, ["device", "connect"])

        assert result.exit_code == 1
        assert "adb not found" in result.output.lower()


class TestDeviceInfo:
    def test_no_ready_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["device", "info"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_single_device_prints_info(self, monkeypatch):
        client = make_fake_client([Device(serial="SERIAL123", state="device", model="Pixel_7")])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["device", "info"])

        assert result.exit_code == 0
        assert "Pixel 7" in result.output
        assert "Google" in result.output
        assert "14" in result.output
        assert "85% (charging)" in result.output
        assert "GB" in result.output

    def test_multiple_devices_without_serial_lists_choices(self, monkeypatch):
        client = make_fake_client(
            [
                Device(serial="AAA", state="device", model="Pixel_7"),
                Device(serial="BBB", state="device", model="Pixel_6"),
            ]
        )
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["device", "info"])

        assert result.exit_code == 1
        assert "AAA" in result.output
        assert "BBB" in result.output
        assert "--serial" in result.output

    def test_explicit_serial_selects_device(self, monkeypatch):
        client = make_fake_client(
            [
                Device(serial="AAA", state="device", model="Pixel_7"),
                Device(serial="BBB", state="device", model="Pixel_6"),
            ]
        )
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["device", "info", "--serial", "AAA"])

        assert result.exit_code == 0
        assert "Pixel 7" in result.output

    def test_unknown_serial_errors(self, monkeypatch):
        client = make_fake_client([Device(serial="AAA", state="device", model="Pixel_7")])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["device", "info", "--serial", "ZZZ"])

        assert result.exit_code == 1
        assert "ZZZ" in result.output
