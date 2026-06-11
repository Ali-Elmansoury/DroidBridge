"""Tests for `droidbridge whatsapp scan` (Module 4 CLI, analysis sub-phase)."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device


@contextmanager
def _noop_inhibitor(*args, **kwargs):
    yield

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]

WA_MEDIA = "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"
W4B_MEDIA = "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business/Media"

# detect_installs shell output: WhatsApp modern path present, all others absent.
DETECT_WA_ONLY = "1\n0\n0\n0\n"
# Both WhatsApp and WhatsApp Business present on the modern path.
DETECT_BOTH = "1\n0\n1\n0\n"
# Neither installed.
DETECT_NONE = "0\n0\n0\n0\n"

SCAN_OUTPUT = (
    f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg\t1000\t1672531200.0\n"
    f"{WA_MEDIA}/WhatsApp Images/Sent/IMG-20230102-WA0002.jpg\t2000\t1672617600.0\n"
)

W4B_SCAN_OUTPUT = f"{W4B_MEDIA}/WhatsApp Business Images/photo.jpg\t500\t1672531200.0\n"


def make_fake_client(devices, shell_side_effect=None):
    client = MagicMock()
    client.devices.return_value = devices
    if shell_side_effect is not None:
        client.shell.side_effect = shell_side_effect
    return client


class TestWhatsAppScan:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["whatsapp", "scan"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_no_whatsapp_installed_exits_nonzero(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "scan"])

        assert result.exit_code == 1
        assert "no whatsapp" in result.output.lower()

    def test_scans_and_prints_summary(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "scan"])

        assert result.exit_code == 0
        assert "WhatsApp (com.whatsapp)" in result.output
        assert "Images" in result.output
        assert "Received" in result.output
        assert "Sent" in result.output
        assert "2 files" in result.output  # TOTAL line

    def test_scans_both_apps_by_default(self, monkeypatch):
        client = make_fake_client(
            READY_DEVICE, shell_side_effect=[DETECT_BOTH, SCAN_OUTPUT, W4B_SCAN_OUTPUT]
        )
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "scan"])

        assert result.exit_code == 0
        assert "WhatsApp (com.whatsapp)" in result.output
        assert "WhatsApp Business (com.whatsapp.w4b)" in result.output

    def test_app_option_filters_to_business_only(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_BOTH, W4B_SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "scan", "--app", "business"])

        assert result.exit_code == 0
        assert "WhatsApp (com.whatsapp)" not in result.output
        assert "WhatsApp Business (com.whatsapp.w4b)" in result.output

    def test_no_media_found_message(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, ""])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "scan"])

        assert result.exit_code == 0
        assert "no media found" in result.output.lower()


WA_STATUSES = f"{WA_MEDIA}/.Statuses"
W4B_STATUSES = f"{W4B_MEDIA}/.Statuses"


class TestWhatsAppSaveStatus:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["whatsapp", "save-status", "--dest", str(tmp_path)])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_no_whatsapp_installed_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "save-status", "--dest", str(tmp_path)])

        assert result.exit_code == 1
        assert "no whatsapp" in result.output.lower()

    def test_saves_current_statuses_to_per_app_subfolders(self, monkeypatch, tmp_path):
        shell_outputs = [
            DETECT_BOTH,
            "1\n",
            f"{WA_STATUSES}/status1.jpg\t1000\t1672531200.0\n",
            "1\n",
            f"{W4B_STATUSES}/status2.mp4\t2000\t1672531300.0\n",
        ]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)

        def fake_pull(serial, remote, local):
            size = 1000 if remote.endswith("status1.jpg") else 2000
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * size)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "SleepInhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["whatsapp", "save-status", "--dest", str(tmp_path)])

        assert result.exit_code == 0
        assert "Pulling 2 files" in result.output
        assert "Verified: 2 file" in result.output
        assert (tmp_path / "WhatsApp" / "Statuses" / "status1.jpg").exists()
        assert (tmp_path / "WhatsApp Business" / "Statuses" / "status2.mp4").exists()

    def test_app_option_filters_to_business_only(self, monkeypatch, tmp_path):
        shell_outputs = [DETECT_BOTH, "1\n", f"{W4B_STATUSES}/status2.mp4\t2000\t1672531300.0\n"]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)

        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 2000)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "SleepInhibitor", _noop_inhibitor)

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "save-status", "--dest", str(tmp_path), "--app", "business"]
        )

        assert result.exit_code == 0
        assert (tmp_path / "WhatsApp Business" / "Statuses" / "status2.mp4").exists()
        assert not (tmp_path / "WhatsApp" / "Statuses").exists()

    def test_no_statuses_found_message(self, monkeypatch, tmp_path):
        shell_outputs = [DETECT_WA_ONLY, "0\n"]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "SleepInhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["whatsapp", "save-status", "--dest", str(tmp_path)])

        assert result.exit_code == 0
        assert "nothing to transfer" in result.output.lower()
