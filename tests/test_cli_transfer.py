"""Tests for `droidbridge transfer pull/push` (Module 3 CLI)."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]

DIR_FIND_OUTPUT = (
    "/sdcard/Camera/photo1.jpg\t1000\t1700000000.0\n"
    "/sdcard/Camera/photo2.jpg\t2000\t1700000100.0\n"
)


@contextmanager
def _noop_inhibitor(*args, **kwargs):
    yield


def make_fake_client(devices, shell_side_effect=None):
    client = MagicMock()
    client.devices.return_value = devices
    if shell_side_effect is not None:
        client.shell.side_effect = shell_side_effect
    return client


class TestTransferPull:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_pulls_single_file_and_verifies(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])

        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        assert result.exit_code == 0
        assert "Pulling 1 file" in result.output
        assert "Verified: 1 file" in result.output
        assert (tmp_path / "photo.jpg").read_bytes() == b"x" * 1000

    def test_pulls_directory_and_verifies(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["DIR\n", DIR_FIND_OUTPUT])

        def fake_pull(serial, remote, local):
            size = 1000 if remote.endswith("photo1.jpg") else 2000
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * size)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/Camera", str(tmp_path)])

        assert result.exit_code == 0
        assert "Pulling 2 files" in result.output
        assert "Verified: 2 file" in result.output
        assert (tmp_path / "Camera" / "photo1.jpg").exists()
        assert (tmp_path / "Camera" / "photo2.jpg").exists()

    def test_already_present_files_are_skipped(self, monkeypatch, tmp_path):
        (tmp_path / "photo.jpg").write_bytes(b"x" * 1000)
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        assert result.exit_code == 0
        assert "Skipping 1 file" in result.output
        assert "Nothing to transfer." in result.output
        client.pull.assert_not_called()

    def test_verification_failure_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])
        # client.pull does nothing, so the destination file never appears.
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path)])

        assert result.exit_code == 1
        assert "Verification FAILED" in result.output

    def test_no_verify_flag_skips_verification(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=["1000"])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(
            main.cli, ["transfer", "pull", "/sdcard/photo.jpg", str(tmp_path), "--no-verify"]
        )

        assert result.exit_code == 0
        assert "Verified" not in result.output
        assert "Verification" not in result.output


class TestTransferPush:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_local_path_must_exist(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        missing = tmp_path / "does-not-exist.pdf"
        result = CliRunner().invoke(main.cli, ["transfer", "push", str(missing), "/sdcard/Download"])

        assert result.exit_code == 2

    def test_pushes_single_file_and_verifies(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_after_push = "/sdcard/Download/report.pdf\t100\t1700000000.0\n"
        client = make_fake_client(
            READY_DEVICE,
            shell_side_effect=["NO\n", "", "DIR\n", existing_after_push],
        )
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        assert result.exit_code == 0
        assert "Pushing 1 file" in result.output
        assert "Verified: 1 file" in result.output
        client.push.assert_called_once_with("SERIAL123", str(local_file), "/sdcard/Download/report.pdf")

    def test_already_present_files_are_skipped(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_output = "/sdcard/Download/report.pdf\t100\t1700000000.0\n"
        client = make_fake_client(READY_DEVICE, shell_side_effect=["DIR\n", existing_output])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        assert result.exit_code == 0
        assert "Skipping 1 file" in result.output
        assert "Nothing to transfer." in result.output
        client.push.assert_not_called()

    def test_conflict_skip_message(self, monkeypatch, tmp_path):
        local_file = tmp_path / "report.pdf"
        local_file.write_bytes(b"x" * 100)

        existing_output = "/sdcard/Download/report.pdf\t50\t1700000000.0\n"
        client = make_fake_client(READY_DEVICE, shell_side_effect=["DIR\n", existing_output])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["transfer", "push", str(local_file), "/sdcard/Download"])

        assert result.exit_code == 0
        assert "conflict" in result.output.lower()
        assert "Nothing to transfer." in result.output
