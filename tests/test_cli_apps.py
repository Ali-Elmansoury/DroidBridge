# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for `droidbridge apps` (Module 8 CLI)."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import AdbCommandError, Device
from tests.test_apps import PACKAGE_DUMP_OUTPUT, PM_LIST_ALL_OUTPUT, PM_LIST_DISABLED_OUTPUT
from tests.test_storage import DISKSTATS_OUTPUT, PM_LIST_SYSTEM_OUTPUT

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]


def make_fake_client(devices, shell):
    client = MagicMock()
    client.devices.return_value = devices
    if callable(shell):
        client.shell.side_effect = shell
    else:
        client.shell.return_value = shell
    return client


def _apps_fake_shell(serial, command, timeout=None):
    if command[:2] == ["dumpsys", "diskstats"]:
        return DISKSTATS_OUTPUT
    if command[:3] == ["dumpsys", "package", "packages"]:
        return PACKAGE_DUMP_OUTPUT
    if command == ["pm", "list", "packages"]:
        return PM_LIST_ALL_OUTPUT
    if command[:4] == ["pm", "list", "packages", "-s"]:
        return PM_LIST_SYSTEM_OUTPUT
    if command[:4] == ["pm", "list", "packages", "-d"]:
        return PM_LIST_DISABLED_OUTPUT
    raise AssertionError(command)


class TestAppsList:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "list"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_lists_apps_by_total_size_descending(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "list"])

        assert result.exit_code == 0
        lines = [line for line in result.output.splitlines() if line.strip()]
        assert lines[0].startswith("com.whatsapp")
        assert "2.26.17.72" in result.output
        assert "2020-09-12" in result.output

    def test_system_filter_shows_disabled_marker(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "list", "--system"])

        assert "com.android.chrome" in result.output
        assert "com.whatsapp" not in result.output
        assert "[disabled]" in result.output

    def test_user_filter(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "list", "--user"])

        assert "com.whatsapp" in result.output
        assert "com.android.chrome" not in result.output

    def test_sort_by_name_ascending(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "list", "--sort", "name", "--no-reverse"])

        lines = [line for line in result.output.splitlines() if line.strip()]
        assert lines[0].startswith("com.android.chrome")
        assert lines[1].startswith("com.whatsapp")


class TestAppsTrimCache:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "trim-cache"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_trims_caches_using_estimated_total(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "trim-caches"]:
                calls.append(command)
                return ""
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "trim-cache"])

        assert result.exit_code == 0
        # Cache Sizes from DISKSTATS_OUTPUT: 33968128 + 373264384 = 407232512
        assert calls == [["pm", "trim-caches", "407232512"]]
        assert "388.4 MB" in result.output

    def test_custom_target(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "trim-caches"]:
                calls.append(command)
                return ""
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "trim-cache", "--target", "100MB"])

        assert result.exit_code == 0
        assert calls == [["pm", "trim-caches", str(100 * 1024 * 1024)]]


class TestAppsReset:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "reset", "com.whatsapp"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_unknown_package_errors(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "reset", "com.unknown"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_blocks_system_apps(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "reset", "com.android.chrome"])

        assert result.exit_code == 1
        assert "system app" in result.output.lower()

    def test_aborts_without_yes_delete(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "reset", "com.whatsapp"], input="nope\n")

        assert "aborted" in result.output.lower()
        assert all(call.args[1][:2] != ["pm", "clear"] for call in client.shell.call_args_list)

    def test_clears_data_on_confirmation(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "clear"]:
                calls.append(command)
                return "Success"
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "reset", "com.whatsapp"], input="YES DELETE\n")

        assert result.exit_code == 0
        assert calls == [["pm", "clear", "com.whatsapp"]]


class TestAppsUninstall:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "uninstall", "com.whatsapp"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_unknown_package_errors(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "uninstall", "com.unknown"], input="y\n")

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_blocks_system_apps(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "uninstall", "com.android.chrome"], input="y\n")

        assert result.exit_code == 1
        assert "system app" in result.output.lower()

    def test_aborts_without_confirmation(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "uninstall", "com.whatsapp"], input="n\n")

        assert "aborted" in result.output.lower()
        assert all(call.args[1][:2] != ["pm", "uninstall"] for call in client.shell.call_args_list)

    def test_uninstalls_on_confirmation(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "uninstall"]:
                calls.append(command)
                return "Success"
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "uninstall", "com.whatsapp"], input="y\n")

        assert result.exit_code == 0
        assert calls == [["pm", "uninstall", "com.whatsapp"]]

    def test_keep_data_flag_with_yes(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "uninstall"]:
                calls.append(command)
                return "Success"
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "uninstall", "com.whatsapp", "--keep-data", "--yes"])

        assert result.exit_code == 0
        assert calls == [["pm", "uninstall", "-k", "com.whatsapp"]]

    def test_batch_uninstall_blocks_if_any_target_is_system(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "uninstall"]:
                calls.append(command)
                return "Success"
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["apps", "uninstall", "com.whatsapp", "com.android.chrome", "--yes"]
        )

        assert result.exit_code == 1
        assert calls == []


