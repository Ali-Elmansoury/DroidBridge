"""Tests for droidbridge.gui.pages.search.SearchPage (Phase 6.2)."""

from datetime import date, datetime
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFileDialog, QHeaderView

from droidbridge.gui import files_ops, search_ops
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
            "name_regex": None, "mime": None,
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


class TestExtensionColumn:
    def test_columns_include_extension(self):
        from droidbridge.gui.pages.search import _COLUMNS
        assert "Extension" in _COLUMNS

    def test_populate_table_sets_extension_cell(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        from droidbridge.gui.pages.search import _COLUMNS
        rows = [{"path": "/sdcard/photo.jpg", "name": "photo.jpg", "size": 1000,
                 "mtime": datetime(2024, 1, 1), "extension": "jpg",
                 "result": MagicMock()}]
        vm.resultsChanged.emit(rows)
        ext_col = list(_COLUMNS).index("Extension")
        assert page.table.item(0, ext_col).text() == "jpg"

    def test_no_extension_shows_none_label(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        from droidbridge.gui.pages.search import _COLUMNS
        rows = [{"path": "/sdcard/noext", "name": "noext", "size": 100,
                 "mtime": datetime(2024, 1, 1), "extension": "",
                 "result": MagicMock()}]
        vm.resultsChanged.emit(rows)
        ext_col = list(_COLUMNS).index("Extension")
        assert page.table.item(0, ext_col).text() == "(none)"


class TestSearchPageTooltips:
    def test_name_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.name_edit.toolTip() != ""

    def test_extensions_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.extensions_edit.toolTip() != ""

    def test_min_size_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.min_size_edit.toolTip() != ""

    def test_max_size_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.max_size_edit.toolTip() != ""

    def test_after_checkbox_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.after_checkbox.toolTip() != ""

    def test_after_date_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.after_date_edit.toolTip() != ""

    def test_before_checkbox_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.before_checkbox.toolTip() != ""

    def test_before_date_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.before_date_edit.toolTip() != ""

    def test_preset_combo_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.preset_combo.toolTip() != ""

    def test_sort_combo_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.sort_combo.toolTip() != ""

    def test_reverse_checkbox_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.reverse_checkbox.toolTip() != ""

    def test_search_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.search_button.toolTip() != ""

    def test_select_all_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.select_all_button.toolTip() != ""

    def test_deselect_all_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.deselect_all_button.toolTip() != ""

    def test_invert_selection_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.invert_selection_button.toolTip() != ""

    def test_clear_results_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.clear_results_button.toolTip() != ""

    def test_rename_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.rename_button.toolTip() != ""

    def test_delete_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.delete_button.toolTip() != ""

    def test_pull_selected_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.pull_selected_button.toolTip() != ""

    def test_export_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.export_button.toolTip() != ""


class TestSearchPageShortcuts:
    def test_f5_runs_search(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        page.show()

        calls = []
        monkeypatch.setattr(vm, "search", lambda **k: calls.append(1))

        qtbot.keyClick(page, Qt.Key.Key_F5)

        assert calls

    def test_escape_clears_selection(self, qtbot):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        page.show()
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(0)
        assert page.table.selectedIndexes()

        qtbot.keyClick(page, Qt.Key.Key_Escape)

        assert page.table.selectedIndexes() == []

    def test_ctrl_shift_c_copies_path(self, qtbot):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        page.show()
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(0)

        qtbot.keyClick(
            page,
            Qt.Key.Key_C,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
        )

        assert QApplication.clipboard().text() == "/sdcard/DCIM/a.jpg"

    def test_f2_triggers_rename(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        page.show()
        vm.resultsChanged.emit(SAMPLE_ROWS)

        calls = []
        monkeypatch.setattr(page, "_on_rename", lambda: calls.append(1))

        page.table.setFocus()
        qtbot.keyClick(page.table, Qt.Key.Key_F2)

        assert calls

    def test_delete_key_triggers_delete(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        page.show()
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page.table.selectRow(0)

        calls = []
        monkeypatch.setattr(delete_flow, "run_delete_flow", lambda *a, **k: calls.append(1) or set())

        qtbot.keyClick(page.table, Qt.Key.Key_Delete)

        assert calls


class TestExportButton:
    def test_export_button_exists_and_disabled_initially(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        assert hasattr(page, "export_button")
        assert not page.export_button.isEnabled()

    def test_export_button_enabled_after_results(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)
        assert page.export_button.isEnabled()

    def test_export_button_disabled_after_clear(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        vm.resultsChanged.emit(SAMPLE_ROWS)
        page._on_clear_results()
        assert not page.export_button.isEnabled()

    def test_export_csv_writes_file(self, qtbot, tmp_path):
        import csv
        from unittest.mock import patch
        from PyQt6.QtWidgets import QMessageBox

        page, vm, _context = _make_page()
        qtbot.addWidget(page)
        rows = [{"path": "/sdcard/photo.jpg", "name": "photo.jpg", "size": 1000,
                 "mtime": datetime(2024, 6, 1, 12, 0), "extension": "jpg",
                 "result": MagicMock()}]
        vm.resultsChanged.emit(rows)

        out_path = str(tmp_path / "results.csv")
        with patch("droidbridge.gui.pages.search.QFileDialog.getSaveFileName",
                   return_value=(out_path, "CSV (*.csv)")):
            with patch("droidbridge.gui.pages.search.QMessageBox.information"):
                page._on_export_clicked()

        with open(out_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            data = next(reader)
        assert header == ["path", "size", "date", "extension"]
        assert data[0] == "/sdcard/photo.jpg"
        assert data[3] == "jpg"


class TestSearchViewModelNewParams:
    def test_name_regex_passed_to_run_search(self, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = SearchViewModel(context, worker_factory=FakeWorker)

        calls = []
        monkeypatch.setattr(search_ops, "run_search", lambda *a, **kw: calls.append(kw) or [])

        vm.search(
            root="/sdcard", name=None, extensions=None,
            min_size_str="", max_size_str="", after=None, before=None,
            preset=None, sort_by="path", reverse=False,
            name_regex="IMG_.*\\.jpg",
        )
        assert calls[0].get("name_regex") == "IMG_.*\\.jpg"

    def test_mime_resolved_to_extensions_before_run_search(self, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = SearchViewModel(context, worker_factory=FakeWorker)

        calls = []
        monkeypatch.setattr(search_ops, "run_search", lambda *a, **kw: calls.append(kw) or [])

        vm.search(
            root="/sdcard", name=None, extensions=None,
            min_size_str="", max_size_str="", after=None, before=None,
            preset=None, sort_by="path", reverse=False,
            mime="image",
        )
        assert calls[0]["extensions"] == search_module.mime_to_extensions("image")

    def test_mime_none_leaves_extensions_unchanged(self, monkeypatch):
        context = DeviceContext()
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
        vm = SearchViewModel(context, worker_factory=FakeWorker)

        calls = []
        monkeypatch.setattr(search_ops, "run_search", lambda *a, **kw: calls.append(kw) or [])

        vm.search(
            root="/sdcard", name=None, extensions=["jpg"],
            min_size_str="", max_size_str="", after=None, before=None,
            preset=None, sort_by="path", reverse=False,
            mime=None,
        )
        assert calls[0]["extensions"] == ["jpg"]


class TestNameModeToggle:
    def test_name_mode_combo_exists_with_glob_default(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert hasattr(page, "name_mode_combo")
        assert page.name_mode_combo.currentText() == "Glob"

    def test_name_mode_combo_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.name_mode_combo.toolTip() != ""

    def test_name_mode_glob_placeholder_and_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert "*.jpg" in page.name_edit.placeholderText()
        assert "glob" in page.name_edit.toolTip().lower()

    def test_name_mode_switch_to_regex_changes_placeholder_and_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        page.name_mode_combo.setCurrentText("Regex")
        assert "IMG_" in page.name_edit.placeholderText()
        assert "regular expression" in page.name_edit.toolTip().lower()

    def test_search_glob_mode_passes_name_not_name_regex(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        calls = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))
        page.name_mode_combo.setCurrentText("Glob")
        page.name_edit.setText("vacation")
        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)
        assert calls[0]["name"] == "vacation"
        assert calls[0]["name_regex"] is None

    def test_search_regex_mode_passes_name_regex_not_name(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        calls = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))
        page.name_mode_combo.setCurrentText("Regex")
        page.name_edit.setText("IMG_.*\\.jpg")
        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)
        assert calls[0]["name_regex"] == "IMG_.*\\.jpg"
        assert calls[0]["name"] is None


class TestMimeDropdown:
    def test_mime_combo_exists_with_dash_default(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert hasattr(page, "mime_combo")
        assert page.mime_combo.currentText() == "—"

    def test_mime_combo_has_six_items(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        items = [page.mime_combo.itemText(i) for i in range(page.mime_combo.count())]
        assert items == ["—", "image", "video", "audio", "document", "archive"]

    def test_mime_combo_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.mime_combo.toolTip() != ""

    def test_extensions_edit_tooltip_mentions_mime(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert "mime" in page.extensions_edit.toolTip().lower()

    def test_search_with_mime_passes_mime_to_viewmodel(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        calls = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))
        page.mime_combo.setCurrentText("image")
        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)
        assert calls[0]["mime"] == "image"

    def test_mime_dash_passes_none_to_viewmodel(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        calls = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))
        page.mime_combo.setCurrentText("—")
        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)
        assert calls[0]["mime"] is None

    def test_extensions_and_mime_both_set_emits_status_error_and_no_search(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        calls = []
        statuses = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))
        vm.statusChanged.connect(statuses.append)
        page.extensions_edit.setText("jpg")
        page.mime_combo.setCurrentText("image")
        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)
        assert calls == []
        assert any("mutually exclusive" in s for s in statuses)


class TestGap1RegexNoStrip:
    def test_regex_mode_preserves_leading_trailing_whitespace(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        calls = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))
        page.name_mode_combo.setCurrentText("Regex")
        page.name_edit.setText(" IMG_.* ")
        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)
        assert calls[0]["name_regex"] == " IMG_.* "


class TestGap2MimePresetConflict:
    def test_extension_preset_and_mime_emits_error_and_no_search(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        calls = []
        statuses = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))
        vm.statusChanged.connect(statuses.append)
        page.preset_combo.setCurrentText("photos")
        page.mime_combo.setCurrentText("video")
        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)
        assert calls == []
        assert any("mutually exclusive" in s.lower() for s in statuses)

    def test_non_extension_preset_and_mime_allows_search(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        calls = []
        monkeypatch.setattr(vm, "search", lambda **kw: calls.append(kw))
        page.preset_combo.setCurrentText("whatsapp")
        page.mime_combo.setCurrentText("image")
        qtbot.mouseClick(page.search_button, Qt.MouseButton.LeftButton)
        assert len(calls) == 1
