"""Tests for droidbridge.modules.storage - Module 5: Storage Analyzer."""

from datetime import datetime
from unittest.mock import MagicMock

from droidbridge.modules import storage
from droidbridge.modules.search import SearchResult


def _ts(year, month=1, day=1):
    return datetime(year, month, day)


DISKSTATS_OUTPUT = (
    "Latency: 1ms [512B Data Write]\n"
    "Recent Disk Write Speed (kB/s) = 4291\n"
    "Data-Free: 31022088K / 236441276K total = 13% free\n"
    "Cache-Free: 31022088K / 236441276K total = 13% free\n"
    "System-Free: 229440K / 5063768K total = 4% free\n"
    "File-based Encryption: true\n"
    "App Size: 32313462784\n"
    "App Data Size: 105749987145\n"
    "App Cache Size: 3418095616\n"
    "Photos Size: 39146213376\n"
    "Videos Size: 22427582464\n"
    "Audio Size: 3150090240\n"
    "Downloads Size: 0\n"
    "System Size: 256000000000\n"
    "Other Size: 86483505152\n"
    'Package Names: ["com.whatsapp","com.android.chrome"]\n'
    "App Sizes: [184619008,447078400]\n"
    "App Data Sizes: [66915028992,784474112]\n"
    "Cache Sizes: [33968128,373264384]\n"
)

DF_OUTPUT = (
    "Filesystem     1K-blocks     Used Available Use% Mounted on\n"
    "/dev/fuse      236441276 205419188  31022088  87% /storage/emulated/0\n"
)


class TestParseDiskstatsCategories:
    def test_parses_all_categories(self):
        categories = storage.parse_diskstats_categories(DISKSTATS_OUTPUT)

        assert categories == {
            "apps": 32313462784,
            "app_data": 105749987145,
            "app_cache": 3418095616,
            "photos": 39146213376,
            "videos": 22427582464,
            "audio": 3150090240,
            "downloads": 0,
            "system": 256000000000,
            "other": 86483505152,
        }

    def test_missing_categories_are_omitted(self):
        output = "App Size: 100\nPhotos Size: 200\n"

        categories = storage.parse_diskstats_categories(output)

        assert categories == {"apps": 100, "photos": 200}


class TestGetStorageOverview:
    def test_combines_df_totals_with_diskstats_categories(self):
        client = MagicMock()

        def fake_shell(serial, command, timeout=None):
            assert serial == "SERIAL123"
            if command[0] == "df":
                return DF_OUTPUT
            if command[:2] == ["dumpsys", "diskstats"]:
                return DISKSTATS_OUTPUT
            raise AssertionError(f"Unexpected shell command: {command}")

        client.shell.side_effect = fake_shell

        overview = storage.get_storage_overview(client, "SERIAL123")

        assert overview.total_kb == 236441276
        assert overview.used_kb == 205419188
        assert overview.free_kb == 31022088
        assert overview.categories["photos"] == 39146213376
        assert overview.categories["apps"] == 32313462784


PM_LIST_SYSTEM_OUTPUT = "package:com.android.chrome\npackage:com.android.settings\n"


class TestParseDiskstatsApps:
    def test_parses_parallel_arrays_into_tuples(self):
        apps = storage.parse_diskstats_apps(DISKSTATS_OUTPUT)

        assert apps == [
            ("com.whatsapp", 184619008, 66915028992, 33968128),
            ("com.android.chrome", 447078400, 784474112, 373264384),
        ]


class TestGetAppStorage:
    def test_combines_diskstats_sizes_with_system_flag(self):
        client = MagicMock()

        def fake_shell(serial, command, timeout=None):
            assert serial == "SERIAL123"
            if command[:2] == ["dumpsys", "diskstats"]:
                return DISKSTATS_OUTPUT
            if command[:3] == ["pm", "list", "packages"] and "-s" in command:
                return PM_LIST_SYSTEM_OUTPUT
            raise AssertionError(f"Unexpected shell command: {command}")

        client.shell.side_effect = fake_shell

        apps = storage.get_app_storage(client, "SERIAL123")

        by_pkg = {a.package: a for a in apps}
        assert by_pkg["com.whatsapp"].apk_size == 184619008
        assert by_pkg["com.whatsapp"].data_size == 66915028992
        assert by_pkg["com.whatsapp"].cache_size == 33968128
        assert by_pkg["com.whatsapp"].is_system is False
        assert by_pkg["com.whatsapp"].total_size == 184619008 + 66915028992 + 33968128

        assert by_pkg["com.android.chrome"].is_system is True


