"""Tests for `droidbridge files search` (Module 7 CLI)."""

import csv as _csv
import os
import tempfile
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from droidbridge.cli.main import cli
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

    def test_type_alias_for_extension_filter(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["files", "search", "--type", "pdf"])

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


class TestSearchRegexCLI:
    def test_regex_flag_passed_to_search_files(self, runner):
        client = make_fake_client(
            READY_DEVICE,
            shell_result="/sdcard/photo.jpg\t1000\t1700000000.0\n",
        )
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(cli, ["files", "search", "--regex", ".*\\.jpg"])
        assert result.exit_code == 0
        assert "photo.jpg" in result.output

    def test_regex_and_name_mutually_exclusive(self, runner):
        client = make_fake_client(READY_DEVICE, shell_result="")
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(
                cli, ["files", "search", "--name", "foo", "--regex", ".*foo.*"]
            )
        assert result.exit_code == 1
        assert "mutually exclusive" in result.output.lower()


class TestSearchMimeCLI:
    def test_mime_expands_to_extensions(self, runner):
        client = make_fake_client(
            READY_DEVICE,
            shell_result="/sdcard/img.jpg\t500\t1700000000.0\n",
        )
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(cli, ["files", "search", "--mime", "image"])
        assert result.exit_code == 0
        assert "img.jpg" in result.output

    def test_unknown_mime_exits_1(self, runner):
        client = make_fake_client(READY_DEVICE, shell_result="")
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(cli, ["files", "search", "--mime", "font"])
        assert result.exit_code == 1
        assert "Unknown MIME category" in result.output

    def test_mime_and_ext_mutually_exclusive(self, runner):
        client = make_fake_client(READY_DEVICE, shell_result="")
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(
                cli, ["files", "search", "--ext", "jpg", "--mime", "image"]
            )
        assert result.exit_code == 1


class TestSearchLimitCLI:
    def test_limit_clips_results(self, runner):
        lines = "\n".join(
            f"/sdcard/file{i}.jpg\t100\t1700000000.0" for i in range(10)
        )
        client = make_fake_client(READY_DEVICE, shell_result=lines)
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(cli, ["files", "search", "--limit", "3"])
        assert result.exit_code == 0
        assert result.output.count("/sdcard/file") == 3


class TestSearchExtensionInOutput:
    def test_extension_column_present_in_output(self, runner):
        client = make_fake_client(
            READY_DEVICE,
            shell_result="/sdcard/photo.jpg\t1000\t1700000000.0\n",
        )
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(cli, ["files", "search"])
        assert result.exit_code == 0
        assert "jpg" in result.output

    def test_no_extension_shows_none_label(self, runner):
        client = make_fake_client(
            READY_DEVICE,
            shell_result="/sdcard/noext\t100\t1700000000.0\n",
        )
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(cli, ["files", "search"])
        assert result.exit_code == 0
        assert "(none)" in result.output


class TestSearchPullToCLI:
    def test_pull_to_executes_transfer(self, runner, tmp_path):
        search_output = "/sdcard/photo.jpg\t500000\t1700000000.0\n"
        client = make_fake_client(READY_DEVICE, shell_result=search_output)
        client.pull = MagicMock()
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(
                cli, ["files", "search", "--pull-to", str(tmp_path), "--no-verify"]
            )
        assert result.exit_code == 0, result.output
        assert client.pull.called

    def test_pull_to_skips_already_present(self, runner, tmp_path):
        dest = tmp_path / "photo.jpg"
        dest.write_bytes(b"x" * 500000)
        search_output = "/sdcard/photo.jpg\t500000\t1700000000.0\n"
        client = make_fake_client(READY_DEVICE, shell_result=search_output)
        client.pull = MagicMock()
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(cli, ["files", "search", "--pull-to", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert not client.pull.called
        assert "already present" in result.output

    def test_pull_to_creates_dest_dir(self, runner, tmp_path):
        new_dir = tmp_path / "new_subdir"
        assert not new_dir.exists()
        search_output = "/sdcard/file.jpg\t100\t1700000000.0\n"
        client = make_fake_client(READY_DEVICE, shell_result=search_output)
        client.pull = MagicMock()
        with patch("droidbridge.cli.main._build_client", return_value=client):
            runner.invoke(cli, ["files", "search", "--pull-to", str(new_dir)])
        assert new_dir.exists()


class TestSearchExportCLI:
    def test_output_csv_writes_file(self, runner):
        client = make_fake_client(READY_DEVICE)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            with patch("droidbridge.cli.main._build_client", return_value=client):
                result = runner.invoke(
                    cli, ["files", "search", "--output", path, "--format", "csv"]
                )
            assert result.exit_code == 0, result.output
            assert "exported" in result.output.lower()
            with open(path, newline="") as f:
                rows = list(_csv.reader(f))
            assert rows[0] == ["path", "size", "date", "extension"]
            assert rows[1][0] == "/sdcard/DCIM/Bills/Bills-05-08-2023_10_56.png"
        finally:
            os.unlink(path)

    def test_output_txt_writes_file(self, runner):
        client = make_fake_client(READY_DEVICE)
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            path = tmp.name
        try:
            with patch("droidbridge.cli.main._build_client", return_value=client):
                result = runner.invoke(
                    cli, ["files", "search", "--output", path, "--format", "txt"]
                )
            assert result.exit_code == 0, result.output
            with open(path) as f:
                content = f.read()
            assert "Bills-11-07-2023_12_50.png" in content
        finally:
            os.unlink(path)

    def test_output_without_format_exits_1(self, runner):
        client = make_fake_client(READY_DEVICE)
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(
                cli, ["files", "search", "--output", "/tmp/out_test.csv"]
            )
        assert result.exit_code == 1
        assert "--format" in result.output

    def test_format_without_output_exits_1(self, runner):
        client = make_fake_client(READY_DEVICE)
        with patch("droidbridge.cli.main._build_client", return_value=client):
            result = runner.invoke(cli, ["files", "search", "--format", "csv"])
        assert result.exit_code == 1
        assert "--output" in result.output
