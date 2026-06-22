from pathlib import Path

from droidbridge.gui import reports_ops
from droidbridge.modules import backup_manager


class TestReportTypesTable:
    def test_has_exactly_thirteen_types(self):
        assert len(reports_ops.REPORT_TYPES) == 13

    def test_ids_match_cli_report_types(self):
        ids = [t["id"] for t in reports_ops.REPORT_TYPES]
        assert ids == [
            "full", "storage", "top-apps", "large-files", "storage-trend",
            "whatsapp-inventory", "whatsapp-cutoff", "whatsapp-filetypes",
            "whatsapp-sections", "whatsapp-documents",
            "backup-history", "backup-summary", "backup-verification",
        ]

    def test_needs_device_matches_cli_logic(self):
        no_device = {"storage-trend", "backup-history", "backup-summary", "backup-verification"}
        for t in reports_ops.REPORT_TYPES:
            expected = t["id"] not in no_device
            assert t["needs_device"] is expected, t["id"]

    def test_profile_required_only_for_summary_and_verification(self):
        required = {"backup-summary", "backup-verification"}
        for t in reports_ops.REPORT_TYPES:
            expected = t["id"] in required
            assert t["profile_required"] is expected, t["id"]

    def test_by_id_lookup_matches_table(self):
        for t in reports_ops.REPORT_TYPES:
            assert reports_ops.REPORT_TYPES_BY_ID[t["id"]] is t


class TestListProfileNames:
    def test_empty_when_no_profiles(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        assert reports_ops.list_profile_names() == []

    def test_returns_saved_profile_names(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_manager, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        backup_manager.save_profile(
            tmp_path / "profiles.json",
            backup_manager.BackupProfile(name="nightly", sources=["/sdcard/DCIM"], dest=str(tmp_path / "dest")),
        )
        assert reports_ops.list_profile_names() == ["nightly"]


class TestSaveReport:
    def test_writes_content_to_path(self, tmp_path):
        out = tmp_path / "report.txt"
        reports_ops.save_report("hello", str(out))
        assert out.read_text(encoding="utf-8") == "hello"

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "nested" / "dir" / "report.json"
        reports_ops.save_report("{}", str(out))
        assert out.exists()
        assert out.read_text(encoding="utf-8") == "{}"
