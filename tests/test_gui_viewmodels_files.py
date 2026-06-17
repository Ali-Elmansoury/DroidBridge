"""Tests for droidbridge.gui.viewmodels.files.FilesViewModel (Phase 6.2).

Uses the synchronous FakeWorker from test_gui_viewmodels_device (no real QThread).
"""

from datetime import datetime
from unittest.mock import MagicMock

from droidbridge.gui import files_ops, preview_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.files import FilesViewModel
from droidbridge.modules.files import FileEntry
from tests.test_gui_viewmodels_device import FakeWorker

SAMPLE_ENTRIES = [
    FileEntry(name="Camera", path="/sdcard/Camera", is_dir=True, is_symlink=False,
              size=4096, mtime=datetime(2023, 8, 5, 22, 56)),
    FileEntry(name="photo.jpg", path="/sdcard/photo.jpg", is_dir=False, is_symlink=False,
              size=24647, mtime=datetime(2023, 8, 1, 10, 0)),
    FileEntry(name=".hidden.txt", path="/sdcard/.hidden.txt", is_dir=False, is_symlink=False,
              size=512, mtime=datetime(2023, 8, 2, 11, 0)),
    FileEntry(name="notes.txt", path="/sdcard/notes.txt", is_dir=False, is_symlink=False,
              size=2048, mtime=datetime(2023, 8, 3, 12, 0)),
]


def _connected_context():
    context = DeviceContext()
    context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
    return context


class TestNavigate:
    def test_success_emits_path_and_entries(self, qtbot, monkeypatch):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: SAMPLE_ENTRIES)

        paths = []
        vm.pathChanged.connect(paths.append)
        rows_events = []
        vm.entriesChanged.connect(rows_events.append)

        vm.navigate("/sdcard")

        assert paths == ["/sdcard"]
        rows = rows_events[0]
        assert [r["name"] for r in rows] == ["Camera", "notes.txt", "photo.jpg"]
        assert rows[0]["is_dir"] is True
        assert rows[0]["path"] == "/sdcard/Camera"
        assert rows[2]["extension"] == "jpg"
        assert rows[2]["entry"] is SAMPLE_ENTRIES[1]
        assert vm.current_path == "/sdcard"

    def test_error_emits_status_and_log(self, qtbot, monkeypatch):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)

        def raise_error(*a, **k):
            raise ValueError("adb shell failed")

        monkeypatch.setattr(files_ops, "list_path", raise_error)

        statuses = []
        vm.statusChanged.connect(statuses.append)

        vm.navigate("/sdcard")

        assert statuses == ["adb shell failed"]


class TestGoUp:
    def test_navigates_to_parent(self, qtbot, monkeypatch):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)

        seen_paths = []

        def fake_list_path(client, serial, path, **kw):
            seen_paths.append(path)
            return SAMPLE_ENTRIES

        monkeypatch.setattr(files_ops, "list_path", fake_list_path)

        vm.navigate("/sdcard/DCIM")
        vm.go_up()

        assert seen_paths == ["/sdcard/DCIM", "/sdcard"]
        assert vm.current_path == "/sdcard"


class TestSetters:
    def test_set_sort_resorts_without_refetching(self, qtbot, monkeypatch):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)
        calls = []

        def fake_list_path(client, serial, path, **kw):
            calls.append(1)
            return SAMPLE_ENTRIES

        monkeypatch.setattr(files_ops, "list_path", fake_list_path)
        vm.navigate("/sdcard")

        rows_events = []
        vm.entriesChanged.connect(rows_events.append)

        vm.set_sort("size", True)

        assert len(calls) == 1  # no new ADB call
        rows = rows_events[-1]
        assert [r["name"] for r in rows] == ["photo.jpg", "Camera", "notes.txt"]

    def test_set_show_hidden_includes_dotfiles(self, qtbot, monkeypatch):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: SAMPLE_ENTRIES)
        vm.navigate("/sdcard")

        rows_events = []
        vm.entriesChanged.connect(rows_events.append)

        vm.set_show_hidden(True)

        rows = rows_events[-1]
        assert ".hidden.txt" in [r["name"] for r in rows]

    def test_set_extension_filter(self, qtbot, monkeypatch):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: SAMPLE_ENTRIES)
        vm.navigate("/sdcard")

        rows_events = []
        vm.entriesChanged.connect(rows_events.append)

        vm.set_extension_filter(["jpg"])

        rows = rows_events[-1]
        assert [r["name"] for r in rows] == ["Camera", "photo.jpg"]

    def test_set_dirs_pass_extension_filter(self, qtbot, monkeypatch):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: SAMPLE_ENTRIES)
        vm.navigate("/sdcard")
        vm.set_extension_filter(["jpg"])

        rows_events = []
        vm.entriesChanged.connect(rows_events.append)

        vm.set_dirs_pass_extension_filter(False)

        rows = rows_events[-1]
        assert [r["name"] for r in rows] == ["photo.jpg"]


class TestSelectEntry:
    def test_previewable_image_emits_image_preview(self, qtbot, monkeypatch):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)
        entry = SAMPLE_ENTRIES[1]  # photo.jpg

        monkeypatch.setattr(preview_ops, "fetch_preview", lambda client, serial, e: "/cache/photo.jpg")

        events = []
        vm.previewChanged.connect(events.append)

        vm.select_entry(entry)

        assert events == [{"kind": "image", "local_path": "/cache/photo.jpg", "entry": entry}]

    def test_directory_emits_info(self, qtbot):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)
        entry = SAMPLE_ENTRIES[0]  # Camera (directory)

        events = []
        vm.previewChanged.connect(events.append)

        vm.select_entry(entry)

        assert events == [{"kind": "info", "entry": entry}]

    def test_none_emits_info(self, qtbot):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)

        events = []
        vm.previewChanged.connect(events.append)

        vm.select_entry(None)

        assert events == [{"kind": "info", "entry": None}]

    def test_stale_generation_is_discarded(self, qtbot):
        vm = FilesViewModel(_connected_context(), worker_factory=FakeWorker)

        events = []
        vm.previewChanged.connect(events.append)

        vm._preview_generation = 5
        vm._on_preview_fetched(generation=3, local_path="/tmp/stale.jpg", entry=None)

        assert events == []