class TestTopSpaceConsumers:
    def test_returns_top_n_by_total_size_descending(self):
        apps = [
            storage.AppStorageInfo("a", apk_size=10, data_size=0, cache_size=0, is_system=False),
            storage.AppStorageInfo("b", apk_size=100, data_size=0, cache_size=0, is_system=False),
            storage.AppStorageInfo("c", apk_size=50, data_size=0, cache_size=0, is_system=False),
        ]

        top = storage.top_space_consumers(apps, n=2)

        assert [a.package for a in top] == ["b", "c"]


class TestFlagLargeCache:
    def test_returns_apps_with_cache_above_threshold(self):
        apps = [
            storage.AppStorageInfo("small", apk_size=0, data_size=0, cache_size=1000, is_system=False),
            storage.AppStorageInfo("big", apk_size=0, data_size=0, cache_size=200_000_000, is_system=False),
        ]

        flagged = storage.flag_large_cache(apps, threshold=100_000_000)

        assert [a.package for a in flagged] == ["big"]


class TestCategorizeMedia:
    def test_groups_by_type_with_count_and_total_size(self):
        results = [
            SearchResult(path="/sdcard/DCIM/a.jpg", size=100, mtime=_ts(2024)),
            SearchResult(path="/sdcard/DCIM/b.png", size=200, mtime=_ts(2024)),
            SearchResult(path="/sdcard/Movies/c.mp4", size=1000, mtime=_ts(2024)),
            SearchResult(path="/sdcard/Music/d.mp3", size=50, mtime=_ts(2024)),
            SearchResult(path="/sdcard/Documents/e.pdf", size=10, mtime=_ts(2024)),
        ]

        categories = storage.categorize_media(results)

        assert categories["photos"] == (2, 300)
        assert categories["videos"] == (1, 1000)
        assert categories["audio"] == (1, 50)
        assert categories["documents"] == (1, 10)


class TestFindLargestFiles:
    def test_returns_top_n_by_size_descending(self):
        results = [
            SearchResult(path="/a", size=10, mtime=_ts(2024)),
            SearchResult(path="/b", size=1000, mtime=_ts(2024)),
            SearchResult(path="/c", size=500, mtime=_ts(2024)),
        ]

        largest = storage.find_largest_files(results, n=2)

        assert [r.path for r in largest] == ["/b", "/c"]


class TestFindDuplicates:
    def test_groups_files_with_same_name_and_size(self):
        results = [
            SearchResult(path="/a/photo.jpg", size=100, mtime=_ts(2024)),
            SearchResult(path="/b/photo.jpg", size=100, mtime=_ts(2024)),
            SearchResult(path="/c/other.jpg", size=200, mtime=_ts(2024)),
        ]

        duplicates = storage.find_duplicates(results)

        assert len(duplicates) == 1
        assert {r.path for r in duplicates[0]} == {"/a/photo.jpg", "/b/photo.jpg"}

    def test_no_duplicates_returns_empty_list(self):
        results = [
            SearchResult(path="/a/photo.jpg", size=100, mtime=_ts(2024)),
            SearchResult(path="/b/photo.jpg", size=200, mtime=_ts(2024)),
        ]

        assert storage.find_duplicates(results) == []


class TestAnalyzeMedia:
    def test_scans_root_and_builds_breakdown(self, monkeypatch):
        results = [
            SearchResult(path="/sdcard/DCIM/a.jpg", size=100, mtime=_ts(2024)),
            SearchResult(path="/sdcard/Movies/b.mp4", size=1000, mtime=_ts(2024)),
        ]

        captured = {}

        def fake_search_files(client, serial, root_path, extensions=None, before=None):
            captured["root_path"] = root_path
            captured["extensions"] = extensions
            captured["before"] = before
            return results

        monkeypatch.setattr(storage.search_module, "search_files", fake_search_files)

        breakdown = storage.analyze_media(MagicMock(), "SERIAL123")

        assert captured["root_path"] == storage.search_module.DEFAULT_ROOT
        assert breakdown.categories["photos"] == (1, 100)
        assert breakdown.categories["videos"] == (1, 1000)
        assert breakdown.total_count == 2
        assert breakdown.total_size == 1100
        assert [r.path for r in breakdown.largest_files] == ["/sdcard/Movies/b.mp4", "/sdcard/DCIM/a.jpg"]
        assert breakdown.duplicates == []


