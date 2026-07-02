# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock

from droidbridge.gui import apps_ops
from droidbridge.modules.apps import AppInfo


def _app(package, version_name="1.0", version_code=1, apk=1000, data=2000, cache=3000,
         is_system=False, is_disabled=False, first_install=None, last_update=None):
    return AppInfo(
        package=package, version_name=version_name, version_code=version_code,
        first_install_time=first_install, last_update_time=last_update,
        apk_size=apk, data_size=data, cache_size=cache,
        is_system=is_system, is_disabled=is_disabled,
    )


class TestGetApps:
    def test_formats_rows_and_passes_filter_sort_through(self, monkeypatch):
        a = _app("com.a", apk=10, data=20, cache=5, first_install=datetime(2024, 1, 1, 9, 0))
        b = _app("com.b", apk=100, data=200, cache=50, is_system=True, is_disabled=True)
        monkeypatch.setattr(apps_ops.apps_module, "get_apps", lambda c, s: [a, b])
        monkeypatch.setattr(apps_ops.apps_module, "get_launcher_labels", lambda c, s: {"com.a": "App A"})
        captured = {}
        monkeypatch.setattr(
            apps_ops.apps_module, "filter_apps",
            lambda apps, kind: captured.setdefault("filter_kind", kind) and apps,
        )
        monkeypatch.setattr(
            apps_ops.apps_module, "sort_apps",
            lambda apps, by, reverse: captured.setdefault("sort", (by, reverse)) and apps,
        )

        result = apps_ops.get_apps(MagicMock(), "S1", filter_kind="system", sort_by="total", reverse=True)

        assert captured["filter_kind"] == "system"
        assert captured["sort"] == ("total", True)
        assert result[0]["app_label"] == "App A"
        assert result[0]["package"] == "com.a"
        assert result[0]["apk_size"] == 10
        assert result[0]["apk_size_str"] == "10 B"
        assert result[0]["data_size"] == 20
        assert result[0]["cache_size"] == 5
        assert result[0]["total_size_str"] == "35 B"
        assert result[0]["kind"] == "user"
        assert result[0]["is_system"] is False
        assert result[0]["installed_str"] == "2024-01-01 09:00"
        assert result[0]["updated_str"] == ""
        assert result[1]["app_label"] == "com.b"   # no label → falls back to package
        assert result[1]["kind"] == "system"
        assert result[1]["status"] == "Disabled"
        assert result[1]["is_disabled"] is True

    def test_default_filter_and_sort_args(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(apps_ops.apps_module, "get_apps", lambda c, s: [])
        monkeypatch.setattr(apps_ops.apps_module, "get_launcher_labels", lambda c, s: {})
        monkeypatch.setattr(
            apps_ops.apps_module, "filter_apps",
            lambda apps, kind: captured.setdefault("filter_kind", kind) and apps,
        )
        monkeypatch.setattr(
            apps_ops.apps_module, "sort_apps",
            lambda apps, by, reverse: captured.setdefault("sort", (by, reverse)) and apps,
        )

        apps_ops.get_apps(MagicMock(), "S1")

        assert captured["filter_kind"] == "all"
        assert captured["sort"] == ("name", False)


class TestGetAppInfo:
    def test_returns_formatted_row_for_matching_package(self, monkeypatch):
        a = _app("com.a")
        b = _app("com.b")
        monkeypatch.setattr(apps_ops.apps_module, "get_apps", lambda c, s: [a, b])

        result = apps_ops.get_app_info(MagicMock(), "S1", "com.b")

        assert result["package"] == "com.b"

    def test_returns_none_when_package_not_found(self, monkeypatch):
        monkeypatch.setattr(apps_ops.apps_module, "get_apps", lambda c, s: [_app("com.a")])

        result = apps_ops.get_app_info(MagicMock(), "S1", "com.missing")

        assert result is None


class TestEstimateCacheClear:
    def test_sums_cache_size_from_rows_with_no_device_call(self):
        rows = [{"cache_size": 1000}, {"cache_size": 2000}]

        result = apps_ops.estimate_cache_clear(rows)

        assert result == {"estimate_bytes": 3000, "estimate_str": "2.9 KB"}

    def test_empty_rows_gives_zero(self):
        assert apps_ops.estimate_cache_clear([]) == {"estimate_bytes": 0, "estimate_str": "0 B"}


class TestTrimCaches:
    def test_calls_module_trim_caches(self, monkeypatch):
        calls = []
        monkeypatch.setattr(apps_ops.apps_module, "trim_caches", lambda c, s, n: calls.append((s, n)))

        apps_ops.trim_caches(MagicMock(), "S1", 5000)

        assert calls == [("S1", 5000)]


class TestResetAppData:
    def test_calls_module_clear_app_data(self, monkeypatch):
        calls = []
        monkeypatch.setattr(apps_ops.apps_module, "get_apps", lambda c, s: [_app("com.a")])
        monkeypatch.setattr(apps_ops.apps_module, "clear_app_data", lambda c, s, p: calls.append((s, p)))

        apps_ops.reset_app_data(MagicMock(), "S1", "com.a")

        assert calls == [("S1", "com.a")]

    def test_raises_value_error_and_does_not_call_module_for_system_app(self, monkeypatch):
        calls = []
        monkeypatch.setattr(apps_ops.apps_module, "get_apps", lambda c, s: [_app("com.a", is_system=True)])
        monkeypatch.setattr(apps_ops.apps_module, "clear_app_data", lambda c, s, p: calls.append((s, p)))

        try:
            apps_ops.reset_app_data(MagicMock(), "S1", "com.a")
            assert False, "expected ValueError"
        except ValueError:
            pass

        assert calls == []


class TestUninstallApp:
    def test_calls_module_uninstall_and_returns_true(self, monkeypatch):
        calls = []
        monkeypatch.setattr(apps_ops.apps_module, "get_apps", lambda c, s: [_app("com.a")])
        monkeypatch.setattr(
            apps_ops.apps_module, "uninstall_app",
            lambda c, s, p, keep_data=False: calls.append((s, p, keep_data)),
        )

        result = apps_ops.uninstall_app(MagicMock(), "S1", "com.a", keep_data=True)

        assert result is True
        assert calls == [("S1", "com.a", True)]

    def test_raises_value_error_and_does_not_call_module_for_system_app(self, monkeypatch):
        calls = []
        monkeypatch.setattr(apps_ops.apps_module, "get_apps", lambda c, s: [_app("com.a", is_system=True)])
        monkeypatch.setattr(
            apps_ops.apps_module, "uninstall_app",
            lambda c, s, p, keep_data=False: calls.append((s, p, keep_data)),
        )

        try:
            apps_ops.uninstall_app(MagicMock(), "S1", "com.a")
            assert False, "expected ValueError"
        except ValueError:
            pass

        assert calls == []


class TestDisableEnableApp:
    def test_disable_calls_module(self, monkeypatch):
        calls = []
        monkeypatch.setattr(apps_ops.apps_module, "disable_app", lambda c, s, p: calls.append((s, p)))

        apps_ops.disable_app(MagicMock(), "S1", "com.a")

        assert calls == [("S1", "com.a")]

    def test_enable_calls_module(self, monkeypatch):
        calls = []
        monkeypatch.setattr(apps_ops.apps_module, "enable_app", lambda c, s, p: calls.append((s, p)))

        apps_ops.enable_app(MagicMock(), "S1", "com.a")

        assert calls == [("S1", "com.a")]


class TestGetApkInfo:
    def test_formats_files_and_total(self, monkeypatch):
        monkeypatch.setattr(
            apps_ops.apps_module, "get_apk_info",
            lambda c, s, p: [("/data/app/x/base.apk", 1000), ("/data/app/x/split.apk", 500)],
        )

        result = apps_ops.get_apk_info(MagicMock(), "S1", "com.a")

        assert result["files"] == [
            {"path": "/data/app/x/base.apk", "size": 1000, "size_str": "1000 B"},
            {"path": "/data/app/x/split.apk", "size": 500, "size_str": "500 B"},
        ]
        assert result["total_size_str"] == "1.5 KB"


class TestExtractApk:
    def test_pulls_each_file_into_dest_dir_and_reports_progress(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            apps_ops.apps_module, "get_apk_info",
            lambda c, s, p: [("/data/app/x/base.apk", 1000)],
        )
        pulls = []
        client = MagicMock()
        client.pull.side_effect = lambda serial, remote, local: pulls.append((serial, remote, local))
        progress_messages = []

        result = apps_ops.extract_apk(
            client, "S1", "com.a", str(tmp_path), progress_callback=progress_messages.append
        )

        assert result == [str(tmp_path / "base.apk")]
        assert pulls == [("S1", "/data/app/x/base.apk", str(tmp_path / "base.apk"))]
        assert progress_messages


class TestBackupApk:
    def test_pulls_files_into_versioned_dir_and_writes_manifest(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            apps_ops.apps_module, "get_apk_info",
            lambda c, s, p: [("/data/app/x/base.apk", 1000)],
        )
        pulls = []
        client = MagicMock()
        client.pull.side_effect = lambda serial, remote, local: pulls.append((remote, local))

        bundle_dir = apps_ops.backup_apk(
            client, "S1", "com.a", "1.2.3", 42, str(tmp_path),
        )

        assert bundle_dir == str(tmp_path / "com.a_42")
        assert pulls == [("/data/app/x/base.apk", str(tmp_path / "com.a_42" / "base.apk"))]
        manifest = json.loads((Path(bundle_dir) / "manifest.json").read_text())
        assert manifest["package"] == "com.a"
        assert manifest["version_name"] == "1.2.3"
        assert manifest["version_code"] == 42
        assert manifest["apk_files"] == [{"filename": "base.apk", "size": 1000}]
        assert "backed_up_at" in manifest


class TestVerifyApkBackup:
    def test_returns_true_when_sizes_match(self, tmp_path):
        bundle_dir = tmp_path / "com.a_1"
        bundle_dir.mkdir()
        (bundle_dir / "base.apk").write_bytes(b"x" * 1000)
        manifest = {
            "package": "com.a", "version_name": "1.0", "version_code": 1,
            "apk_files": [{"filename": "base.apk", "size": 1000}], "backed_up_at": "2026-01-01",
        }
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest))

        assert apps_ops.verify_apk_backup(str(bundle_dir)) is True

    def test_returns_false_when_size_mismatched(self, tmp_path):
        bundle_dir = tmp_path / "com.a_1"
        bundle_dir.mkdir()
        (bundle_dir / "base.apk").write_bytes(b"x" * 500)
        manifest = {
            "package": "com.a", "version_name": "1.0", "version_code": 1,
            "apk_files": [{"filename": "base.apk", "size": 1000}], "backed_up_at": "2026-01-01",
        }
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest))

        assert apps_ops.verify_apk_backup(str(bundle_dir)) is False

    def test_returns_false_when_file_missing(self, tmp_path):
        bundle_dir = tmp_path / "com.a_1"
        bundle_dir.mkdir()
        manifest = {
            "package": "com.a", "version_name": "1.0", "version_code": 1,
            "apk_files": [{"filename": "base.apk", "size": 1000}], "backed_up_at": "2026-01-01",
        }
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest))

        assert apps_ops.verify_apk_backup(str(bundle_dir)) is False


