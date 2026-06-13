"""Tests for droidbridge.gui.pages.transfer.TransferPage (Phase 6.2)."""

from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.transfer import TransferPage
from droidbridge.gui.viewmodels.transfer import TransferViewModel
from droidbridge.modules import transfer as transfer_module
from droidbridge.utils.format import format_bytes
from tests.test_gui_viewmodels_device import FakeWorker


def _make_page():
    context = DeviceContext()
    context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")
    vm = TransferViewModel(context, worker_factory=FakeWorker)
    page = TransferPage(vm)
    page.show()  # isVisible() checks require the top-level widget to be shown
    return page, vm, context


class TestModeToggle:
    def test_pull_selected_by_default(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.pull_radio.isChecked() is True
        assert page.pull_group.isVisible() is True
        assert page.push_group.isVisible() is False

    def test_push_radio_shows_push_fields(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        page.push_radio.setChecked(True)

        assert page.pull_group.isVisible() is False
        assert page.push_group.isVisible() is True


class TestStartTransfer:
    def test_pull_calls_start_pull_with_form_fields(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []
        monkeypatch.setattr(vm, "start_pull", lambda *a, **k: calls.append((a, k)))

        page.remote_path_edit.setText("/sdcard/DCIM")
        page.local_dir_edit.setText("/tmp/out")
        page.conflict_combo.setCurrentText(transfer_module.CONFLICT_OVERWRITE)
        page.verify_checkbox.setChecked(False)

        qtbot.mouseClick(page.start_button, Qt.MouseButton.LeftButton)

        assert calls == [(("/sdcard/DCIM", "/tmp/out"), {
            "conflict": transfer_module.CONFLICT_OVERWRITE, "verify": False,
        })]

    def test_push_calls_start_push_with_form_fields(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []
        monkeypatch.setattr(vm, "start_push", lambda *a, **k: calls.append((a, k)))

        page.push_radio.setChecked(True)
        page.local_path_edit.setText("/tmp/photo.jpg")
        page.remote_dir_edit.setText("/sdcard/Pictures")

        qtbot.mouseClick(page.start_button, Qt.MouseButton.LeftButton)

        assert calls == [(("/tmp/photo.jpg", "/sdcard/Pictures"), {
            "conflict": transfer_module.CONFLICT_SKIP, "verify": True,
        })]


class TestPlanChanged:
    def test_basic_plan_shown(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.planChanged.emit({"total_files": 3, "total_bytes": 300, "already_present": 0, "conflicts_skipped": 0})

        assert "3 file(s)" in page.plan_label.text()
        assert format_bytes(300) in page.plan_label.text()

    def test_skipped_files_noted(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.planChanged.emit({"total_files": 1, "total_bytes": 100, "already_present": 2, "conflicts_skipped": 1})

        text = page.plan_label.text()
        assert "Skipping 2 file(s) already present" in text
        assert "Skipping 1 file(s) due to conflicts" in text


class TestProgressChanged:
    def test_progress_bar_and_label(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.progressChanged.emit({
            "done_files": 1, "total_files": 2, "done_bytes": 100, "total_bytes": 200,
            "done_bytes_str": "100 B", "total_bytes_str": "200 B",
            "speed_str": "50 B/s", "eta_str": "2s", "percent": 50.0,
        })

        assert page.progress_bar.value() == 50
        assert page.progress_label.text() == "1/2 files | 100 B / 200 B | 50 B/s | ETA 2s"


class TestVerificationChanged:
    def test_ok_verification_shows_green(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.verificationChanged.emit({"ok": True, "message": "Verified: 1 file(s), 100 B."})

        assert page.verification_label.text() == "Verified: 1 file(s), 100 B."
        assert "green" in page.verification_label.styleSheet()

    def test_failed_verification_shows_red(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.verificationChanged.emit({
            "ok": False,
            "message": "Verification FAILED: expected 1 file(s) (100 B), found 0 file(s) (0 B).",
        })

        assert "red" in page.verification_label.styleSheet()


class TestHistory:
    def test_entry_added_to_table(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.historyEntryAdded.emit({"direction": "pull", "total_files": 1, "total_bytes": 100, "verification_ok": True})

        assert page.history_table.rowCount() == 1
        assert page.history_table.item(0, 0).text() == "pull"
        assert page.history_table.item(0, 1).text() == "1"
        assert page.history_table.item(0, 2).text() == format_bytes(100)
        assert page.history_table.item(0, 3).text() == "Yes"

    def test_unverified_entry_shows_dash(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.historyEntryAdded.emit({"direction": "push", "total_files": 1, "total_bytes": 100, "verification_ok": None})

        assert page.history_table.item(0, 3).text() == "-"


class TestCancelButton:
    def test_visible_only_while_busy(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.cancel_button.isVisible() is False

        vm.busyChanged.emit(True)
        assert page.cancel_button.isVisible() is True
        assert page.start_button.isEnabled() is False

        vm.busyChanged.emit(False)
        assert page.cancel_button.isVisible() is False
        assert page.start_button.isEnabled() is True

    def test_click_sets_cancel_requested(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.busyChanged.emit(True)
        qtbot.mouseClick(page.cancel_button, Qt.MouseButton.LeftButton)

        assert vm._cancel_requested is True


class TestBrowseButtons:
    def test_browse_local_dir_fills_pull_field(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/dest"))

        qtbot.mouseClick(page.local_dir_browse_button, Qt.MouseButton.LeftButton)

        assert page.local_dir_edit.text() == "/tmp/dest"

    def test_browse_local_file_fills_push_field(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("/tmp/photo.jpg", "")))

        qtbot.mouseClick(page.local_file_browse_button, Qt.MouseButton.LeftButton)

        assert page.local_path_edit.text() == "/tmp/photo.jpg"

    def test_browse_local_folder_fills_push_field(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/folder"))

        qtbot.mouseClick(page.local_folder_browse_button, Qt.MouseButton.LeftButton)

        assert page.local_path_edit.text() == "/tmp/folder"