class TestFindLargeFiles:
    def test_searches_with_threshold_and_sorts_by_size_descending(self, monkeypatch):
        results = [
            SearchResult(path="/sdcard/a.zip", size=60_000_000, mtime=_ts(2024)),
            SearchResult(path="/sdcard/b.iso", size=200_000_000, mtime=_ts(2024)),
        ]

        captured = {}

        def fake_search_files(client, serial, root_path, min_size=None):
            captured["root_path"] = root_path
            captured["min_size"] = min_size
            return results

        monkeypatch.setattr(storage.search_module, "search_files", fake_search_files)

        large_files = storage.find_large_files(MagicMock(), "SERIAL123")

        assert captured["root_path"] == storage.search_module.DEFAULT_ROOT
        assert captured["min_size"] == storage.search_module.LARGE_FILE_THRESHOLD
        assert [r.path for r in large_files] == ["/sdcard/b.iso", "/sdcard/a.zip"]

    def test_custom_threshold_is_passed_through(self, monkeypatch):
        captured = {}

        def fake_search_files(client, serial, root_path, min_size=None):
            captured["min_size"] = min_size
            return []

        monkeypatch.setattr(storage.search_module, "search_files", fake_search_files)

        storage.find_large_files(MagicMock(), "SERIAL123", threshold=10_000_000)

        assert captured["min_size"] == 10_000_000


class TestFindThumbnailCaches:
    def test_returns_existing_dirs_with_sizes(self):
        client = MagicMock()

        def fake_shell(serial, command, timeout=None):
            if command.startswith("[ -d"):
                if "DCIM/.thumbnails" in command:
                    return "1\n"
                return "0\n"
            if command.startswith("du -sk"):
                return "12345\t/sdcard/DCIM/.thumbnails\n"
            raise AssertionError(f"Unexpected shell command: {command}")

        client.shell.side_effect = fake_shell

        found = storage.find_thumbnail_caches(client, "SERIAL123")

        assert found == [("/sdcard/DCIM/.thumbnails", 12345 * 1024)]

    def test_returns_empty_list_when_none_exist(self):
        client = MagicMock()
        client.shell.return_value = "0\n"

        assert storage.find_thumbnail_caches(client, "SERIAL123") == []


class TestSuggestCleanup:
    def test_builds_suggestions_from_apps_apks_logs_and_thumbnails(self, monkeypatch):
        apps = [
            storage.AppStorageInfo("big_cache_app", apk_size=0, data_size=0, cache_size=200_000_000, is_system=False),
            storage.AppStorageInfo("small", apk_size=0, data_size=0, cache_size=1000, is_system=False),
        ]

        def fake_search_files(client, serial, root_path, extensions=None, before=None):
            if root_path == storage.DOWNLOAD_DIR:
                return [SearchResult(path="/sdcard/Download/app.apk", size=5_000_000, mtime=_ts(2024))]
            if extensions == ["log"]:
                return [SearchResult(path="/sdcard/old.log", size=1000, mtime=_ts(2020))]
            return []

        monkeypatch.setattr(storage.search_module, "search_files", fake_search_files)
        monkeypatch.setattr(
            storage, "find_thumbnail_caches", lambda client, serial: [("/sdcard/DCIM/.thumbnails", 1_000_000)]
        )

        suggestions = storage.suggest_cleanup(MagicMock(), "SERIAL123", apps=apps)

        titles = [s.title for s in suggestions]
        assert "Clear app caches" in titles
        assert "APK installer files in Downloads" in titles
        assert "Old log files" in titles
        assert "Thumbnail caches" in titles

        cache_suggestion = next(s for s in suggestions if s.title == "Clear app caches")
        assert cache_suggestion.items == ["big_cache_app"]
        assert cache_suggestion.estimated_bytes == 200_000_000

        apk_suggestion = next(s for s in suggestions if s.title == "APK installer files in Downloads")
        assert apk_suggestion.estimated_bytes == 5_000_000
        assert apk_suggestion.items == ["/sdcard/Download/app.apk"]

        thumb_suggestion = next(s for s in suggestions if s.title == "Thumbnail caches")
        assert thumb_suggestion.estimated_bytes == 1_000_000
        assert thumb_suggestion.items == ["/sdcard/DCIM/.thumbnails"]

    def test_no_suggestions_when_nothing_found(self, monkeypatch):
        monkeypatch.setattr(storage.search_module, "search_files", lambda *a, **k: [])
        monkeypatch.setattr(storage, "find_thumbnail_caches", lambda client, serial: [])

        suggestions = storage.suggest_cleanup(MagicMock(), "SERIAL123", apps=[])

        assert suggestions == []