class TestReadManifest:
    def test_round_trips_backup_apk_output(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            apps_ops.apps_module, "get_apk_info",
            lambda c, s, p: [("/data/app/x/base.apk", 1000)],
        )
        client = MagicMock()
        bundle_dir = apps_ops.backup_apk(client, "S1", "com.a", "1.0", 1, str(tmp_path))

        manifest = apps_ops.read_manifest(bundle_dir)

        assert manifest["package"] == "com.a"
        assert manifest["apk_files"] == [{"filename": "base.apk", "size": 1000}]


class TestRestoreApk:
    def test_installs_apk_files_from_manifest(self, monkeypatch, tmp_path):
        bundle_dir = tmp_path / "com.a_1"
        bundle_dir.mkdir()
        (bundle_dir / "base.apk").write_bytes(b"x")
        manifest = {
            "package": "com.a", "version_name": "1.0", "version_code": 1,
            "apk_files": [{"filename": "base.apk", "size": 1}], "backed_up_at": "2026-01-01",
        }
        (bundle_dir / "manifest.json").write_text(json.dumps(manifest))
        calls = []
        monkeypatch.setattr(
            apps_ops.apps_module, "install_apk",
            lambda c, s, paths, allow_downgrade=False: calls.append((s, paths, allow_downgrade)),
        )

        result = apps_ops.restore_apk(MagicMock(), "S1", str(bundle_dir), allow_downgrade=True)

        assert result["package"] == "com.a"
        assert calls == [("S1", [str(bundle_dir / "base.apk")], True)]


