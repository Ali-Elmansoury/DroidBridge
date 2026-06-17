"""Tests for `droidbridge whatsapp scan` (Module 4 CLI, analysis sub-phase)."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.cli.main import cli
from droidbridge.core.adb import Device
from droidbridge.modules.whatsapp import MediaFile, WhatsAppInstall
from droidbridge.modules.transfer import (
    ACTION_COPY,
    TransferItem,
    TransferPlan,
    TransferProgress,
    VerificationResult,
)
from tests.test_device import DF_OUTPUT


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

    def test_by_year_groups_by_year_month(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "scan", "--by", "year"])

        assert result.exit_code == 0
        assert "2023-01" in result.output
        assert "2 files" in result.output

    def test_by_extension_groups_by_file_extension(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "scan", "--by", "extension"])

        assert result.exit_code == 0
        assert "jpg" in result.output
        assert "2 files" in result.output


class TestWhatsAppAnalyze:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["whatsapp", "analyze"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_no_whatsapp_installed_exits_nonzero(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "analyze"])

        assert result.exit_code == 1
        assert "no whatsapp" in result.output.lower()

    def test_default_cutoff_splits_pre_and_post(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "analyze"])

        assert result.exit_code == 0
        assert "Cutoff date: 2024-09-01" in result.output
        assert "Pre-cutoff" in result.output
        assert "Post-cutoff" in result.output
        assert "2 files" in result.output  # both SCAN_OUTPUT files are pre-2024-09-01
        assert "Deletable" in result.output

    def test_custom_cutoff_moves_files_to_post(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "analyze", "--cutoff", "2020-01-01"])

        assert result.exit_code == 0
        assert "Cutoff date: 2020-01-01" in result.output
        assert "Deletable (pre-cutoff): 0 files" in result.output

    def test_no_media_found_message(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, ""])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "analyze"])

        assert result.exit_code == 0
        assert "no media found" in result.output.lower()

    def test_invalid_cutoff_format_exits_nonzero(self, monkeypatch):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "analyze", "--cutoff", "not-a-date"])

        assert result.exit_code != 0


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
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

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
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

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
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["whatsapp", "save-status", "--dest", str(tmp_path)])

        assert result.exit_code == 0
        assert "nothing to transfer" in result.output.lower()


BACKUP_SCAN_OUTPUT = (
    f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg\t1000\t1672531200.0\n"
    f"{WA_MEDIA}/WhatsApp Voice Notes/PTT-20230102-WA0001.opus\t2000\t1672531200.0\n"
)


class TestWhatsAppBackup:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["whatsapp", "backup", "--dest", str(tmp_path)])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_no_whatsapp_installed_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "backup", "--dest", str(tmp_path)])

        assert result.exit_code == 1
        assert "no whatsapp" in result.output.lower()

    def test_full_backup_pulls_all_media(self, monkeypatch, tmp_path):
        shell_outputs = [DETECT_WA_ONLY, SCAN_OUTPUT]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)

        def fake_pull(serial, remote, local):
            size = 1000 if remote.endswith("WA0001.jpg") else 2000
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * size)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["whatsapp", "backup", "--dest", str(tmp_path)])

        assert result.exit_code == 0
        assert "Pulling 2 files" in result.output
        assert "Verified: 2 file" in result.output
        assert (tmp_path / "WhatsApp" / "Media" / "WhatsApp Images" / "IMG-20230101-WA0001.jpg").exists()
        assert (
            tmp_path / "WhatsApp" / "Media" / "WhatsApp Images" / "Sent" / "IMG-20230102-WA0002.jpg"
        ).exists()

    def test_selective_backup_by_type(self, monkeypatch, tmp_path):
        shell_outputs = [DETECT_WA_ONLY, BACKUP_SCAN_OUTPUT]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)

        def fake_pull(serial, remote, local):
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * 1000)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "backup", "--dest", str(tmp_path), "--type", "images"]
        )

        assert result.exit_code == 0
        assert "Pulling 1 file" in result.output
        assert (tmp_path / "WhatsApp" / "Media" / "WhatsApp Images" / "IMG-20230101-WA0001.jpg").exists()
        assert not (tmp_path / "WhatsApp" / "Media" / "WhatsApp Voice Notes").exists()

    def test_invalid_type_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "backup", "--dest", str(tmp_path), "--type", "not-a-type"]
        )

        assert result.exit_code != 0
        assert "invalid --type" in result.output.lower()

    def test_no_media_found_message(self, monkeypatch, tmp_path):
        shell_outputs = [DETECT_WA_ONLY, ""]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["whatsapp", "backup", "--dest", str(tmp_path)])

        assert result.exit_code == 0
        assert "nothing to transfer" in result.output.lower()


class TestWhatsAppRestore:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["whatsapp", "restore", "--src", str(tmp_path)])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_no_whatsapp_installed_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "restore", "--src", str(tmp_path)])

        assert result.exit_code == 1
        assert "no whatsapp" in result.output.lower()

    def test_restores_backup_folder_to_media_path(self, monkeypatch, tmp_path):
        media_dir = tmp_path / "WhatsApp" / "Media" / "WhatsApp Images"
        media_dir.mkdir(parents=True)
        (media_dir / "IMG-20230101-WA0001.jpg").write_bytes(b"x" * 1000)

        shell_outputs = [
            DETECT_WA_ONLY,
            "NO\n",  # plan_push: _remote_manifest -> _remote_dir_exists (media path doesn't exist yet)
            "",  # execute_plan: mkdir -p remote_dir
            "DIR\n",  # verify_push: _remote_manifest -> _remote_dir_exists
            f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg\t1000\t1672531200.0\n",  # verify_push: search_files
        ]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["whatsapp", "restore", "--src", str(tmp_path)])

        assert result.exit_code == 0
        assert "Pushing 1 file" in result.output
        assert "Verified: 1 file" in result.output
        client.push.assert_called_once_with(
            "SERIAL123",
            str(media_dir / "IMG-20230101-WA0001.jpg"),
            f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg",
        )

    def test_no_backup_found_for_app_message(self, monkeypatch, tmp_path):
        shell_outputs = [DETECT_WA_ONLY]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["whatsapp", "restore", "--src", str(tmp_path)])

        assert result.exit_code == 0
        assert "no backup found" in result.output.lower()


class TestWhatsAppOrganize:
    def test_organizes_voice_notes_by_date_unsectioned(self, tmp_path):
        src = tmp_path / "WhatsApp Voice Notes"
        src.mkdir()
        (src / "PTT-20230115-WA0001.opus").write_bytes(b"x")

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "organize", "--src", str(src), "--type", "voice_notes"]
        )

        assert result.exit_code == 0
        assert "Organizing 1 file" in result.output
        organized = tmp_path / "WhatsApp_Voice_Notes_Organized"
        assert (organized / "2023" / "01-Jan" / "PTT-20230115-WA0001.opus").exists()

    def test_organizes_images_by_section_then_date(self, tmp_path):
        src = tmp_path / "WhatsApp Images"
        sent = src / "Sent"
        sent.mkdir(parents=True)
        (src / "IMG-20230101-WA0001.jpg").write_bytes(b"x")
        (sent / "IMG-20230102-WA0002.jpg").write_bytes(b"y")

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "organize", "--src", str(src), "--type", "images"]
        )

        assert result.exit_code == 0
        organized = tmp_path / "WhatsApp_Images_Organized"
        assert (organized / "Received" / "2023" / "01-Jan" / "IMG-20230101-WA0001.jpg").exists()
        assert (organized / "Sent" / "2023" / "01-Jan" / "IMG-20230102-WA0002.jpg").exists()

    def test_organizes_documents_by_category_then_date(self, tmp_path):
        src = tmp_path / "WhatsApp Documents"
        src.mkdir()
        (src / "DOC-20230101-WA0001.pdf").write_bytes(b"x")

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "organize", "--src", str(src), "--type", "documents"]
        )

        assert result.exit_code == 0
        organized = tmp_path / "WhatsApp_Documents_Organized"
        assert (organized / "Received" / "PDFs" / "2023" / "01-Jan" / "DOC-20230101-WA0001.pdf").exists()

    def test_fixes_filenames_before_organizing(self, tmp_path):
        src = tmp_path / "WhatsApp Voice Notes"
        src.mkdir()
        (src / "PTT-20230115-WA0001..opus").write_bytes(b"x")

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "organize", "--src", str(src), "--type", "voice_notes"]
        )

        assert result.exit_code == 0
        assert "Fixed 1 filename" in result.output
        organized = tmp_path / "WhatsApp_Voice_Notes_Organized"
        assert (organized / "2023" / "01-Jan" / "PTT-20230115-WA0001.opus").exists()

    def test_invalid_type_exits_nonzero(self, tmp_path):
        result = CliRunner().invoke(
            main.cli, ["whatsapp", "organize", "--src", str(tmp_path), "--type", "bogus"]
        )

        assert result.exit_code != 0

    def test_empty_src_reports_nothing_to_organize(self, tmp_path):
        src = tmp_path / "WhatsApp Voice Notes"
        src.mkdir()

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "organize", "--src", str(src), "--type", "voice_notes"]
        )

        assert result.exit_code == 0
        assert "nothing to organize" in result.output.lower()


class TestWhatsAppFixExtensions:
    def test_fixes_double_dot_and_missing_extension(self, tmp_path):
        (tmp_path / "Sheet..pdf").write_bytes(b"%PDF-1.4")
        (tmp_path / "DOC-20220310-WA0001.").write_bytes(b"%PDF-1.4")

        result = CliRunner().invoke(main.cli, ["whatsapp", "fix-extensions", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert f"{tmp_path / 'Sheet..pdf'} -> {tmp_path / 'Sheet.pdf'}" in result.output
        assert f"{tmp_path / 'DOC-20220310-WA0001.'} -> {tmp_path / 'DOC-20220310-WA0001.pdf'}" in result.output
        assert "Fixed 2 filenames" in result.output
        assert (tmp_path / "Sheet.pdf").exists()
        assert (tmp_path / "DOC-20220310-WA0001.pdf").exists()

    def test_nothing_to_fix_message(self, tmp_path):
        (tmp_path / "IMG-20230101-WA0001.jpg").write_bytes(b"\xff\xd8\xff\xe0")

        result = CliRunner().invoke(main.cli, ["whatsapp", "fix-extensions", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert "No filenames needed fixing." in result.output


# IMG-20230101 (pre-cutoff) and IMG-20250101 (post-cutoff).
DELETE_SCAN_OUTPUT = (
    f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg\t1000\t1672531200.0\n"
    f"{WA_MEDIA}/WhatsApp Images/IMG-20250101-WA0002.jpg\t2000\t1735689600.0\n"
)

# Same as DELETE_SCAN_OUTPUT plus a pre-cutoff Document, for --keep tests.
DELETE_SCAN_OUTPUT_WITH_DOC = DELETE_SCAN_OUTPUT + (
    f"{WA_MEDIA}/WhatsApp Documents/DOC-20230101-WA0001.pdf\t3000\t1672531200.0\n"
)

# After deleting IMG-20230101-WA0001.jpg, only the post-cutoff file remains.
DELETE_RESCAN_OUTPUT = f"{WA_MEDIA}/WhatsApp Images/IMG-20250101-WA0002.jpg\t2000\t1735689600.0\n"


def _write_backup_file(backup_dir, rel_path, size):
    path = backup_dir / "WhatsApp" / "Media" / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


class TestWhatsAppDelete:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "delete", "--before", "2024-09-01", "--backup-dir", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_no_whatsapp_installed_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "delete", "--before", "2024-09-01", "--backup-dir", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "no whatsapp" in result.output.lower()

    def test_invalid_before_date_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "delete", "--before", "not-a-date", "--backup-dir", str(tmp_path)]
        )

        assert result.exit_code != 0
        assert "invalid --before" in result.output.lower()

    def test_invalid_keep_type_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli,
            [
                "whatsapp", "delete",
                "--before", "2024-09-01",
                "--keep", "not-a-type",
                "--backup-dir", str(tmp_path),
            ],
        )

        assert result.exit_code != 0
        assert "invalid --keep" in result.output.lower()

    def test_nothing_to_delete_message(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        shell_outputs = [DETECT_WA_ONLY, DELETE_RESCAN_OUTPUT]  # both files post-cutoff
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "delete", "--before", "2024-09-01", "--backup-dir", str(tmp_path)]
        )

        assert result.exit_code == 0
        assert "nothing to delete" in result.output.lower()
        assert not (tmp_path / "session_logs" / "reports").exists()

    def test_blocks_when_backup_missing(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        shell_outputs = [DETECT_WA_ONLY, DELETE_SCAN_OUTPUT, DF_OUTPUT]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli, ["whatsapp", "delete", "--before", "2024-09-01", "--backup-dir", str(tmp_path)]
        )

        assert result.exit_code == 1
        assert "not backed up" in result.output.lower()
        assert client.shell.call_count == 3

        reports = list((tmp_path / "session_logs" / "reports").glob("whatsapp-deletion-preview_whatsapp_*.txt"))
        assert len(reports) == 1
        assert not list((tmp_path / "session_logs" / "reports").glob("whatsapp-storage-comparison_*.txt"))

    def test_aborts_without_yes_delete_confirmation(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        _write_backup_file(tmp_path, "WhatsApp Images/IMG-20230101-WA0001.jpg", 1000)
        shell_outputs = [DETECT_WA_ONLY, DELETE_SCAN_OUTPUT, DF_OUTPUT]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli,
            ["whatsapp", "delete", "--before", "2024-09-01", "--backup-dir", str(tmp_path)],
            input="no\n",
        )

        assert result.exit_code == 0
        assert "aborted" in result.output.lower()
        assert client.shell.call_count == 3
        reports_dir = tmp_path / "session_logs" / "reports"
        assert list(reports_dir.glob("whatsapp-deletion-preview_whatsapp_*.txt"))
        assert not list(reports_dir.glob("whatsapp-deletion-result_whatsapp_*.txt"))
        assert "Reports saved to session_logs/reports/" not in result.output
        assert not list(reports_dir.glob("whatsapp-storage-comparison_*.txt"))

    def test_full_flow_deletes_and_reports(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        _write_backup_file(tmp_path, "WhatsApp Images/IMG-20230101-WA0001.jpg", 1000)
        shell_outputs = [DETECT_WA_ONLY, DELETE_SCAN_OUTPUT, DF_OUTPUT, "", DELETE_RESCAN_OUTPUT, DF_OUTPUT]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli,
            ["whatsapp", "delete", "--before", "2024-09-01", "--backup-dir", str(tmp_path)],
            input="YES DELETE\n",
        )

        assert result.exit_code == 0
        assert "Total to delete: 1 file" in result.output
        assert "deleted 1 file" in result.output.lower()
        assert "Reports saved to session_logs/reports/" in result.output
        assert client.shell.call_count == 6

        rm_serial, rm_command = client.shell.call_args_list[3][0]
        assert rm_serial == "SERIAL123"
        assert rm_command.startswith("rm -f ")
        assert f"{WA_MEDIA}/WhatsApp Images/IMG-20230101-WA0001.jpg" in rm_command
        assert "IMG-20250101-WA0002.jpg" not in rm_command

        reports_dir = tmp_path / "session_logs" / "reports"
        assert list(reports_dir.glob("whatsapp-deletion-preview_whatsapp_*.txt"))
        assert list(reports_dir.glob("whatsapp-deletion-result_whatsapp_*.txt"))
        assert list(reports_dir.glob("whatsapp-storage-comparison_*.txt"))
        assert list(reports_dir.glob("whatsapp-cleanup-comparison_whatsapp_*.txt"))

    def test_keep_excludes_type_from_deletion(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        _write_backup_file(tmp_path, "WhatsApp Images/IMG-20230101-WA0001.jpg", 1000)
        shell_outputs = [DETECT_WA_ONLY, DELETE_SCAN_OUTPUT_WITH_DOC, DF_OUTPUT, "", DELETE_RESCAN_OUTPUT, DF_OUTPUT]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(
            main.cli,
            [
                "whatsapp", "delete",
                "--before", "2024-09-01",
                "--keep", "documents",
                "--backup-dir", str(tmp_path),
            ],
            input="YES DELETE\n",
        )

        assert result.exit_code == 0
        assert "Total to delete: 1 file" in result.output

        rm_serial, rm_command = client.shell.call_args_list[3][0]
        assert "DOC-20230101-WA0001.pdf" not in rm_command

        reports_dir = tmp_path / "session_logs" / "reports"
        assert list(reports_dir.glob("whatsapp-deletion-preview_whatsapp_*.txt"))
        assert list(reports_dir.glob("whatsapp-deletion-result_whatsapp_*.txt"))
        assert list(reports_dir.glob("whatsapp-storage-comparison_*.txt"))
        assert list(reports_dir.glob("whatsapp-cleanup-comparison_whatsapp_*.txt"))


WA_BASE = "/sdcard/Android/media/com.whatsapp/WhatsApp"
DB_PATH = f"{WA_BASE}/Databases"
BACKUPS_PATH = f"{WA_BASE}/Backups"

DB_SEARCH_OUTPUT = f"{DB_PATH}/msgstore.db.crypt14\t1000\t1672531200.0\n"
BACKUPS_SEARCH_OUTPUT = f"{BACKUPS_PATH}/wa.db.crypt14\t2000\t1672531200.0\n"


class TestWhatsAppBackupDb:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "_build_client", lambda: make_fake_client([]))

        result = CliRunner().invoke(main.cli, ["whatsapp", "backup-db", "--dest", str(tmp_path)])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_no_whatsapp_installed_exits_nonzero(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "backup-db", "--dest", str(tmp_path)])

        assert result.exit_code == 1
        assert "no whatsapp" in result.output.lower()

    def test_nothing_to_back_up_message(self, monkeypatch, tmp_path):
        shell_outputs = [DETECT_WA_ONLY, "0\n", "0\n", "0\n"]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["whatsapp", "backup-db", "--dest", str(tmp_path)])

        assert result.exit_code == 0
        assert "nothing to transfer" in result.output.lower()

    def test_full_backup_pulls_databases_and_backups_reports_encryption(self, monkeypatch, tmp_path):
        shell_outputs = [
            DETECT_WA_ONLY,
            "1\n", DB_SEARCH_OUTPUT,
            "1\n", BACKUPS_SEARCH_OUTPUT,
            "0\n",
        ]
        client = make_fake_client(READY_DEVICE, shell_side_effect=shell_outputs)

        def fake_pull(serial, remote, local):
            size = 1000 if remote.endswith("msgstore.db.crypt14") else 2000
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            Path(local).write_bytes(b"x" * size)

        client.pull.side_effect = fake_pull
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(main, "get_sleep_inhibitor", _noop_inhibitor)

        result = CliRunner().invoke(main.cli, ["whatsapp", "backup-db", "--dest", str(tmp_path)])

        assert result.exit_code == 0
        assert "Pulling 2 files" in result.output
        assert "Verified: 2 file" in result.output
        assert "2/2" in result.output
        assert "msgstore.db.crypt*" in result.output
        assert (tmp_path / "WhatsApp" / "Databases" / "msgstore.db.crypt14").exists()
        assert (tmp_path / "WhatsApp" / "Backups" / "wa.db.crypt14").exists()


_WA_INSTALL = WhatsAppInstall("com.whatsapp", "WhatsApp", "/sdcard/Android/media/com.whatsapp/WhatsApp")
_WA_MEDIA_FILE = MediaFile(
    "/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Images/IMG-20240101-WA0001.jpg",
    1024,
    1704067200.0,
    "Images",
    "Received",
)


class TestScanReportSaved:
    def test_scan_writes_report_file(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.scan_media", return_value=[_WA_MEDIA_FILE]):
            result = runner.invoke(cli, ["whatsapp", "scan"])
        assert result.exit_code == 0
        reports = list((tmp_path / "session_logs" / "reports").glob("whatsapp-scan_whatsapp_*.txt"))
        assert len(reports) == 1

    def test_scan_prints_report_saved(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.scan_media", return_value=[_WA_MEDIA_FILE]):
            result = runner.invoke(cli, ["whatsapp", "scan"])
        assert "Report saved to session_logs/reports/" in result.output

    def test_scan_no_report_when_no_media(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.scan_media", return_value=[]):
            result = runner.invoke(cli, ["whatsapp", "scan"])
        assert result.exit_code == 0
        assert not (tmp_path / "session_logs" / "reports").exists()


class TestAnalyzeReportSaved:
    def test_analyze_writes_report_file(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.scan_media", return_value=[_WA_MEDIA_FILE]):
            result = runner.invoke(cli, ["whatsapp", "analyze", "--cutoff", "2024-01-01"])
        assert result.exit_code == 0
        reports = list((tmp_path / "session_logs" / "reports").glob("whatsapp-analyze_whatsapp_*.txt"))
        assert len(reports) == 1

    def test_analyze_prints_report_saved(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.scan_media", return_value=[_WA_MEDIA_FILE]):
            result = runner.invoke(cli, ["whatsapp", "analyze", "--cutoff", "2024-01-01"])
        assert "Report saved to session_logs/reports/" in result.output


_WA_BACKUP_INSTALL = WhatsAppInstall(
    "com.whatsapp", "WhatsApp", "/sdcard/Android/media/com.whatsapp/WhatsApp"
)
_FAKE_ITEM = TransferItem(
    source="/sdcard/WhatsApp/Media/img.jpg",
    dest="/tmp/backup/img.jpg",
    size=1024,
    action=ACTION_COPY,
)
_FAKE_PLAN = TransferPlan(direction="pull", items=[_FAKE_ITEM])
_FAKE_PROGRESS = TransferProgress(total_files=1, total_bytes=1024, done_files=1, done_bytes=1024)
_FAKE_VERIFICATION = VerificationResult(
    expected_files=1, expected_bytes=1024, actual_files=1, actual_bytes=1024
)


class TestBackupReportSaved:
    def test_backup_writes_report_file(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_BACKUP_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.plan_backup", return_value=_FAKE_PLAN), \
             patch("droidbridge.cli.main.transfer_module.execute_plan", return_value=_FAKE_PROGRESS), \
             patch("droidbridge.cli.main.transfer_module.verify_pull", return_value=_FAKE_VERIFICATION), \
             patch("droidbridge.cli.main.get_sleep_inhibitor", _noop_inhibitor):
            result = runner.invoke(cli, ["whatsapp", "backup", "--dest", str(tmp_path / "backup")])
        assert result.exit_code == 0, result.output
        reports = list((tmp_path / "session_logs" / "reports").glob("whatsapp-backup_*.txt"))
        assert len(reports) == 1

    def test_backup_prints_report_saved(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_BACKUP_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.plan_backup", return_value=_FAKE_PLAN), \
             patch("droidbridge.cli.main.transfer_module.execute_plan", return_value=_FAKE_PROGRESS), \
             patch("droidbridge.cli.main.transfer_module.verify_pull", return_value=_FAKE_VERIFICATION), \
             patch("droidbridge.cli.main.get_sleep_inhibitor", _noop_inhibitor):
            result = runner.invoke(cli, ["whatsapp", "backup", "--dest", str(tmp_path / "backup")])
        assert "Report saved to session_logs/reports/" in result.output

    def test_backup_no_report_when_nothing_to_transfer(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        empty_plan = TransferPlan(direction="pull", items=[])
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_BACKUP_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.plan_backup", return_value=empty_plan), \
             patch("droidbridge.cli.main.get_sleep_inhibitor", _noop_inhibitor):
            result = runner.invoke(cli, ["whatsapp", "backup", "--dest", str(tmp_path / "backup")])
        assert result.exit_code == 0
        assert "nothing to transfer" in result.output.lower()
        assert not (tmp_path / "session_logs" / "reports").exists()

    def test_backup_writes_report_without_verify_when_no_verify_flag(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with patch("droidbridge.cli.main._build_client"), \
             patch("droidbridge.cli.main._resolve_serial", return_value="SERIAL"), \
             patch("droidbridge.cli.main.whatsapp_module.detect_installs", return_value=[_WA_BACKUP_INSTALL]), \
             patch("droidbridge.cli.main.whatsapp_module.plan_backup", return_value=_FAKE_PLAN), \
             patch("droidbridge.cli.main.transfer_module.execute_plan", return_value=_FAKE_PROGRESS), \
             patch("droidbridge.cli.main.transfer_module.verify_pull", return_value=_FAKE_VERIFICATION) as mock_verify, \
             patch("droidbridge.cli.main.get_sleep_inhibitor", _noop_inhibitor):
            result = runner.invoke(
                cli, ["whatsapp", "backup", "--dest", str(tmp_path / "backup"), "--no-verify"]
            )
        assert result.exit_code == 0, result.output
        reports = list((tmp_path / "session_logs" / "reports").glob("whatsapp-backup_*.txt"))
        assert len(reports) == 1
        mock_verify.assert_not_called()