class TestAppsExtractApk:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "extract-apk", "com.whatsapp", "--dest", str(tmp_path)])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_unknown_package_errors(self, monkeypatch, tmp_path):
        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "path"]:
                raise AdbCommandError(command, 1, "", "")
            raise AssertionError(command)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "extract-apk", "com.unknown", "--dest", str(tmp_path)])

        assert result.exit_code == 1
        assert "no apk found" in result.output.lower()

    def test_extracts_base_and_split_apks(self, monkeypatch, tmp_path):
        pulled = []

        def fake_shell(serial, command, timeout=None):
            if command == ["pm", "path", "com.whatsapp"]:
                return "package:/data/app/x/base.apk\npackage:/data/app/x/split_config.arm64_v8a.apk\n"
            if isinstance(command, str) and command.startswith("find -L"):
                return "1000"
            raise AssertionError(command)

        client = make_fake_client(READY_DEVICE, fake_shell)
        client.pull.side_effect = lambda serial, remote, local: pulled.append((remote, local))
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "extract-apk", "com.whatsapp", "--dest", str(tmp_path)])

        assert result.exit_code == 0
        assert pulled == [
            ("/data/app/x/base.apk", str(tmp_path / "base.apk")),
            ("/data/app/x/split_config.arm64_v8a.apk", str(tmp_path / "split_config.arm64_v8a.apk")),
        ]
        assert "2 APK file(s)" in result.output


class TestAppsDisable:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "disable", "com.android.chrome"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_unknown_package_errors(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "disable", "com.unknown"], input="y\n")

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_already_disabled_short_circuits(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        # com.android.chrome is in PM_LIST_DISABLED_OUTPUT
        result = CliRunner().invoke(main.cli, ["apps", "disable", "com.android.chrome"], input="y\n")

        assert result.exit_code == 0
        assert "already disabled" in result.output.lower()
        assert all(call.args[1][:2] != ["pm", "disable-user"] for call in client.shell.call_args_list)

    def test_aborts_without_confirmation(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "disable", "com.whatsapp"], input="n\n")

        assert "aborted" in result.output.lower()
        assert all(call.args[1][:2] != ["pm", "disable-user"] for call in client.shell.call_args_list)

    def test_disables_on_confirmation(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "disable-user"]:
                calls.append(command)
                return ""
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "disable", "com.whatsapp"], input="y\n")

        assert result.exit_code == 0
        assert calls == [["pm", "disable-user", "--user", "0", "com.whatsapp"]]


class TestAppsClearCache:
    def test_no_flags_gives_usage_error(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "clear-cache"])

        assert result.exit_code != 0
        assert "error" in result.output.lower() or "usage" in result.output.lower()

    def test_all_flag_calls_trim_caches_with_large_number(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "trim-caches"]:
                calls.append(command)
                return ""
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "clear-cache", "--all"])

        assert result.exit_code == 0
        assert len(calls) == 1
        assert int(calls[0][2]) > 1_000_000_000

    def test_target_flag_calls_trim_caches_with_exact_bytes(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "trim-caches"]:
                calls.append(command)
                return ""
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "clear-cache", "--target", "500000000"])

        assert result.exit_code == 0
        assert calls == [["pm", "trim-caches", "500000000"]]

    def test_all_flag_prints_confirmation_message(self, monkeypatch):
        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "trim-caches"]:
                return ""
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "clear-cache", "--all"])

        assert result.exit_code == 0
        assert "cache trim requested" in result.output.lower()

    def test_all_and_target_together_gives_error(self, monkeypatch):
        """--all and --target are mutually exclusive."""
        from unittest.mock import patch

        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.apps_module.trim_caches"):
            result = CliRunner().invoke(main.cli, ["apps", "clear-cache", "--all", "--target", "500000000"])
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output.lower() or "error" in result.output.lower()

    def test_target_accepts_human_readable_size(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "trim-caches"]:
                calls.append(command)
                return ""
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "clear-cache", "--target", "500MB"])

        assert result.exit_code == 0
        assert calls == [["pm", "trim-caches", "524288000"]]

    def test_target_invalid_size_exits_nonzero(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "clear-cache", "--target", "notanumber"])

        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "error" in result.output.lower()

    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        """No-device case: AdbError propagates as guidance and non-zero exit."""
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "clear-cache", "--all"])

        assert result.exit_code != 0
        assert "usb debugging" in result.output.lower()


class TestAppsEnable:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([], "")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "enable", "com.android.chrome"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_unknown_package_errors(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "enable", "com.unknown"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_already_enabled_short_circuits(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, _apps_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "enable", "com.whatsapp"])

        assert result.exit_code == 0
        assert "already enabled" in result.output.lower()
        assert all(call.args[1][:2] != ["pm", "enable"] for call in client.shell.call_args_list)

    def test_enables(self, monkeypatch):
        calls = []

        def fake_shell(serial, command, timeout=None):
            if command[:2] == ["pm", "enable"]:
                calls.append(command)
                return ""
            return _apps_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["apps", "enable", "com.android.chrome"])

        assert result.exit_code == 0
        assert calls == [["pm", "enable", "--user", "0", "com.android.chrome"]]
