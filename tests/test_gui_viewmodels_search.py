"""Tests for droidbridge.gui.viewmodels.search.SearchViewModel (Phase 6.2)."""

from datetime import datetime
from unittest.mock import MagicMock

from droidbridge.gui import files_ops, search_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.search import SearchViewModel
from droidbridge.modules.files import FileEntry
from droidbridge.modules.search import SearchResult
from tests.test_gui_viewmodels_device import FakeWorker

SAMPLE_RESULTS = [
    SearchResult(path="/sdcard/DCIM/a.jpg", size=100, mtime=datetime(2023, 8, 1, 10, 0)),
    SearchResult(path="/sdcard/DCIM/b.jpg", size=200, mtime=datetime(2023, 8, 2, 10, 0)),
]


def _connected_context():
    context = DeviceContext()
    context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
    return context


class TestSearch:
    def test_success_emits_results(self, qtbot, monkeypatch):
        vm = SearchViewModel(_connected_context(), worker_factory=FakeWorker)

        calls = []

        def fake_run_search(client, serial, root, **kwargs):
            calls.append((root, kwargs))
            return SAMPLE_RESULTS

        monkeypatch.setattr(search_ops, "run_search", fake_run_search)

        events = []
        vm.resultsChanged.connect(events.append)

        vm.search(root="/sdcard", name="jpg", extensions=None, min_size_str="", max_size_str="",
                   after=None, before=None, preset=None, sort_by="path", reverse=False)

        rows = events[0]
        assert [r["path"] for r in rows] == ["/sdcard/DCIM/a.jpg", "/sdcard/DCIM/b.jpg"]
        assert rows[0]["size"] == 100
        assert rows[0]["extension"] == "jpg"
        assert rows[0]["result"] is SAMPLE_RESULTS[0]
        assert calls == [("/sdcard", {
            "name": "jpg", "extensions": None, "min_size": None, "max_size": None,
            "after": None, "before": None, "preset": None, "sort_by": "path", "reverse": False,
        })]

    def test_parses_min_max_size(self, qtbot, monkeypatch):
        vm = SearchViewModel(_connected_context(), worker_factory=FakeWorker)

        captured = {}

        def fake_run_search(client, serial, root, **kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(search_ops, "run_search", fake_run_search)

        vm.search(root="/sdcard", name=None, extensions=None, min_size_str="10MB", max_size_str="1GB",
                   after=None, before=None, preset=None, sort_by="path", reverse=False)

        assert captured["min_size"] == 10 * 1024 * 1024
        assert captured["max_size"] == 1024 ** 3

    def test_invalid_size_emits_status_error_without_searching(self, qtbot, monkeypatch):
        vm = SearchViewModel(_connected_context(), worker_factory=FakeWorker)

        called = []
        monkeypatch.setattr(search_ops, "run_search", lambda *a, **k: called.append(1))

        statuses = []
        vm.statusChanged.connect(statuses.append)

        vm.search(root="/sdcard", name=None, extensions=None, min_size_str="not-a-size", max_size_str="",
                   after=None, before=None, preset=None, sort_by="path", reverse=False)

        assert called == []
        assert statuses == ["Invalid size: 'not-a-size'"]

    def test_error_emits_status_and_log(self, qtbot, monkeypatch):
        vm = SearchViewModel(_connected_context(), worker_factory=FakeWorker)

        def raise_error(*a, **k):
            raise ValueError("adb shell failed")

        monkeypatch.setattr(search_ops, "run_search", raise_error)

        statuses = []
        vm.statusChanged.connect(statuses.append)

        vm.search(root="/sdcard", name=None, extensions=None, min_size_str="", max_size_str="",
                   after=None, before=None, preset=None, sort_by="path", reverse=False)

        assert statuses == ["adb shell failed"]


class TestSetSort:
    def test_resorts_without_research(self, qtbot, monkeypatch):
        vm = SearchViewModel(_connected_context(), worker_factory=FakeWorker)

        calls = []

        def fake_run_search(client, serial, root, **kwargs):
            calls.append(1)
            return SAMPLE_RESULTS

        monkeypatch.setattr(search_ops, "run_search", fake_run_search)

        vm.search(root="/sdcard", name=None, extensions=None, min_size_str="", max_size_str="",
                   after=None, before=None, preset=None, sort_by="path", reverse=False)

        events = []
        vm.resultsChanged.connect(events.append)

        vm.set_sort("size", True)

        assert len(calls) == 1  # no new search
        rows = events[-1]
        assert [r["size"] for r in rows] == [200, 100]


class TestBrowseRoot:
    def test_browse_root_emits_subdirs_only(self, qtbot, monkeypatch):
        vm = SearchViewModel(_connected_context(), worker_factory=FakeWorker)

        entries = [
            FileEntry(name="DCIM", path="/sdcard/DCIM", is_dir=True, is_symlink=False,
                      size=4096, mtime=datetime(2023, 8, 1, 10, 0)),
            FileEntry(name="notes.txt", path="/sdcard/notes.txt", is_dir=False, is_symlink=False,
                      size=10, mtime=datetime(2023, 8, 1, 10, 0)),
            FileEntry(name="Download", path="/sdcard/Download", is_dir=True, is_symlink=False,
                      size=4096, mtime=datetime(2023, 8, 1, 10, 0)),
        ]
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: entries)

        events = []
        vm.rootSubdirsChanged.connect(lambda path, subdirs: events.append((path, subdirs)))

        vm.browse_root("/sdcard")

        assert events == [("/sdcard", ["DCIM", "Download"])]
