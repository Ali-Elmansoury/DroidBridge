"""Tests for droidbridge.gui.widgets.remote_browse_dialog.RemoteBrowseDialog (Phase 6.2)."""

from datetime import datetime
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from droidbridge.gui import files_ops
from droidbridge.gui.widgets.remote_browse_dialog import RemoteBrowseDialog
from droidbridge.modules.files import FileEntry

ROOT_ENTRIES = [
    FileEntry(name="DCIM", path="/sdcard/DCIM", is_dir=True, is_symlink=False,
              size=4096, mtime=datetime(2023, 8, 5, 22, 56)),
    FileEntry(name="notes.txt", path="/sdcard/notes.txt", is_dir=False, is_symlink=False,
              size=2048, mtime=datetime(2023, 8, 3, 12, 0)),
]

DCIM_ENTRIES = [
    FileEntry(name="Camera", path="/sdcard/DCIM/Camera", is_dir=True, is_symlink=False,
              size=4096, mtime=datetime(2023, 8, 5, 22, 56)),
]


def _fake_list_path(client, serial, path, **kw):
    if path == "/sdcard":
        return ROOT_ENTRIES
    if path == "/sdcard/DCIM":
        return DCIM_ENTRIES
    return []


def _make_dialog(qtbot, monkeypatch, mode="any", start_path="/sdcard"):
    monkeypatch.setattr(files_ops, "list_path", _fake_list_path)
    dialog = RemoteBrowseDialog(MagicMock(), "SERIAL123", start_path, mode=mode)
    qtbot.addWidget(dialog)
    return dialog


class TestLoading:
    def test_initial_load_populates_table(self, qtbot, monkeypatch):
        dialog = _make_dialog(qtbot, monkeypatch)

        assert dialog.table.rowCount() == 2
        assert dialog.table.item(0, 0).text() == "DCIM"
        assert dialog.table.item(0, 1).text() == "dir"
        assert dialog.table.item(1, 0).text() == "notes.txt"
        assert dialog.table.item(1, 1).text() == "file"
        assert dialog.path_label.text() == "/sdcard"


class TestNavigation:
    def test_double_click_directory_navigates_in(self, qtbot, monkeypatch):
        dialog = _make_dialog(qtbot, monkeypatch)

        dialog.table.itemDoubleClicked.emit(dialog.table.item(0, 0))

        assert dialog.path_label.text() == "/sdcard/DCIM"
        assert dialog.table.rowCount() == 1
        assert dialog.table.item(0, 0).text() == "Camera"

    def test_double_click_file_does_not_navigate(self, qtbot, monkeypatch):
        dialog = _make_dialog(qtbot, monkeypatch)

        dialog.table.itemDoubleClicked.emit(dialog.table.item(1, 0))

        assert dialog.path_label.text() == "/sdcard"

    def test_up_button_navigates_to_parent(self, qtbot, monkeypatch):
        dialog = _make_dialog(qtbot, monkeypatch, start_path="/sdcard/DCIM")

        qtbot.mouseClick(dialog.up_button, Qt.MouseButton.LeftButton)

        assert dialog.path_label.text() == "/sdcard"


class TestSelectionAndAccept:
    def test_no_selection_returns_current_path(self, qtbot, monkeypatch):
        dialog = _make_dialog(qtbot, monkeypatch)

        assert dialog.selected_path() == "/sdcard"

    def test_selecting_entry_returns_its_path(self, qtbot, monkeypatch):
        dialog = _make_dialog(qtbot, monkeypatch)

        dialog.table.selectRow(1)  # notes.txt

        assert dialog.selected_path() == "/sdcard/notes.txt"

    def test_directory_mode_rejects_file_selection(self, qtbot, monkeypatch):
        dialog = _make_dialog(qtbot, monkeypatch, mode="directory")

        dialog.table.selectRow(1)  # notes.txt (a file)

        assert dialog.table.selectedIndexes() == []
        assert dialog.selected_path() == "/sdcard"

    def test_directory_mode_allows_directory_selection(self, qtbot, monkeypatch):
        dialog = _make_dialog(qtbot, monkeypatch, mode="directory")

        dialog.table.selectRow(0)  # DCIM (a directory)

        assert dialog.selected_path() == "/sdcard/DCIM"


class TestGetRemotePath:
    def test_accepted_returns_selected_path(self, qtbot, monkeypatch):
        monkeypatch.setattr(files_ops, "list_path", _fake_list_path)
        monkeypatch.setattr(RemoteBrowseDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

        path = RemoteBrowseDialog.get_remote_path(None, MagicMock(), "SERIAL123", "/sdcard")

        assert path == "/sdcard"

    def test_cancelled_returns_none(self, qtbot, monkeypatch):
        monkeypatch.setattr(files_ops, "list_path", _fake_list_path)
        monkeypatch.setattr(RemoteBrowseDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

        path = RemoteBrowseDialog.get_remote_path(None, MagicMock(), "SERIAL123", "/sdcard")

        assert path is None
