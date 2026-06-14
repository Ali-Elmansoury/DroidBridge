"""Tests for droidbridge.gui.pages.search.SearchPage (Phase 6.2)."""

from datetime import date, datetime
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QHeaderView

from droidbridge.gui import files_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.search import SearchPage
from droidbridge.gui.viewmodels.search import SearchViewModel
from droidbridge.gui.widgets import delete_flow
from droidbridge.gui.widgets.deselectable_table import DeselectableTableWidget
from droidbridge.modules import search as search_module
from droidbridge.modules.files import FileEntry
from droidbridge.modules.search import SearchResult
from droidbridge.utils.format import format_bytes
from tests.test_gui_viewmodels_device import FakeWorker

SAMPLE_RESULTS = [
    SearchResult(path="/sdcard/DCIM/a.jpg", size=100, mtime=datetime(2023, 8, 1, 10, 0)),
    SearchResult(path="/sdcard/DCIM/b.jpg", size=200, mtime=datetime(2023, 8, 2, 10, 0)),
]


def _row(result):
    return {
        "result": result,
        "name": result.name,
        "path": result.path,
        "size": result.size,
        "mtime": result.mtime,
        "extension": result.extension,
    }


SAMPLE_ROWS = [_row(r) for r in SAMPLE_RESULTS]


def _make_page(connected=True):
    context = DeviceContext()
    if connected:
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
    vm = SearchViewModel(context, worker_factory=FakeWorker)
    page = SearchPage(vm)
    return page, vm, context


