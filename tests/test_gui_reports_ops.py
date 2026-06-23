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


from unittest.mock import MagicMock

from droidbridge.modules.storage import StorageOverview
from droidbridge.reports import storage_reports


class TestGenerateReportStorage:
    def test_storage_type_builds_report_and_records_snapshot(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", tmp_path / "history.json")
        overview = StorageOverview(total_kb=1000, used_kb=400, free_kb=600, categories={})
        monkeypatch.setattr(reports_ops.storage_module, "get_storage_overview", lambda c, s: overview)

        result = reports_ops.generate_report(MagicMock(), "SERIAL", "storage", "txt")

        assert "Storage Breakdown Report" in result["content"]
        assert result["default_filename"].startswith("storage_")
        assert result["default_filename"].endswith(".txt")
        history = storage_reports.load_storage_history(tmp_path / "history.json")
        assert len(history) == 1

    def test_top_apps_type_passes_top_n_through(self, monkeypatch):
        apps = [MagicMock(package=f"com.app{i}", apk_size=1000, data_size=2000, cache_size=500, total_size=i) for i in range(3)]
        captured = {}
        real_build_top_apps = storage_reports.build_top_apps_report

        def fake_build_top_apps(apps_arg, top=20):
            captured["top"] = top
            return real_build_top_apps(apps_arg, top=top)

        monkeypatch.setattr(reports_ops.storage_module, "get_app_storage", lambda c, s: apps)
        monkeypatch.setattr(reports_ops.storage_reports, "build_top_apps_report", fake_build_top_apps)

        result = reports_ops.generate_report(MagicMock(), "SERIAL", "top-apps", "txt", top_n=1)

        assert captured["top"] == 1
        assert "Top Apps by Size Report" in result["content"]

    def test_large_files_type_uses_default_threshold_when_min_size_blank(self, monkeypatch):
        captured = {}

        def fake_find_large_files(client, serial, threshold=None):
            captured["threshold"] = threshold
            return []

        monkeypatch.setattr(reports_ops.storage_module, "find_large_files", fake_find_large_files)

        reports_ops.generate_report(MagicMock(), "SERIAL", "large-files", "txt")

        assert captured["threshold"] == reports_ops.search_module.LARGE_FILE_THRESHOLD

    def test_large_files_type_parses_min_size(self, monkeypatch):
        captured = {}

        def fake_find_large_files(client, serial, threshold=None):
            captured["threshold"] = threshold
            return []

        monkeypatch.setattr(reports_ops.storage_module, "find_large_files", fake_find_large_files)

        reports_ops.generate_report(MagicMock(), "SERIAL", "large-files", "txt", min_size="10MB")

        assert captured["threshold"] == 10 * 1024 * 1024

    def test_storage_trend_type_raises_when_no_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", tmp_path / "history.json")

        try:
            reports_ops.generate_report(None, None, "storage-trend", "txt")
            assert False, "expected ValueError"
        except ValueError as exc:
            assert str(exc) == "No storage history recorded yet. Run `report generate --type storage` first."

    def test_storage_trend_type_builds_report_from_history(self, tmp_path, monkeypatch):
        history_path = tmp_path / "history.json"
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", history_path)
        storage_reports.record_storage_snapshot(
            StorageOverview(total_kb=1000, used_kb=400, free_kb=600, categories={}),
            path=history_path, timestamp="2026-06-01T00:00:00+00:00",
        )
        storage_reports.record_storage_snapshot(
            StorageOverview(total_kb=1000, used_kb=500, free_kb=500, categories={}),
            path=history_path, timestamp="2026-06-08T00:00:00+00:00",
        )

        result = reports_ops.generate_report(None, None, "storage-trend", "txt")

        assert "Storage Trend Report" in result["content"]

    def test_json_format_renders_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage_reports, "DEFAULT_TREND_PATH", tmp_path / "history.json")
        overview = StorageOverview(total_kb=1000, used_kb=400, free_kb=600, categories={})
        monkeypatch.setattr(reports_ops.storage_module, "get_storage_overview", lambda c, s: overview)

        result = reports_ops.generate_report(MagicMock(), "SERIAL", "storage", "json")

        import json
        data = json.loads(result["content"])
        assert data["title"] == "Storage Breakdown Report"

    def test_unknown_report_type_raises(self):
        try:
            reports_ops.generate_report(None, None, "not-a-type", "txt")
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "not-a-type" in str(exc)
