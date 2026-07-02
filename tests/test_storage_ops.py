# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from unittest.mock import MagicMock
from droidbridge.gui import storage_ops
from droidbridge.modules.storage import StorageOverview, AppStorageInfo, MediaBreakdown, CleanupSuggestion
from droidbridge.modules.search import SearchResult
from datetime import datetime


class TestGetOverview:
    def test_formats_totals_and_percent(self, monkeypatch):
        overview = StorageOverview(
            total_kb=1000 * 1024, used_kb=400 * 1024, free_kb=600 * 1024,
            categories={"apps": 100 * 1024 * 1024, "photos": 50 * 1024 * 1024},
        )
        monkeypatch.setattr(storage_ops.storage_module, "get_storage_overview", lambda c, s: overview)
        result = storage_ops.get_overview(MagicMock(), "S1")
        assert result["total_str"] == "1000.0 MB" or "GB" in result["total_str"]
        assert result["percent"] == 40
        assert {"label": "Apps", "size_str": "100.0 MB"} in result["categories"]
        assert {"label": "Photos", "size_str": "50.0 MB"} in result["categories"]

    def test_only_includes_present_categories_in_label_order(self, monkeypatch):
        overview = StorageOverview(
            total_kb=100, used_kb=50, free_kb=50,
            categories={"system": 10, "apps": 20},
        )
        monkeypatch.setattr(storage_ops.storage_module, "get_storage_overview", lambda c, s: overview)
        result = storage_ops.get_overview(MagicMock(), "S1")
        labels = [c["label"] for c in result["categories"]]
        assert labels == ["Apps", "System"]

    def test_zero_total_gives_zero_percent(self, monkeypatch):
        overview = StorageOverview(total_kb=0, used_kb=0, free_kb=0, categories={})
        monkeypatch.setattr(storage_ops.storage_module, "get_storage_overview", lambda c, s: overview)
        result = storage_ops.get_overview(MagicMock(), "S1")
        assert result["percent"] == 0

    def test_excludes_zero_size_categories(self, monkeypatch):
        overview = StorageOverview(
            total_kb=100, used_kb=50, free_kb=50,
            categories={"apps": 20, "downloads": 0},
        )
        monkeypatch.setattr(storage_ops.storage_module, "get_storage_overview", lambda c, s: overview)
        result = storage_ops.get_overview(MagicMock(), "S1")
        labels = [c["label"] for c in result["categories"]]
        assert labels == ["Apps"]


class TestGetApps:
    def _apps(self):
        return [
            AppStorageInfo(package="com.a", apk_size=10, data_size=20, cache_size=5, is_system=False),
            AppStorageInfo(package="com.b", apk_size=100, data_size=200, cache_size=50, is_system=True),
        ]

    def test_sorted_descending_by_total_size(self, monkeypatch):
        monkeypatch.setattr(storage_ops.storage_module, "get_app_storage", lambda c, s: self._apps())
        result = storage_ops.get_apps(MagicMock(), "S1")
        assert [r["package"] for r in result] == ["com.b", "com.a"]
        assert result[0]["kind"] == "system"
        assert result[1]["kind"] == "user"

    def test_filter_kind_system(self, monkeypatch):
        monkeypatch.setattr(storage_ops.storage_module, "get_app_storage", lambda c, s: self._apps())
        result = storage_ops.get_apps(MagicMock(), "S1", filter_kind="system")
        assert [r["package"] for r in result] == ["com.b"]

    def test_filter_kind_user(self, monkeypatch):
        monkeypatch.setattr(storage_ops.storage_module, "get_app_storage", lambda c, s: self._apps())
        result = storage_ops.get_apps(MagicMock(), "S1", filter_kind="user")
        assert [r["package"] for r in result] == ["com.a"]


