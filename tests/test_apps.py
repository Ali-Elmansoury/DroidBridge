"""Tests for droidbridge.modules.apps - Module 8: App Manager."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from droidbridge.core.adb import AdbCommandError
from droidbridge.modules import apps
from tests.test_storage import DISKSTATS_OUTPUT, PM_LIST_SYSTEM_OUTPUT

PACKAGE_DUMP_OUTPUT = (
    "Packages:\n"
    "  Package [com.whatsapp] (a16800d):\n"
    "    versionCode=261707200 minSdk=21 targetSdk=36\n"
    "    versionName=2.26.17.72\n"
    "    timeStamp=2026-05-12 23:16:22\n"
    "    firstInstallTime=2020-09-12 11:27:53\n"
    "    lastUpdateTime=2026-05-12 23:16:24\n"
    "  Package [com.android.chrome] (b27911e):\n"
    "    versionCode=533012345 minSdk=29 targetSdk=34\n"
    "    versionName=120.0.6099.43\n"
    "    timeStamp=2024-01-10 08:00:00\n"
    "    firstInstallTime=2021-03-01 09:00:00\n"
    "    lastUpdateTime=2024-01-10 08:00:05\n"
)

PM_LIST_DISABLED_OUTPUT = "package:com.android.chrome\n"


class TestParsePackageDump:
    def test_parses_version_and_dates(self):
        info = apps.parse_package_dump(PACKAGE_DUMP_OUTPUT)

        assert info["com.whatsapp"]["version_name"] == "2.26.17.72"
        assert info["com.whatsapp"]["version_code"] == 261707200
        assert info["com.whatsapp"]["first_install_time"] == datetime(2020, 9, 12, 11, 27, 53)
        assert info["com.whatsapp"]["last_update_time"] == datetime(2026, 5, 12, 23, 16, 24)
        assert info["com.android.chrome"]["version_name"] == "120.0.6099.43"

    def test_empty_output_returns_empty_dict(self):
        assert apps.parse_package_dump("") == {}


class TestAppInfo:
    def test_total_size_and_name_fallback(self):
        app = apps.AppInfo(
            package="com.whatsapp",
            version_name="2.26.17.72",
            version_code=261707200,
            first_install_time=None,
            last_update_time=None,
            apk_size=100,
            data_size=200,
            cache_size=50,
            is_system=False,
            is_disabled=False,
        )

        assert app.total_size == 350
        assert app.name == "com.whatsapp"


class TestGetApps:
    def test_combines_sizes_metadata_and_flags(self):
        client = MagicMock()

        def fake_shell(serial, command, timeout=None):
            assert serial == "SERIAL123"
            if command[:2] == ["dumpsys", "diskstats"]:
                return DISKSTATS_OUTPUT
            if command[:3] == ["dumpsys", "package", "packages"]:
                return PACKAGE_DUMP_OUTPUT
            if command[:4] == ["pm", "list", "packages", "-s"]:
                return PM_LIST_SYSTEM_OUTPUT
            if command[:4] == ["pm", "list", "packages", "-d"]:
                return PM_LIST_DISABLED_OUTPUT
            raise AssertionError(f"Unexpected shell command: {command}")

        client.shell.side_effect = fake_shell

        app_list = apps.get_apps(client, "SERIAL123")

        whatsapp = next(a for a in app_list if a.package == "com.whatsapp")
        chrome = next(a for a in app_list if a.package == "com.android.chrome")

        assert whatsapp.version_name == "2.26.17.72"
        assert whatsapp.version_code == 261707200
        assert whatsapp.first_install_time == datetime(2020, 9, 12, 11, 27, 53)
        assert whatsapp.apk_size == 184619008
        assert whatsapp.data_size == 66915028992
        assert whatsapp.cache_size == 33968128
        assert whatsapp.total_size == whatsapp.apk_size + whatsapp.data_size + whatsapp.cache_size
        assert whatsapp.is_system is False
        assert whatsapp.is_disabled is False

        assert chrome.is_system is True
        assert chrome.is_disabled is True


def _make_app(package, total=(0, 0, 0), is_system=False, first_install=None, last_update=None):
    apk, data, cache = total
    return apps.AppInfo(
        package=package,
        version_name="1.0",
        version_code=1,
        first_install_time=first_install,
        last_update_time=last_update,
        apk_size=apk,
        data_size=data,
        cache_size=cache,
        is_system=is_system,
        is_disabled=False,
    )


class TestSortApps:
    def test_sort_by_total_size_descending(self):
        a = _make_app("com.a", total=(100, 0, 0))
        b = _make_app("com.b", total=(500, 0, 0))
        c = _make_app("com.c", total=(200, 0, 0))

        result = apps.sort_apps([a, b, c], by="total", reverse=True)

        assert [x.package for x in result] == ["com.b", "com.c", "com.a"]

    def test_sort_by_size_descending_matches_total(self):
        a = _make_app("com.a", total=(100, 0, 0))
        b = _make_app("com.b", total=(500, 0, 0))
        c = _make_app("com.c", total=(200, 0, 0))

        result = apps.sort_apps([a, b, c], by="size", reverse=True)

        assert [x.package for x in result] == ["com.b", "com.c", "com.a"]

    def test_sort_by_name_ascending(self):
        a = _make_app("com.charlie")
        b = _make_app("com.alpha")
        c = _make_app("com.bravo")

        result = apps.sort_apps([a, b, c], by="name", reverse=False)

        assert [x.package for x in result] == ["com.alpha", "com.bravo", "com.charlie"]

    def test_sort_by_install_date(self):
        a = _make_app("com.old", first_install=datetime(2018, 1, 1))
        b = _make_app("com.new", first_install=datetime(2024, 1, 1))

        result = apps.sort_apps([a, b], by="install_date", reverse=True)

        assert [x.package for x in result] == ["com.new", "com.old"]

    def test_unknown_sort_key_raises(self):
        with pytest.raises(ValueError):
            apps.sort_apps([], by="bogus")


class TestFilterApps:
    def test_filters_by_system_and_user(self):
        a = _make_app("com.system", is_system=True)
        b = _make_app("com.user", is_system=False)

        assert apps.filter_apps([a, b], "system") == [a]
        assert apps.filter_apps([a, b], "user") == [b]
        assert apps.filter_apps([a, b], "all") == [a, b]

    def test_unknown_filter_kind_raises(self):
        with pytest.raises(ValueError):
            apps.filter_apps([], "bogus")


class TestEstimateCacheClear:
    def test_sums_cache_sizes(self):
        a = _make_app("com.a", total=(0, 0, 1000))
        b = _make_app("com.b", total=(0, 0, 2000))

        assert apps.estimate_cache_clear([a, b]) == 3000


class TestTrimCaches:
    def test_calls_pm_trim_caches_with_bytes(self):
        client = MagicMock()

        apps.trim_caches(client, "SERIAL123", 1234567)

        client.shell.assert_called_once_with("SERIAL123", ["pm", "trim-caches", "1234567"])


class TestClearAppData:
    def test_calls_pm_clear(self):
        client = MagicMock()

        apps.clear_app_data(client, "SERIAL123", "com.example.app")

        client.shell.assert_called_once_with("SERIAL123", ["pm", "clear", "com.example.app"])


class TestUninstallApp:
    def test_calls_pm_uninstall(self):
        client = MagicMock()

        apps.uninstall_app(client, "SERIAL123", "com.example.app")

        client.shell.assert_called_once_with("SERIAL123", ["pm", "uninstall", "com.example.app"])

    def test_keep_data_adds_flag(self):
        client = MagicMock()

        apps.uninstall_app(client, "SERIAL123", "com.example.app", keep_data=True)

        client.shell.assert_called_once_with("SERIAL123", ["pm", "uninstall", "-k", "com.example.app"])


class TestGetApkPaths:
    def test_parses_base_and_split_apks(self):
        client = MagicMock()
        client.shell.return_value = (
            "package:/data/app/x/base.apk\n"
            "package:/data/app/x/split_config.arm64_v8a.apk\n"
        )

        paths = apps.get_apk_paths(client, "SERIAL123", "com.whatsapp")

        assert paths == [
            "/data/app/x/base.apk",
            "/data/app/x/split_config.arm64_v8a.apk",
        ]
        client.shell.assert_called_once_with("SERIAL123", ["pm", "path", "com.whatsapp"])

    def test_unknown_package_returns_empty_list(self):
        client = MagicMock()
        client.shell.side_effect = AdbCommandError(["pm", "path", "com.unknown"], 1, "", "")

        assert apps.get_apk_paths(client, "SERIAL123", "com.unknown") == []


class TestGetApkInfo:
    def test_returns_path_and_size_pairs(self):
        client = MagicMock()

        def fake_shell(serial, command, timeout=None):
            if command == ["pm", "path", "com.whatsapp"]:
                return "package:/data/app/x/base.apk\n"
            if isinstance(command, str) and command.startswith("find -L"):
                return "68039298"
            raise AssertionError(command)

        client.shell.side_effect = fake_shell

        info = apps.get_apk_info(client, "SERIAL123", "com.whatsapp")

        assert info == [("/data/app/x/base.apk", 68039298)]


class TestDisableApp:
    def test_calls_pm_disable_user(self):
        client = MagicMock()

        apps.disable_app(client, "SERIAL123", "com.example.bloat")

        client.shell.assert_called_once_with(
            "SERIAL123", ["pm", "disable-user", "--user", "0", "com.example.bloat"]
        )


class TestEnableApp:
    def test_calls_pm_enable(self):
        client = MagicMock()

        apps.enable_app(client, "SERIAL123", "com.example.bloat")

        client.shell.assert_called_once_with(
            "SERIAL123", ["pm", "enable", "--user", "0", "com.example.bloat"]
        )


class TestInstallApk:
    def test_passes_paths_through_to_client_install(self):
        client = MagicMock()

        apps.install_apk(client, "SERIAL123", ["/local/base.apk", "/local/split.apk"])

        client.install.assert_called_once_with(
            "SERIAL123", ["/local/base.apk", "/local/split.apk"], allow_downgrade=False
        )

    def test_passes_allow_downgrade_through(self):
        client = MagicMock()

        apps.install_apk(client, "SERIAL123", ["/local/base.apk"], allow_downgrade=True)

        client.install.assert_called_once_with(
            "SERIAL123", ["/local/base.apk"], allow_downgrade=True
        )


_QUERY_INTENTS_OUTPUT = (
    "Activities:\n"
    "  ActivityInfo:\n"
    "    name=com.whatsapp.HomeActivity\n"
    "    packageName=com.whatsapp\n"
    "    nonLocalizedLabel=WhatsApp\n"
    "  ActivityInfo:\n"
    "    name=com.google.android.apps.photos.MainActivity\n"
    "    packageName=com.google.android.apps.photos\n"
    "    nonLocalizedLabel=Photos\n"
    "  ActivityInfo:\n"
    "    name=com.example.noLabel.MainActivity\n"
    "    packageName=com.example.noLabel\n"
)


class TestParseLauncherLabels:
    def test_extracts_package_label_pairs(self):
        result = apps.parse_launcher_labels(_QUERY_INTENTS_OUTPUT)
        assert result["com.whatsapp"] == "WhatsApp"
        assert result["com.google.android.apps.photos"] == "Photos"

    def test_skips_packages_without_label(self):
        result = apps.parse_launcher_labels(_QUERY_INTENTS_OUTPUT)
        assert "com.example.noLabel" not in result

    def test_ignores_null_label(self):
        output = "  ActivityInfo:\n    packageName=com.bad\n    nonLocalizedLabel=null\n"
        assert apps.parse_launcher_labels(output) == {}

    def test_first_label_wins_for_duplicate_packages(self):
        output = (
            "  ActivityInfo:\n    packageName=com.pkg\n    nonLocalizedLabel=First\n"
            "  ActivityInfo:\n    packageName=com.pkg\n    nonLocalizedLabel=Second\n"
        )
        result = apps.parse_launcher_labels(output)
        assert result["com.pkg"] == "First"

    def test_empty_output_returns_empty_dict(self):
        assert apps.parse_launcher_labels("") == {}


class TestGetLauncherLabels:
    def test_calls_shell_with_correct_command_and_returns_parsed_labels(self):
        client = MagicMock()
        client.shell.return_value = _QUERY_INTENTS_OUTPUT

        result = apps.get_launcher_labels(client, "SERIAL123")

        client.shell.assert_called_once_with(
            "SERIAL123",
            ["cmd", "activity", "query-intents",
             "-a", "android.intent.action.MAIN",
             "-c", "android.intent.category.LAUNCHER"],
        )
        assert result["com.whatsapp"] == "WhatsApp"

    def test_returns_empty_dict_on_adb_error(self):
        client = MagicMock()
        client.shell.side_effect = RuntimeError("device offline")

        result = apps.get_launcher_labels(client, "SERIAL123")

        assert result == {}


class TestExtractLabelFromApk:
    def test_returns_label_from_badging_output(self, tmp_path, monkeypatch):
        fake_apk = tmp_path / "base.apk"
        fake_apk.write_bytes(b"")

        def fake_run(cmd, **kwargs):
            class R:
                stdout = "application-label:'WhatsApp'\napplication-label-en:'WhatsApp'\n"
                returncode = 0
            return R()

        monkeypatch.setattr(apps.subprocess, "run", fake_run)
        assert apps.extract_label_from_apk("/fake/aapt2", str(fake_apk)) == "WhatsApp"

    def test_returns_none_on_subprocess_error(self, tmp_path, monkeypatch):
        fake_apk = tmp_path / "base.apk"
        fake_apk.write_bytes(b"")
        monkeypatch.setattr(apps.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(OSError("no aapt2")))
        assert apps.extract_label_from_apk("/fake/aapt2", str(fake_apk)) is None

    def test_returns_none_when_label_not_in_output(self, tmp_path, monkeypatch):
        fake_apk = tmp_path / "base.apk"
        fake_apk.write_bytes(b"")

        def fake_run(cmd, **kwargs):
            class R:
                stdout = "package: name='com.example' versionCode='1'\n"
                returncode = 0
            return R()

        monkeypatch.setattr(apps.subprocess, "run", fake_run)
        assert apps.extract_label_from_apk("/fake/aapt2", str(fake_apk)) is None
