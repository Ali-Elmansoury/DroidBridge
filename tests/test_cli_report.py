"""Tests for `droidbridge report generate` (Module 9 CLI)."""

import json
from unittest.mock import MagicMock

from click.testing import CliRunner

from droidbridge.cli import main
from droidbridge.core.adb import Device
from droidbridge.modules import backup_manager
from droidbridge.modules.storage import StorageOverview
from droidbridge.reports import storage_reports
from tests.test_cli_whatsapp import DETECT_NONE, DETECT_WA_ONLY, SCAN_OUTPUT
from tests.test_storage import DF_OUTPUT, DISKSTATS_OUTPUT, PM_LIST_SYSTEM_OUTPUT

READY_DEVICE = [Device(serial="SERIAL123", state="device", model="Pixel_7")]


def make_fake_client(devices, shell=None, shell_side_effect=None):
    client = MagicMock()
    client.devices.return_value = devices
    if shell_side_effect is not None:
        client.shell.side_effect = shell_side_effect
    elif shell is not None:
        client.shell.side_effect = shell
    return client


def _device_fake_shell(serial, command, timeout=None):
    if isinstance(command, list):
        if command[0] == "df":
            return DF_OUTPUT
        if command[:2] == ["dumpsys", "diskstats"]:
            return DISKSTATS_OUTPUT
        if command[:3] == ["pm", "list", "packages"]:
            return PM_LIST_SYSTEM_OUTPUT
        raise AssertionError(command)
    if isinstance(command, str) and command.startswith("find -L"):
        return ""
    # detect_installs sends a single combined shell string
    return DETECT_NONE


class TestReportGenerateStorage:
    def test_no_device_shows_guidance_and_exits_nonzero(self, monkeypatch):
        client = make_fake_client([])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "storage"])

        assert result.exit_code == 1
        assert "usb debugging" in result.output.lower()

    def test_generates_txt_report_and_writes_file(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell=_device_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", tmp_path / "storage_history.json")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "storage"])

        assert result.exit_code == 0
        assert "Storage Breakdown Report" in result.output
        assert "Report written to" in result.output

        reports = list((tmp_path / "session_logs" / "reports").glob("storage_*.txt"))
        assert len(reports) == 1

    def test_records_storage_snapshot(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell=_device_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        history_path = tmp_path / "storage_history.json"
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", history_path)
        monkeypatch.chdir(tmp_path)

        CliRunner().invoke(main.cli, ["report", "generate", "--type", "storage"])

        history = storage_reports.load_storage_history(history_path)
        assert len(history) == 1

    def test_json_format_with_explicit_output(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell=_device_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", tmp_path / "storage_history.json")
        output_path = tmp_path / "report.json"

        result = CliRunner().invoke(
            main.cli,
            ["report", "generate", "--type", "storage", "--format", "json", "--output", str(output_path)],
        )

        assert result.exit_code == 0
        data = json.loads(output_path.read_text())
        assert data["title"] == "Storage Breakdown Report"


class TestReportGenerateTopAppsAndLargeFiles:
    def test_top_apps_report(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell=_device_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "top-apps", "--top", "1"])

        assert result.exit_code == 0
        assert "Top Apps by Size Report" in result.output

    def test_large_files_report(self, monkeypatch, tmp_path):
        def fake_shell(serial, command, timeout=None):
            if isinstance(command, str) and command.startswith("find -L"):
                return ""
            return _device_fake_shell(serial, command, timeout)

        client = make_fake_client(READY_DEVICE, shell=fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "large-files"])

        assert result.exit_code == 0
        assert "Large Files Report" in result.output


class TestReportGenerateStorageTrend:
    def test_no_history_errors(self, monkeypatch, tmp_path):
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", tmp_path / "storage_history.json")

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "storage-trend"])

        assert result.exit_code == 1
        assert "no storage history" in result.output.lower()

    def test_shows_trend_after_recording(self, monkeypatch, tmp_path):
        history_path = tmp_path / "storage_history.json"
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", history_path)
        storage_reports.record_storage_snapshot(
            StorageOverview(total_kb=1000, used_kb=400, free_kb=600, categories={}),
            path=history_path,
            timestamp="2026-06-01T00:00:00+00:00",
        )
        storage_reports.record_storage_snapshot(
            StorageOverview(total_kb=1000, used_kb=500, free_kb=500, categories={}),
            path=history_path,
            timestamp="2026-06-08T00:00:00+00:00",
        )
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "storage-trend"])

        assert result.exit_code == 0
        assert "Storage Trend Report" in result.output


class TestReportGenerateBackupHistory:
    def test_no_history_message(self, monkeypatch, tmp_path):
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", tmp_path / "backup_history.json")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "backup-history"])

        assert result.exit_code == 0
        assert "Backup History Report" in result.output

    def test_lists_records(self, monkeypatch, tmp_path):
        history_path = tmp_path / "backup_history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", history_path)
        backup_manager.append_history(
            history_path,
            backup_manager.BackupRecord(
                profile="whatsapp_full",
                timestamp="2026-06-01T00:00:00+00:00",
                file_count=5,
                total_bytes=5000,
                duration_seconds=10.0,
                destination="/media/drive",
                verified=True,
            ),
        )
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "backup-history"])

        assert result.exit_code == 0
        assert "whatsapp_full" in result.output


class TestReportGenerateBackupSummary:
    def test_requires_profile_option(self, monkeypatch, tmp_path):
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", tmp_path / "backup_history.json")

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "backup-summary"])

        assert result.exit_code == 1
        assert "--profile" in result.output

    def test_no_backups_for_profile_errors(self, monkeypatch, tmp_path):
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", tmp_path / "backup_history.json")

        result = CliRunner().invoke(
            main.cli, ["report", "generate", "--type", "backup-summary", "--profile", "whatsapp_full"]
        )

        assert result.exit_code == 1
        assert "no backups recorded" in result.output.lower()


