"""Tests for `droidbridge files search` (Module 7 CLI)."""

from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device
from droidbridge.modules import search as search_module
from tests.test_search import FIND_OUTPUT

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]


def make_fake_client(devices, shell_result=FIND_OUTPUT):
    client = MagicMock()
    client.devices.return_value = devices
    client.shell.return_value = shell_result
    return client


class TestFilesSearch:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["files", "search"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_default_path_is_sdcard(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result="")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        CliRunner().invoke(main.cli, ["files", "search"])

        cmd = client.shell.call_args[0][1]
        assert cmd.startswith("find -L /sdcard -type f")

    def test_lists_results_with_size_and_path(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "search", "/sdcard"])

        assert result.exit_code == 0
        assert "/sdcard/Download/report.pdf" in result.output
        assert "50.0 MB" in result.output

    def test_name_filter_wraps_partial_match(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result="")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        CliRunner().invoke(main.cli, ["files", "search", "--name", "report"])

        cmd = client.shell.call_args[0][1]
        assert "-iname '*report*'" in cmd

    def test_name_filter_with_wildcard_passthrough(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result="")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        CliRunner().invoke(main.cli, ["files", "search", "--name", "*.png"])

        cmd = client.shell.call_args[0][1]
        assert "-iname '*.png'" in cmd

    def test_extension_filter(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "search", "--ext", "pdf"])

        assert "report.pdf" in result.output
        assert ".png" not in result.output

    def test_size_filters_with_human_units(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "search", "--min-size", "1MB"]
        )

        assert "report.pdf" in result.output
        assert "Bills" not in result.output

    def test_date_filters(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "search", "--after", "2022-01-01", "--before", "2024-01-01"]
        )

        # report.pdf (2020) and noext (2017) fall outside the 2022-2024 window
        assert "report.pdf" not in result.output
        assert "noext" not in result.output
        assert "Bills" in result.output

    def test_combined_type_date_and_size_filters(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli,
            [
                "files", "search",
                "--ext", "png",
                "--after", "2023-08-01",
                "--min-size", "160KB",
            ],
        )

        lines = [l for l in result.output.splitlines() if l.strip()]
        assert len(lines) == 1
        assert "Bills-05-08-2023_10_56.png" in lines[0]

    def test_preset_photos(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "search", "--preset", "photos"])

        assert "Bills-11-07-2023_12_50.png" in result.output
        assert "report.pdf" not in result.output
        assert "noext" not in result.output

    def test_preset_whatsapp_overrides_root(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result="")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        CliRunner().invoke(main.cli, ["files", "search", "--preset", "whatsapp"])

        cmd = client.shell.call_args[0][1]
        assert cmd.startswith(f"find -L {search_module.WHATSAPP_MEDIA_PATH} -type f")

    def test_sort_by_size_reverse(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["files", "search", "--sort", "size", "--reverse"]
        )

        lines = [l for l in result.output.splitlines() if l.strip()]
        assert "report.pdf" in lines[0]

    def test_no_results_message(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_result="")
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "search"])

        assert result.exit_code == 0
        assert "no files found" in result.output.lower()