class TestParseLauncherPackages:
    def test_extracts_packages_from_brief_output(self):
        output = (
            "3 activities found:\n"
            "  Activity #0:\n"
            "    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true\n"
            "    com.android.chrome/com.google.android.apps.chrome.Main\n"
            "  Activity #1:\n"
            "    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true\n"
            "    com.whatsapp/.HomeActivity\n"
            "  Activity #2:\n"
            "    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true\n"
            "    com.android.contacts/.DialtactsActivityAlias\n"
        )
        result = apps_ops._parse_launcher_packages(output)
        assert result == {"com.android.chrome", "com.whatsapp", "com.android.contacts"}

    def test_empty_output_returns_empty_set(self):
        assert apps_ops._parse_launcher_packages("") == set()


class TestParseApkPaths:
    def test_extracts_package_to_apk_mapping(self):
        output = (
            "package:/data/app/~~abc==/com.whatsapp-xyz==/base.apk=com.whatsapp\n"
            "package:/system/app/Chrome/Chrome.apk=com.android.chrome\n"
        )
        result = apps_ops._parse_apk_paths(output)
        assert result["com.whatsapp"] == "/data/app/~~abc==/com.whatsapp-xyz==/base.apk"
        assert result["com.android.chrome"] == "/system/app/Chrome/Chrome.apk"

    def test_first_entry_wins_for_duplicate_package(self):
        output = (
            "package:/data/app/base.apk=com.pkg\n"
            "package:/data/app/split.apk=com.pkg\n"
        )
        result = apps_ops._parse_apk_paths(output)
        assert result["com.pkg"] == "/data/app/base.apk"