class TestGetMedia:
    def test_shapes_categories_largest_and_duplicates(self, monkeypatch):
        r1 = SearchResult(path="/sdcard/a.jpg", size=300, mtime=datetime(2024, 1, 1))
        r2 = SearchResult(path="/sdcard/b/a.jpg", size=300, mtime=datetime(2024, 1, 1))
        r3 = SearchResult(path="/sdcard/big.mp4", size=900, mtime=datetime(2024, 1, 1))
        breakdown = MediaBreakdown(
            categories={"photos": (2, 600), "videos": (1, 900)},
            largest_files=[r3, r1],
            duplicates=[[r1, r2]],
            total_count=3,
            total_size=1500,
        )
        monkeypatch.setattr(storage_ops.storage_module, "analyze_media", lambda c, s, root, before=None: breakdown)
        result = storage_ops.get_media(MagicMock(), "S1", "/sdcard")
        assert result["total_count"] == 3
        assert {"type": "photos", "count": 2, "size_str": "600 B"} in result["categories"]
        assert result["largest_files"][0]["path"] == "/sdcard/big.mp4"
        assert result["duplicate_groups"][0]["name"] == "a.jpg"
        assert result["duplicate_groups"][0]["count"] == 2
        assert set(result["duplicate_groups"][0]["paths"]) == {"/sdcard/a.jpg", "/sdcard/b/a.jpg"}
        assert result["duplicate_overflow"] == 0

    def test_caps_duplicate_groups_at_ten_and_reports_overflow(self, monkeypatch):
        groups = []
        for i in range(12):
            a = SearchResult(path=f"/sdcard/{i}/x.jpg", size=100, mtime=datetime(2024, 1, 1))
            b = SearchResult(path=f"/sdcard/{i}/y/x.jpg", size=100, mtime=datetime(2024, 1, 1))
            groups.append([a, b])
        breakdown = MediaBreakdown(categories={}, largest_files=[], duplicates=groups, total_count=24, total_size=2400)
        monkeypatch.setattr(storage_ops.storage_module, "analyze_media", lambda c, s, root, before=None: breakdown)
        result = storage_ops.get_media(MagicMock(), "S1", "/sdcard")
        assert len(result["duplicate_groups"]) == 10
        assert result["duplicate_overflow"] == 2

    def test_passes_before_through(self, monkeypatch):
        captured = {}

        def fake_analyze(c, s, root, before=None):
            captured["before"] = before
            return MediaBreakdown(categories={}, largest_files=[], duplicates=[], total_count=0, total_size=0)

        monkeypatch.setattr(storage_ops.storage_module, "analyze_media", fake_analyze)
        before = datetime(2024, 6, 1)
        storage_ops.get_media(MagicMock(), "S1", "/sdcard", before=before)
        assert captured["before"] == before


class TestGetLargeFiles:
    def test_formats_rows(self, monkeypatch):
        results = [SearchResult(path="/sdcard/big.bin", size=123456789, mtime=datetime(2024, 3, 4, 5, 6))]
        monkeypatch.setattr(storage_ops.storage_module, "find_large_files", lambda c, s, root: results)
        result = storage_ops.get_large_files(MagicMock(), "S1", "/sdcard")
        assert result[0]["path"] == "/sdcard/big.bin"
        assert result[0]["modified_str"] == "2024-03-04 05:06"

    def test_passes_threshold_through_when_given(self, monkeypatch):
        captured = {}

        def fake_find(c, s, root, threshold=None):
            captured["threshold"] = threshold
            return []

        monkeypatch.setattr(storage_ops.storage_module, "find_large_files", fake_find)
        storage_ops.get_large_files(MagicMock(), "S1", "/sdcard", threshold=12345)
        assert captured["threshold"] == 12345

    def test_omits_threshold_kwarg_when_none(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            storage_ops.storage_module, "find_large_files",
            lambda c, s, root: calls.append(("no-threshold", root)) or [],
        )
        storage_ops.get_large_files(MagicMock(), "S1", "/sdcard")
        assert calls == [("no-threshold", "/sdcard")]


class TestGetCleanupSuggestions:
    def test_formats_suggestions_and_total(self, monkeypatch):
        suggestions = [
            CleanupSuggestion(title="Clear app caches", description="2 apps", estimated_bytes=1024, items=["com.a", "com.b"]),
            CleanupSuggestion(title="Old logs", description="1 file", estimated_bytes=2048, items=["/sdcard/a.log"]),
        ]
        monkeypatch.setattr(storage_ops.storage_module, "suggest_cleanup", lambda c, s: suggestions)
        result = storage_ops.get_cleanup_suggestions(MagicMock(), "S1")
        assert result["suggestions"][0]["title"] == "Clear app caches"
        assert result["suggestions"][0]["item_count"] == 2
        assert result["suggestions"][0]["items"] == ["com.a", "com.b"]
        assert result["suggestions"][0]["item_overflow"] == 0
        assert result["suggestions"][0]["estimated_bytes_str"] == "1.0 KB"
        assert result["total_str"] == "3.0 KB"

    def test_caps_items_at_ten_and_reports_overflow(self, monkeypatch):
        items = [f"com.app{i}" for i in range(15)]
        suggestions = [
            CleanupSuggestion(title="Clear app caches", description="15 apps", estimated_bytes=1024, items=items),
        ]
        monkeypatch.setattr(storage_ops.storage_module, "suggest_cleanup", lambda c, s: suggestions)
        result = storage_ops.get_cleanup_suggestions(MagicMock(), "S1")
        assert result["suggestions"][0]["item_count"] == 15
        assert len(result["suggestions"][0]["items"]) == 10
        assert result["suggestions"][0]["item_overflow"] == 5

    def test_empty_suggestions_gives_zero_total(self, monkeypatch):
        monkeypatch.setattr(storage_ops.storage_module, "suggest_cleanup", lambda c, s: [])
        result = storage_ops.get_cleanup_suggestions(MagicMock(), "S1")
        assert result["suggestions"] == []
        assert result["total_str"] == "0 B"
