"""Tests for droidbridge.gui.pages.files.FilesPage (Phase 6.2)."""

from datetime import datetime
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFileDialog

from droidbridge.gui import files_ops, preview_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.files import FilesPage
from droidbridge.gui.viewmodels.files import FilesViewModel
from droidbridge.gui.widgets import delete_flow
from droidbridge.gui.widgets.deselectable_table import DeselectableTableWidget
from droidbridge.modules.files import FileEntry
from droidbridge.utils.format import format_bytes
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


def _row(entry):
    return {
        "entry": entry,
        "name": entry.name,
        "type": "dir" if entry.is_dir else "file",
        "size": entry.size,
        "mtime": entry.mtime,
        "is_dir": entry.is_dir,
        "path": entry.path,
        "extension": entry.extension,
    }


SAMPLE_ROWS = [_row(SAMPLE_ENTRIES[0]), _row(SAMPLE_ENTRIES[1])]


def _make_page():
    context = DeviceContext()
    context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
    vm = FilesViewModel(context, worker_factory=FakeWorker)
    page = FilesPage(vm)
    page.show()  # isVisible() checks require the top-level widget to be shown
    return page, vm, context


class TestEntriesAndPath:
    def test_entries_changed_populates_table(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.entriesChanged.emit(SAMPLE_ROWS)

        assert page.table.rowCount() == 2
        assert page.table.item(0, 0).text() == "Camera"
        assert page.table.item(0, 1).text() == "dir"
        assert page.table.item(1, 0).text() == "photo.jpg"
        assert page.table.item(1, 2).text() == format_bytes(24647)

    def test_path_changed_updates_path_edit(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.pathChanged.emit("/sdcard/DCIM")

        assert page.path_edit.text() == "/sdcard/DCIM"


class TestNavigation:
    def test_quick_jump_button_navigates(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []

        def fake_list_path(client, serial, path, **kw):
            calls.append(path)
            return []

        monkeypatch.setattr(files_ops, "list_path", fake_list_path)

        qtbot.mouseClick(page.quick_jump_buttons["DCIM"], Qt.MouseButton.LeftButton)

        assert calls == [files_ops.QUICK_JUMP_PATHS["DCIM"]]
        assert vm.current_path == files_ops.QUICK_JUMP_PATHS["DCIM"]

    def test_up_button_navigates_to_parent(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []

        def fake_list_path(client, serial, path, **kw):
            calls.append(path)
            return []

        monkeypatch.setattr(files_ops, "list_path", fake_list_path)

        vm.current_path = "/sdcard/DCIM"
        qtbot.mouseClick(page.up_button, Qt.MouseButton.LeftButton)

        assert calls == ["/sdcard"]

    def test_path_edit_enter_navigates(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []

        def fake_list_path(client, serial, path, **kw):
            calls.append(path)
            return []

        monkeypatch.setattr(files_ops, "list_path", fake_list_path)

        page.path_edit.setText("/sdcard/Download")
        qtbot.keyClick(page.path_edit, Qt.Key.Key_Return)

        assert calls == ["/sdcard/Download"]


class TestSortFilterControls:
    def test_changing_sort_hidden_extension_updates_table(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: SAMPLE_ENTRIES)
        vm.navigate("/sdcard")

        names = lambda: [page.table.item(r, 0).text() for r in range(page.table.rowCount())]

        assert names() == ["Camera", "notes.txt", "photo.jpg"]

        page.sort_combo.setCurrentText("size")
        page.reverse_checkbox.setChecked(True)

        assert names() == ["photo.jpg", "Camera", "notes.txt"]

        page.show_hidden_checkbox.setChecked(True)

        assert ".hidden.txt" in names()

        page.extension_edit.setText("jpg")

        assert names() == ["photo.jpg", "Camera"]

    def test_extension_filter_updates_live_as_typed(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: SAMPLE_ENTRIES)
        vm.navigate("/sdcard")

        names = lambda: [page.table.item(r, 0).text() for r in range(page.table.rowCount())]
        assert names() == ["Camera", "notes.txt", "photo.jpg"]

        qtbot.keyClicks(page.extension_edit, "jpg")

        assert names() == ["Camera", "photo.jpg"]

    def test_extension_edit_minimum_width_fits_placeholder(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        metrics = page.extension_edit.fontMetrics()
        placeholder_width = metrics.horizontalAdvance(page.extension_edit.placeholderText())

        assert page.extension_edit.minimumWidth() >= placeholder_width

    def test_dirs_pass_filter_checkbox_checked_by_default(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.dirs_pass_filter_checkbox.isChecked() is True

    def test_unchecking_dirs_pass_filter_hides_directories(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: SAMPLE_ENTRIES)
        vm.navigate("/sdcard")

        names = lambda: [page.table.item(r, 0).text() for r in range(page.table.rowCount())]

        qtbot.keyClicks(page.extension_edit, "jpg")
        assert names() == ["Camera", "photo.jpg"]

        page.dirs_pass_filter_checkbox.setChecked(False)

        assert names() == ["photo.jpg"]


class TestSelection:
    def test_single_selection_calls_select_entry(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)

        monkeypatch.setattr(preview_ops, "fetch_preview", lambda client, serial, e: "/cache/x.jpg")

        events = []
        vm.previewChanged.connect(events.append)

        page.table.selectRow(1)  # photo.jpg

        assert events == [{"kind": "image", "local_path": "/cache/x.jpg"}]
        assert page.pull_selected_button.isEnabled() is True

    def test_multi_selection_calls_select_entry_none(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)

        events = []
        vm.previewChanged.connect(events.append)

        page.table.selectAll()

        assert events == [{"kind": "info", "entry": None}]


class TestSelectionButtons:
    def test_select_all_deselect_all_invert(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)

        qtbot.mouseClick(page.select_all_button, Qt.MouseButton.LeftButton)
        assert {i.row() for i in page.table.selectedIndexes()} == {0, 1}

        qtbot.mouseClick(page.deselect_all_button, Qt.MouseButton.LeftButton)
        assert page.table.selectedIndexes() == []

        page.table.selectRow(0)
        qtbot.mouseClick(page.invert_selection_button, Qt.MouseButton.LeftButton)
        assert {i.row() for i in page.table.selectedIndexes()} == {1}


class TestPreview:
    def test_image_preview_sets_pixmap(self, qtbot, tmp_path):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        img_path = tmp_path / "preview.png"
        QPixmap(4, 4).save(str(img_path))

        vm.previewChanged.emit({"kind": "image", "local_path": str(img_path)})

        assert not page.preview_image_label.pixmap().isNull()
        assert page.preview_image_label.isVisible()
        assert not page.preview_info_label.isVisible()

    def test_large_image_preview_is_scaled_down(self, qtbot, tmp_path):
        """A large photo must not grow the preview label (and thus the window) past
        a fixed cap - it should be scaled down, preserving aspect ratio."""
        from droidbridge.gui.pages.files import PREVIEW_MAX_DIMENSION

        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        img_path = tmp_path / "large.png"
        QPixmap(1600, 1200).save(str(img_path))

        vm.previewChanged.emit({"kind": "image", "local_path": str(img_path)})

        pixmap = page.preview_image_label.pixmap()
        assert pixmap.width() <= PREVIEW_MAX_DIMENSION
        assert pixmap.height() <= PREVIEW_MAX_DIMENSION
        assert pixmap.width() == 4 * pixmap.height() // 3  # 1600x1200 aspect ratio kept

    def test_info_preview_shows_entry_details(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.previewChanged.emit({"kind": "info", "entry": SAMPLE_ENTRIES[1]})

        assert "photo.jpg" in page.preview_info_label.text()
        assert page.preview_info_label.isVisible()
        assert not page.preview_image_label.isVisible()


class TestPullSelected:
    def test_emits_pull_requested(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)  # photo.jpg

        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/dest"))

        events = []
        page.pullRequested.connect(lambda paths, local_dir: events.append((paths, local_dir)))

        qtbot.mouseClick(page.pull_selected_button, Qt.MouseButton.LeftButton)

        assert events == [(["/sdcard/photo.jpg"], "/tmp/dest")]

    def test_no_dir_chosen_does_nothing(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)

        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))

        events = []
        page.pullRequested.connect(lambda paths, local_dir: events.append((paths, local_dir)))

        qtbot.mouseClick(page.pull_selected_button, Qt.MouseButton.LeftButton)

        assert events == []

    def test_disabled_with_no_selection(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)

        assert page.pull_selected_button.isEnabled() is False


class TestRowDoubleClick:
    def test_table_is_deselectable(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert isinstance(page.table, DeselectableTableWidget)

    def test_double_click_directory_navigates(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)  # row 0 = Camera (dir), row 1 = photo.jpg (file)

        calls = []
        monkeypatch.setattr(vm, "navigate", lambda path: calls.append(path))

        page.table.itemDoubleClicked.emit(page.table.item(0, 0))

        assert calls == ["/sdcard/Camera"]

    def test_double_click_file_does_nothing(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)

        calls = []
        monkeypatch.setattr(vm, "navigate", lambda path: calls.append(path))

        page.table.itemDoubleClicked.emit(page.table.item(1, 0))

        assert calls == []


class TestRenameAndDeleteButtons:
    def test_enabled_state_follows_selection(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)

        assert page.rename_button.isEnabled() is False
        assert page.delete_button.isEnabled() is False

        page.table.selectRow(1)
        assert page.rename_button.isEnabled() is True
        assert page.delete_button.isEnabled() is True

        page.table.selectAll()
        assert page.rename_button.isEnabled() is False
        assert page.delete_button.isEnabled() is True

        page.table.clearSelection()
        assert page.rename_button.isEnabled() is False
        assert page.delete_button.isEnabled() is False


class TestRename:
    def test_success_refreshes_listing(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)  # photo.jpg

        monkeypatch.setattr(delete_flow, "run_rename_flow", lambda *a, **k: "/sdcard/renamed.jpg")
        calls = []
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: calls.append(path) or [])

        qtbot.mouseClick(page.rename_button, Qt.MouseButton.LeftButton)

        assert calls == [vm.current_path]

    def test_cancel_does_not_refresh(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)

        monkeypatch.setattr(delete_flow, "run_rename_flow", lambda *a, **k: None)
        calls = []
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: calls.append(path) or [])

        qtbot.mouseClick(page.rename_button, Qt.MouseButton.LeftButton)

        assert calls == []


class TestDelete:
    def test_success_refreshes_listing(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)  # photo.jpg

        monkeypatch.setattr(delete_flow, "run_delete_flow", lambda *a, **k: {"/sdcard/photo.jpg"})
        calls = []
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: calls.append(path) or [])

        qtbot.mouseClick(page.delete_button, Qt.MouseButton.LeftButton)

        assert calls == [vm.current_path]

    def test_nothing_deleted_does_not_refresh(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.entriesChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)

        monkeypatch.setattr(delete_flow, "run_delete_flow", lambda *a, **k: set())
        calls = []
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: calls.append(path) or [])

        qtbot.mouseClick(page.delete_button, Qt.MouseButton.LeftButton)

        assert calls == []


class TestFilesPageContextMenu:
    def test_context_menu_policy_is_custom(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


class TestFilesPagePreviewPath:
    def test_preview_shows_full_path(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        entry = FileEntry(
            name="photo.jpg",
            path="/sdcard/DCIM/Camera/photo.jpg",
            is_dir=False,
            is_symlink=False,
            size=2048,
            mtime=datetime(2024, 6, 1, 12, 0),
            link_target=None,
        )
        page._on_preview_changed({"kind": "entry", "entry": entry})
        assert "/sdcard/DCIM/Camera/photo.jpg" in page.preview_info_label.text()

    def test_preview_path_is_first_line(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        entry = FileEntry(
            name="doc.pdf",
            path="/sdcard/Download/doc.pdf",
            is_dir=False,
            is_symlink=False,
            size=512,
            mtime=datetime(2024, 1, 1),
            link_target=None,
        )
        page._on_preview_changed({"kind": "entry", "entry": entry})
        first_line = page.preview_info_label.text().split("\n")[0]
        assert first_line.startswith("Path:")


class TestFilesPageBreadcrumb:
    def test_breadcrumb_bar_exists_on_page(self, qapp, qtbot):
        from droidbridge.gui.widgets.breadcrumb_bar import BreadcrumbBar
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        assert hasattr(page, "breadcrumb")
        assert isinstance(page.breadcrumb, BreadcrumbBar)

    def test_path_change_updates_breadcrumb(self, qapp, qtbot):
        from PyQt6.QtWidgets import QPushButton
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page._on_path_changed("/sdcard/DCIM")
        bar = page.breadcrumb
        buttons = [bar._layout.itemAt(i).widget() for i in range(bar._layout.count())
                   if isinstance(bar._layout.itemAt(i).widget(), QPushButton)]
        texts = [b.text() for b in buttons]
        assert "DCIM" in texts