class TestResolveAppLabels:
    def test_returns_cache_immediately_when_no_aapt2(self, monkeypatch, tmp_path):
        monkeypatch.setattr(apps_ops.apps_module, "find_aapt2", lambda: None)
        monkeypatch.setattr(apps_ops, "load_label_cache", lambda s: {"com.a": "App A"})
        result = apps_ops.resolve_app_labels(MagicMock(), "S1", ["com.a"])
        assert result == {"com.a": "App A"}

    def test_skips_already_cached_packages(self, monkeypatch, tmp_path):
        monkeypatch.setattr(apps_ops.apps_module, "find_aapt2", lambda: "/fake/aapt2")
        monkeypatch.setattr(apps_ops, "load_label_cache", lambda s: {"com.a": "App A"})
        monkeypatch.setattr(apps_ops, "_save_label_cache", lambda s, c: None)
        client = MagicMock()
        client.shell.return_value = "1 activities found:\n    com.a/.Main\n"
        result = apps_ops.resolve_app_labels(client, "S1", ["com.a"])
        # pull should not have been called since com.a is cached
        client.pull.assert_not_called()
        assert result["com.a"] == "App A"

    def test_resolves_uncached_launcher_package(self, monkeypatch, tmp_path):
        monkeypatch.setattr(apps_ops.apps_module, "find_aapt2", lambda: "/fake/aapt2")
        monkeypatch.setattr(apps_ops, "load_label_cache", lambda s: {})
        saved = {}
        monkeypatch.setattr(apps_ops, "_save_label_cache", lambda s, c: saved.update(c))
        monkeypatch.setattr(apps_ops.apps_module, "extract_label_from_apk",
                            lambda aapt2, apk: "WhatsApp")
        client = MagicMock()
        client.shell.side_effect = [
            "1 activities found:\n    com.whatsapp/.HomeActivity\n",   # launcher query
            "package:/data/app/base.apk=com.whatsapp\n",              # pm list packages -f
        ]
        result = apps_ops.resolve_app_labels(client, "S1", ["com.whatsapp"])
        assert result.get("com.whatsapp") == "WhatsApp"
        assert saved.get("com.whatsapp") == "WhatsApp"

    def test_skips_non_launcher_packages(self, monkeypatch):
        monkeypatch.setattr(apps_ops.apps_module, "find_aapt2", lambda: "/fake/aapt2")
        monkeypatch.setattr(apps_ops, "load_label_cache", lambda s: {})
        monkeypatch.setattr(apps_ops, "_save_label_cache", lambda s, c: None)
        client = MagicMock()
        client.shell.side_effect = [
            # launcher query returns only com.launcher
            "1 activities found:\n    com.launcher/.Main\n",
            "package:/data/app/base.apk=com.background\n",
        ]
        result = apps_ops.resolve_app_labels(client, "S1", ["com.background"])
        client.pull.assert_not_called()
