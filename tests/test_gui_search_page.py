"""Tests for droidbridge.gui.pages.search.SearchPage (Phase 6.2)."""

from datetime import date, datetime
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.search import SearchPage
from droidbridge.gui.viewmodels.search import SearchViewModel
from droidbridge.modules import search as search_module
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


def _make_page():
    context = DeviceContext()
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
