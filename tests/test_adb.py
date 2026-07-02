# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.core.adb - the ADB wrapper."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from droidbridge.core import adb


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=["adb"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestFindAdbBinary:
    def test_finds_bundled_linux_binary(self, tmp_path):
        resources_dir = tmp_path / "resources"
        bundled_dir = resources_dir / "platform-tools-linux"
        bundled_dir.mkdir(parents=True)
        adb_bin = bundled_dir / "adb"
        adb_bin.write_text("#!/bin/sh\n")
        adb_bin.chmod(0o755)

        found = adb.find_adb_binary(system="Linux", resources_dir=resources_dir)

        assert found == str(adb_bin)

    def test_finds_bundled_windows_binary(self, tmp_path):
        resources_dir = tmp_path / "resources"
        bundled_dir = resources_dir / "platform-tools-windows"
        bundled_dir.mkdir(parents=True)
        adb_bin = bundled_dir / "adb.exe"
        adb_bin.write_text("")

        found = adb.find_adb_binary(system="Windows", resources_dir=resources_dir)

        assert found == str(adb_bin)

    def test_falls_back_to_path_when_no_bundled_binary(self, tmp_path, monkeypatch):
        resources_dir = tmp_path / "resources"  # does not exist

        monkeypatch.setattr(adb.shutil, "which", lambda name: "/usr/bin/adb")

        found = adb.find_adb_binary(system="Linux", resources_dir=resources_dir)

        assert found == "/usr/bin/adb"

    def test_raises_when_no_adb_available_anywhere(self, tmp_path, monkeypatch):
        resources_dir = tmp_path / "resources"  # does not exist

        monkeypatch.setattr(adb.shutil, "which", lambda name: None)

        try:
            adb.find_adb_binary(system="Linux", resources_dir=resources_dir)
            assert False, "expected AdbNotFoundError"
        except adb.AdbNotFoundError:
            pass


class TestAdbClientInit:
    def test_uses_provided_adb_path(self):
        client = adb.AdbClient(adb_path="/custom/adb")

        assert client.adb_path == "/custom/adb"

    def test_uses_found_adb_binary_by_default(self, monkeypatch):
        monkeypatch.setattr(adb, "find_adb_binary", lambda: "/found/adb")

        client = adb.AdbClient()

        assert client.adb_path == "/found/adb"


class TestDevices:
    def test_returns_empty_list_when_no_devices(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="List of devices attached\n\n")

            result = client.devices()

        assert result == []

    def test_parses_ready_device_with_info(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        stdout = (
            "List of devices attached\n"
            "ABC123XYZ      device usb:1-1 product:redfin model:Pixel_5 "
            "device:redfin transport_id:3\n\n"
        )
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout=stdout)

            result = client.devices()

        assert len(result) == 1
        device = result[0]
        assert device.serial == "ABC123XYZ"
        assert device.state == "device"
        assert device.product == "redfin"
        assert device.model == "Pixel_5"
        assert device.device == "redfin"
        assert device.transport_id == "3"
        assert device.is_ready is True

    def test_parses_unauthorized_and_offline_devices(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        stdout = (
            "List of devices attached\n"
            "AAA111      unauthorized usb:1-1\n"
            "BBB222      offline\n\n"
        )
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout=stdout)

            result = client.devices()

        assert [d.serial for d in result] == ["AAA111", "BBB222"]
        assert [d.state for d in result] == ["unauthorized", "offline"]
        assert all(not d.is_ready for d in result)

    def test_calls_devices_dash_l(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="List of devices attached\n\n")

            client.devices()

        args, kwargs = mock_run.call_args
        assert args[0] == ["/fake/adb", "devices", "-l"]


class TestRunErrorHandling:
    def test_raises_adb_command_error_on_nonzero_exit(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(
                stdout="", stderr="error: no devices/emulators found", returncode=1
            )

            with pytest.raises(adb.AdbCommandError) as exc_info:
                client.shell("SERIAL", "echo hi")

        assert exc_info.value.returncode == 1
        assert "no devices/emulators found" in str(exc_info.value)

    def test_raises_adb_timeout_error_on_timeout(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["adb"], timeout=5)

            with pytest.raises(adb.AdbTimeoutError):
                client.shell("SERIAL", "echo hi")

    def test_raises_adb_not_found_error_when_binary_missing(self):
        client = adb.AdbClient(adb_path="/nonexistent/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(adb.AdbNotFoundError):
                client.shell("SERIAL", "echo hi")

    def test_run_does_not_forward_stdin_to_adb(self):
        """`adb shell` forwards inherited stdin to the device by default, which would
        eat input meant for an interactive CLI prompt (e.g. `whatsapp delete`'s
        'YES DELETE' confirmation). Pass stdin=DEVNULL so adb never consumes it."""
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed()

            client.shell("SERIAL", "echo hi")

        args, kwargs = mock_run.call_args
        assert kwargs["stdin"] == subprocess.DEVNULL


class TestServerManagement:
    def test_start_server(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed()

            client.start_server()

        args, kwargs = mock_run.call_args
        assert args[0] == ["/fake/adb", "start-server"]

    def test_kill_server(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed()

            client.kill_server()

        args, kwargs = mock_run.call_args
        assert args[0] == ["/fake/adb", "kill-server"]

    def test_restart_server_kills_then_starts(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed()

            client.restart_server()

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls == [
            ["/fake/adb", "kill-server"],
            ["/fake/adb", "start-server"],
        ]

    def test_get_state_returns_device_state(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="device\n")

            state = client.get_state("SERIAL")

        assert state == "device"
        args, kwargs = mock_run.call_args
        assert args[0] == ["/fake/adb", "-s", "SERIAL", "get-state"]

    def test_get_state_returns_not_found_for_missing_device(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(
                stderr="error: device 'SERIAL' not found", returncode=1
            )

            state = client.get_state("SERIAL")

        assert state == "not found"


class TestWaitForDevice:
    def test_calls_wait_for_device(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed()

            client.wait_for_device()

        args, kwargs = mock_run.call_args
        assert args[0] == ["/fake/adb", "wait-for-device"]
        assert kwargs["timeout"] is None

    def test_passes_serial_and_timeout(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed()

            client.wait_for_device(serial="SERIAL123", timeout=5)

        args, kwargs = mock_run.call_args
        assert args[0] == ["/fake/adb", "-s", "SERIAL123", "wait-for-device"]
        assert kwargs["timeout"] == 5

    def test_timeout_raises_adb_timeout_error(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["adb", "wait-for-device"], timeout=5
            )

            with pytest.raises(adb.AdbTimeoutError):
                client.wait_for_device(timeout=5)


class TestShell:
    def test_shell_with_string_command(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="hi\n")

            result = client.shell("SERIAL", "echo hi")

        args, _ = mock_run.call_args
        assert args[0] == ["/fake/adb", "-s", "SERIAL", "shell", "echo hi"]
        assert result == "hi\n"

    def test_shell_with_list_command(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="ok\n")

            client.shell("SERIAL", ["ls", "-la", "/sdcard"])

        args, _ = mock_run.call_args
        assert args[0] == ["/fake/adb", "-s", "SERIAL", "shell", "ls", "-la", "/sdcard"]

    def test_shell_uses_default_timeout_when_not_specified(self):
        client = adb.AdbClient(adb_path="/fake/adb", default_timeout=15)
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="ok")

            client.shell("SERIAL", "echo hi")

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 15

    def test_shell_uses_explicit_timeout_when_specified(self):
        client = adb.AdbClient(adb_path="/fake/adb", default_timeout=15)
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="ok")

            client.shell("SERIAL", "echo hi", timeout=5)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 5

    def test_shell_does_not_raise_on_non_utf8_output(self, tmp_path):
        """Real device filenames can contain bytes that aren't valid UTF-8 (e.g. a
        stray 0xA0). `ls -la` output containing such a name must not crash the whole
        operation - invalid bytes are replaced rather than raising UnicodeDecodeError."""
        fake_adb = tmp_path / "adb"
        fake_adb.write_text("#!/bin/sh\nprintf 'foo\\240bar\\n'\n")
        fake_adb.chmod(0o755)
        client = adb.AdbClient(adb_path=str(fake_adb))

        result = client.shell("SERIAL", "ls -la /sdcard")

        assert "foo" in result and "bar" in result
        assert "�" in result


class TestPull:
    def test_pull_calls_correct_command_with_no_default_timeout(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="1 file pulled")

            result = client.pull("SERIAL", "/sdcard/DCIM/photo.jpg", "/local/photo.jpg")

        args, kwargs = mock_run.call_args
        assert args[0] == [
            "/fake/adb", "-s", "SERIAL", "pull",
            "/sdcard/DCIM/photo.jpg", "/local/photo.jpg",
        ]
        assert kwargs["timeout"] is None
        assert result.stdout == "1 file pulled"

    def test_pull_raises_on_failure(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(
                stderr="remote object '/sdcard/missing' does not exist", returncode=1
            )

            with pytest.raises(adb.AdbCommandError):
                client.pull("SERIAL", "/sdcard/missing", "/local/dest")

    def test_pull_with_explicit_timeout(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed()

            client.pull("SERIAL", "/sdcard/DCIM", "/local/dest", timeout=120)

        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 120


class TestPush:
    def test_push_calls_correct_command_with_no_default_timeout(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="1 file pushed")

            result = client.push("SERIAL", "/local/photo.jpg", "/sdcard/DCIM/photo.jpg")

        args, kwargs = mock_run.call_args
        assert args[0] == [
            "/fake/adb", "-s", "SERIAL", "push",
            "/local/photo.jpg", "/sdcard/DCIM/photo.jpg",
        ]
        assert kwargs["timeout"] is None
        assert result.stdout == "1 file pushed"

    def test_push_raises_on_failure(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(
                stderr="cannot stat '/local/missing': No such file or directory",
                returncode=1,
            )

            with pytest.raises(adb.AdbCommandError):
                client.push("SERIAL", "/local/missing", "/sdcard/dest")


class TestInstall:
    def test_single_apk_uses_install_with_r_flag(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="Success")

            client.install("SERIAL", "/local/app.apk")

        args, kwargs = mock_run.call_args
        assert args[0] == ["/fake/adb", "-s", "SERIAL", "install", "-r", "/local/app.apk"]
        assert kwargs["timeout"] is None

    def test_split_apks_uses_install_multiple(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="Success")

            client.install("SERIAL", ["/local/base.apk", "/local/split.apk"])

        args, kwargs = mock_run.call_args
        assert args[0] == [
            "/fake/adb", "-s", "SERIAL", "install-multiple", "-r",
            "/local/base.apk", "/local/split.apk",
        ]

    def test_allow_downgrade_adds_d_flag(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="Success")

            client.install("SERIAL", "/local/app.apk", allow_downgrade=True)

        args, _ = mock_run.call_args
        assert args[0] == ["/fake/adb", "-s", "SERIAL", "install", "-r", "-d", "/local/app.apk"]

    def test_reinstall_false_omits_r_flag(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(stdout="Success")

            client.install("SERIAL", "/local/app.apk", reinstall=False)

        args, _ = mock_run.call_args
        assert args[0] == ["/fake/adb", "-s", "SERIAL", "install", "/local/app.apk"]

    def test_install_raises_on_failure(self):
        client = adb.AdbClient(adb_path="/fake/adb")
        with patch.object(adb.subprocess, "run") as mock_run:
            mock_run.return_value = _completed(
                stderr="Failure [INSTALL_FAILED_VERSION_DOWNGRADE]", returncode=1
            )

            with pytest.raises(adb.AdbCommandError):
                client.install("SERIAL", "/local/app.apk")


class TestRealBundledAdb:
    """Sanity checks against the real bundled Linux adb binary (no device needed)."""

    def test_find_adb_binary_resolves_to_bundled_binary_on_linux(self):
        found = adb.find_adb_binary(system="Linux")

        assert found == str(adb.RESOURCES_DIR / "platform-tools-linux" / "adb")
        assert Path(found).is_file()

    def test_real_devices_call_returns_a_list(self):
        client = adb.AdbClient()

        result = client.devices()

        assert isinstance(result, list)