class TestReportGenerateBackupVerification:
    def test_unknown_profile_errors(self, monkeypatch, tmp_path):
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", tmp_path / "backup_history.json")

        result = CliRunner().invoke(
            main.cli, ["report", "generate", "--type", "backup-verification", "--profile", "nope"]
        )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_requires_profile_option(self, monkeypatch, tmp_path):
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", tmp_path / "backup_history.json")

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "backup-verification"])

        assert result.exit_code == 1
        assert "--profile" in result.output

    def test_no_backups_for_profile_errors(self, monkeypatch, tmp_path):
        profiles_path = tmp_path / "profiles.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", tmp_path / "backup_history.json")
        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="whatsapp_full", sources=["/sdcard/a.jpg"], dest=str(tmp_path / "dest")),
        )

        result = CliRunner().invoke(
            main.cli, ["report", "generate", "--type", "backup-verification", "--profile", "whatsapp_full"]
        )

        assert result.exit_code == 1
        assert "no backups recorded" in result.output.lower()

    def test_no_device_needed_and_writes_report(self, monkeypatch, tmp_path):
        profiles_path = tmp_path / "profiles.json"
        history_path = tmp_path / "backup_history.json"
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", profiles_path)
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", history_path)
        monkeypatch.chdir(tmp_path)

        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a.jpg").write_bytes(b"x" * 1000)

        backup_manager.save_profile(
            profiles_path,
            backup_manager.BackupProfile(name="whatsapp_full", sources=["/sdcard/a.jpg"], dest=str(dest)),
        )
        backup_manager.append_history(
            history_path,
            backup_manager.BackupRecord("whatsapp_full", "2026-06-01T00:00:00+00:00", 1, 1000, 1.0, str(dest), True),
        )

        def _fail_build_client():
            raise AssertionError("_build_client should not be called for backup-verification")

        monkeypatch.setattr(main, "_build_client", _fail_build_client)

        result = CliRunner().invoke(
            main.cli,
            ["report", "generate", "--type", "backup-verification", "--profile", "whatsapp_full", "--format", "json"],
        )

        assert result.exit_code == 0
        out_files = list((tmp_path / "session_logs" / "reports").glob("backup-verification_*.json"))
        assert len(out_files) == 1
        content = json.loads(out_files[0].read_text())
        assert content["title"] == "Backup Verification — whatsapp_full"


class TestReportGenerateWhatsApp:
    def test_no_whatsapp_installed_exits_nonzero(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_NONE])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "whatsapp-inventory"])

        assert result.exit_code == 1

    def test_inventory_report(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "whatsapp-inventory"])

        assert result.exit_code == 0
        assert "WhatsApp Media Inventory Report" in result.output

    def test_filetypes_report(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "whatsapp-filetypes"])

        assert result.exit_code == 0
        assert "WhatsApp File Type Breakdown Report" in result.output

    def test_sections_report(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "whatsapp-sections"])

        assert result.exit_code == 0
        assert "WhatsApp Sent/Received/Private Breakdown Report" in result.output

    def test_documents_report(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "whatsapp-documents"])

        assert result.exit_code == 0
        assert "WhatsApp Documents Categorization Report" in result.output

    def test_cutoff_requires_option(self, monkeypatch):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)

        result = CliRunner().invoke(main.cli, ["report", "generate", "--type", "whatsapp-cutoff"])

        assert result.exit_code == 1
        assert "--cutoff" in result.output

    def test_cutoff_report(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell_side_effect=[DETECT_WA_ONLY, SCAN_OUTPUT])
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(
            main.cli, ["report", "generate", "--type", "whatsapp-cutoff", "--cutoff", "2024-09-01"]
        )

        assert result.exit_code == 0
        assert "WhatsApp Pre/Post Cutoff Comparison Report" in result.output


class TestReportGenerateFull:
    def test_combines_sections(self, monkeypatch, tmp_path):
        client = make_fake_client(READY_DEVICE, shell=_device_fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", tmp_path / "storage_history.json")
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", tmp_path / "backup_history.json")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate"])

        assert result.exit_code == 0
        assert "DroidBridge Full Report" in result.output
        assert "Top" in result.output
        assert "Large Files" in result.output

    def test_includes_whatsapp_breakdowns_when_installed(self, monkeypatch, tmp_path):
        def fake_shell(serial, command, timeout=None):
            if isinstance(command, list):
                if command[0] == "df":
                    return DF_OUTPUT
                if command[:2] == ["dumpsys", "diskstats"]:
                    return DISKSTATS_OUTPUT
                if command[:3] == ["pm", "list", "packages"]:
                    return PM_LIST_SYSTEM_OUTPUT
                raise AssertionError(command)
            if isinstance(command, str) and command.startswith("find -L"):
                return ""
            if not hasattr(fake_shell, "_calls"):
                fake_shell._calls = 0
            fake_shell._calls += 1
            return DETECT_WA_ONLY if fake_shell._calls == 1 else SCAN_OUTPUT

        client = make_fake_client(READY_DEVICE, shell=fake_shell)
        monkeypatch.setattr(main, "_build_client", lambda: client)
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", tmp_path / "storage_history.json")
        monkeypatch.setattr(backup_manager, "DEFAULT_HISTORY_PATH", tmp_path / "backup_history.json")
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(main.cli, ["report", "generate"])

        assert result.exit_code == 0
        assert "Large Files" in result.output
        assert "File Types" in result.output
        assert "By Section" in result.output
        assert "Documents by Category" in result.output