class TestDefaults:
    def test_root_defaults_to_default_root(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.root_edit.text() == search_module.DEFAULT_ROOT

    def test_preset_combo_contains_presets_and_none(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        items = [page.preset_combo.itemText(i) for i in range(page.preset_combo.count())]
        assert items == ["None"] + list(search_module.PRESET_NAMES)

    def test_date_edits_disabled_until_checkbox_checked(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.after_date_edit.isEnabled() is False
        assert page.before_date_edit.isEnabled() is False

        page.after_checkbox.setChecked(True)
        assert page.after_date_edit.isEnabled() is True


class TestResultsTable:
    def test_results_changed_populates_table(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.resultsChanged.emit(SAMPLE_ROWS)

        assert page.table.rowCount() == 2
        assert page.table.item(0, 0).text() == "/sdcard/DCIM/a.jpg"
        assert page.table.item(0, 1).text() == format_bytes(100)

    def test_path_column_stretches_to_fill_available_space(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        header = page.table.horizontalHeader()
        assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
        assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.ResizeToContents
        assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.ResizeToContents

    def test_path_cell_shows_full_path_in_tooltip(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.resultsChanged.emit(SAMPLE_ROWS)

        assert page.table.item(0, 0).toolTip() == "/sdcard/DCIM/a.jpg"

    def test_clear_results_button_empties_table_and_disables_pull(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(0)
        assert page.table.rowCount() == 2
        assert page.pull_selected_button.isEnabled() is True

        qtbot.mouseClick(page.clear_results_button, Qt.MouseButton.LeftButton)

        assert page.table.rowCount() == 0
        assert page._rows == []
        assert page.pull_selected_button.isEnabled() is False


class TestSearchButton:
    def test_search_button_calls_viewmodel_search_with_form_fields(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))

        page.root_edit.setText("/sdcard/DCIM")
        page.name_edit.setText("vacation")
        page.extensions_edit.setText("jpg, png")
        page.min_size_edit.setText("10MB")
        page.max_size_edit.setText("1GB")
        page.after_checkbox.setChecked(True)
        page.after_date_edit.setDate(date(2023, 1, 1))
        page.sort_combo.setCurrentText("size")
        page.reverse_checkbox.setChecked(True)

        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)

        assert calls == [{
            "root": "/sdcard/DCIM", "name": "vacation", "extensions": ["jpg", "png"],
            "min_size_str": "10MB", "max_size_str": "1GB",
            "after": date(2023, 1, 1), "before": None,
            "preset": None, "sort_by": "size", "reverse": True,
        }]

    def test_preset_selection_passed_through(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))

        page.preset_combo.setCurrentText("whatsapp")

        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)

        assert calls[0]["preset"] == "whatsapp"


class TestSortControls:
    def test_changing_sort_calls_set_sort(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []
        monkeypatch.setattr(vm, "set_sort", lambda by, reverse: calls.append((by, reverse)))

        page.sort_combo.setCurrentText("size")
        assert calls == [("size", False)]

        page.reverse_checkbox.setChecked(True)
        assert calls[-1] == ("size", True)


class TestSelectionButtons:
    def test_select_all_deselect_all_invert(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)

        qtbot.mouseClick(page.select_all_button, Qt.MouseButton.LeftButton)
        assert {i.row() for i in page.table.selectedIndexes()} == {0, 1}

        qtbot.mouseClick(page.deselect_all_button, Qt.MouseButton.LeftButton)
        assert page.table.selectedIndexes() == []

        page.table.selectRow(0)
        qtbot.mouseClick(page.invert_selection_button, Qt.MouseButton.LeftButton)
        assert {i.row() for i in page.table.selectedIndexes()} == {1}


class TestPullSelected:
    def test_disabled_with_no_selection(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)

        assert page.pull_selected_button.isEnabled() is False

    def test_emits_pull_requested(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)

        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/dest"))

        events = []
        page.pullRequested.connect(lambda paths, local_dir: events.append((paths, local_dir)))

        qtbot.mouseClick(page.pull_selected_button, Qt.MouseButton.LeftButton)

        assert events == [(["/sdcard/DCIM/b.jpg"], "/tmp/dest")]


class TestTableType:
    def test_table_is_deselectable(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert isinstance(page.table, DeselectableTableWidget)


def _dir_entry(name):
    return FileEntry(name=name, path=f"/x/{name}", is_dir=True, is_symlink=False,
                      size=4096, mtime=datetime(2023, 8, 1, 10, 0))


def _file_entry(name):
    return FileEntry(name=name, path=f"/x/{name}", is_dir=False, is_symlink=False,
                      size=10, mtime=datetime(2023, 8, 1, 10, 0))


class TestRootBrowseCombo:
    def test_combo_has_label_and_tooltip(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.root_browse_label.text() == "Browse:"
        assert page.root_browse_combo.toolTip() != ""

    def test_combo_populates_with_subdirs_on_init_without_parent_entry(self, qtbot, monkeypatch):
        entries = [_dir_entry("DCIM"), _file_entry("notes.txt"), _dir_entry("Download")]
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: entries)

        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        items = [page.root_browse_combo.itemText(i) for i in range(page.root_browse_combo.count())]
        assert items == ["DCIM", "Download"]

    def test_selecting_subdir_drills_down_and_updates_root_edit(self, qtbot, monkeypatch):
        def fake_list_path(client, serial, path, **kw):
            if path == "/sdcard/DCIM":
                return [_dir_entry("Camera"), _file_entry("photo.jpg")]
            return [_dir_entry("DCIM"), _dir_entry("Download")]

        monkeypatch.setattr(files_ops, "list_path", fake_list_path)

        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        page.root_browse_combo.activated.emit(0)  # "DCIM"

        assert page.root_edit.text() == "/sdcard/DCIM"
        items = [page.root_browse_combo.itemText(i) for i in range(page.root_browse_combo.count())]
        assert items == ["..", "Camera"]

    def test_selecting_parent_entry_navigates_up(self, qtbot, monkeypatch):
        def fake_list_path(client, serial, path, **kw):
            if path == "/sdcard/DCIM":
                return [_dir_entry("Camera")]
            return [_dir_entry("DCIM"), _dir_entry("Download")]

        monkeypatch.setattr(files_ops, "list_path", fake_list_path)

        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.browse_root("/sdcard/DCIM")  # drill down without going through the combo
        assert [page.root_browse_combo.itemText(i) for i in range(page.root_browse_combo.count())] == ["..", "Camera"]

        page.root_browse_combo.activated.emit(0)  # ".."

        assert page.root_edit.text() == "/sdcard"
        items = [page.root_browse_combo.itemText(i) for i in range(page.root_browse_combo.count())]
        assert items == ["DCIM", "Download"]

    def test_init_while_disconnected_does_not_populate_or_error(self, qtbot, monkeypatch):
        calls = []
        monkeypatch.setattr(files_ops, "list_path", lambda *a, **kw: calls.append(1))

        page, _vm, _context = _make_page(connected=False)
        qtbot.addWidget(page)

        assert calls == []
        assert page.root_browse_combo.count() == 0

    def test_connecting_after_init_populates_combo(self, qtbot, monkeypatch):
        entries = [_dir_entry("DCIM"), _dir_entry("Download")]
        monkeypatch.setattr(files_ops, "list_path", lambda client, serial, path, **kw: entries)

        page, _vm, context = _make_page(connected=False)
        qtbot.addWidget(page)

        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")

        items = [page.root_browse_combo.itemText(i) for i in range(page.root_browse_combo.count())]
        assert items == ["DCIM", "Download"]

    def test_editing_root_path_refreshes_combo(self, qtbot, monkeypatch):
        def fake_list_path(client, serial, path, **kw):
            if path == "/sdcard/DCIM":
                return [_dir_entry("Camera")]
            return [_dir_entry("DCIM"), _dir_entry("Download")]

        monkeypatch.setattr(files_ops, "list_path", fake_list_path)

        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        page.root_edit.setText("/sdcard/DCIM")
        page.root_edit.editingFinished.emit()

        items = [page.root_browse_combo.itemText(i) for i in range(page.root_browse_combo.count())]
        assert items == ["..", "Camera"]


class TestRenameAndDeleteButtons:
    def test_enabled_state_follows_selection(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)

        assert page.rename_button.isEnabled() is False
        assert page.delete_button.isEnabled() is False

        page.table.selectRow(1)
        assert page.rename_button.isEnabled() is True
        assert page.delete_button.isEnabled() is True

        page.table.selectAll()
        assert page.rename_button.isEnabled() is False
        assert page.delete_button.isEnabled() is True


class TestRename:
    def test_success_updates_row_path(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)  # /sdcard/DCIM/b.jpg

        monkeypatch.setattr(delete_flow, "run_rename_flow", lambda *a, **k: "/sdcard/DCIM/renamed.jpg")

        qtbot.mouseClick(page.rename_button, Qt.MouseButton.LeftButton)

        assert page._rows[1]["path"] == "/sdcard/DCIM/renamed.jpg"
        assert page.table.item(1, 0).text() == "/sdcard/DCIM/renamed.jpg"

    def test_cancel_leaves_row_unchanged(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)

        monkeypatch.setattr(delete_flow, "run_rename_flow", lambda *a, **k: None)

        qtbot.mouseClick(page.rename_button, Qt.MouseButton.LeftButton)

        assert page._rows[1]["path"] == "/sdcard/DCIM/b.jpg"
        assert page.table.item(1, 0).text() == "/sdcard/DCIM/b.jpg"


class TestDelete:
    def test_success_removes_deleted_rows(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)  # /sdcard/DCIM/b.jpg

        monkeypatch.setattr(delete_flow, "run_delete_flow", lambda *a, **k: {"/sdcard/DCIM/b.jpg"})

        qtbot.mouseClick(page.delete_button, Qt.MouseButton.LeftButton)

        assert [row["path"] for row in page._rows] == ["/sdcard/DCIM/a.jpg"]
        assert page.table.rowCount() == 1
        assert page.table.item(0, 0).text() == "/sdcard/DCIM/a.jpg"

    def test_nothing_deleted_leaves_rows_unchanged(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(1)

        monkeypatch.setattr(delete_flow, "run_delete_flow", lambda *a, **k: set())

        qtbot.mouseClick(page.delete_button, Qt.MouseButton.LeftButton)

        assert len(page._rows) == 2
        assert page.table.rowCount() == 2
