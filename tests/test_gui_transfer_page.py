"""Tests for droidbridge.gui.pages.transfer.TransferPage (Phase 6.2)."""

from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from droidbridge.core.adb import AdbCommandError
from droidbridge.gui import files_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.transfer import TransferPage
from droidbridge.gui.viewmodels.transfer import TransferViewModel
from droidbridge.gui.widgets.remote_browse_dialog import RemoteBrowseDialog
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


class TestConflictComboTooltip:
    def test_conflict_combo_explains_resume_precedence(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        tooltip = page.conflict_combo.toolTip()
        assert tooltip != ""
        assert "same size" in tooltip
        assert "resume" in tooltip.lower()


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
            "conflict": transfer_module.CONFLICT_OVERWRITE, "verify": False, "retry_count": 3,
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
            "conflict": transfer_module.CONFLICT_SKIP, "verify": True, "retry_count": 3,
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

    def test_clear_history_button_empties_table(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.historyEntryAdded.emit({"direction": "pull", "total_files": 1, "total_bytes": 100, "verification_ok": True})
        assert page.history_table.rowCount() == 1

        qtbot.mouseClick(page.clear_history_button, Qt.MouseButton.LeftButton)

        assert page.history_table.rowCount() == 0


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

    def test_browse_remote_path_fills_pull_field(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []

        def fake_get_remote_path(parent, client, serial, start_path, mode="any"):
            calls.append((start_path, mode))
            return "/sdcard/DCIM"

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(fake_get_remote_path))

        qtbot.mouseClick(page.remote_path_browse_button, Qt.MouseButton.LeftButton)

        assert page.remote_path_edit.text() == "/sdcard/DCIM"
        assert calls == [("/sdcard", "any")]

    def test_browse_remote_dir_fills_push_field(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []

        def fake_get_remote_path(parent, client, serial, start_path, mode="any"):
            calls.append((start_path, mode))
            return "/sdcard/Pictures"

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(fake_get_remote_path))

        qtbot.mouseClick(page.remote_dir_browse_button, Qt.MouseButton.LeftButton)

        assert page.remote_dir_edit.text() == "/sdcard/Pictures"
        assert calls == [("/sdcard", "directory")]

    def test_browse_remote_path_cancelled_leaves_field_unchanged(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page.remote_path_edit.setText("/sdcard/Existing")

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(lambda *a, **k: None))

        qtbot.mouseClick(page.remote_path_browse_button, Qt.MouseButton.LeftButton)

        assert page.remote_path_edit.text() == "/sdcard/Existing"


class TestNewRemoteFolderButton:
    def test_creates_folder_under_chosen_parent_and_fills_field(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page.push_radio.setChecked(True)

        calls = []

        def fake_get_remote_path(parent, client, serial, start_path, mode="any"):
            calls.append((start_path, mode))
            return "/sdcard/Pictures"

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(fake_get_remote_path))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Vacation2026", True)))

        mkdir_calls = []
        monkeypatch.setattr(files_ops, "make_directory", lambda client, serial, path: mkdir_calls.append(path))

        qtbot.mouseClick(page.remote_dir_new_folder_button, Qt.MouseButton.LeftButton)

        assert calls == [("/sdcard", "directory")]
        assert mkdir_calls == ["/sdcard/Pictures/Vacation2026"]
        assert page.remote_dir_edit.text() == "/sdcard/Pictures/Vacation2026"

    def test_uses_existing_field_value_as_start_path(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page.push_radio.setChecked(True)
        page.remote_dir_edit.setText("/sdcard/Existing")

        calls = []

        def fake_get_remote_path(parent, client, serial, start_path, mode="any"):
            calls.append((start_path, mode))
            return None

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(fake_get_remote_path))

        qtbot.mouseClick(page.remote_dir_new_folder_button, Qt.MouseButton.LeftButton)

        assert calls == [("/sdcard/Existing", "directory")]

    def test_cancelled_parent_picker_does_not_create_folder(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page.push_radio.setChecked(True)

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(lambda *a, **k: None))
        mkdir_calls = []
        monkeypatch.setattr(files_ops, "make_directory", lambda client, serial, path: mkdir_calls.append(path))

        qtbot.mouseClick(page.remote_dir_new_folder_button, Qt.MouseButton.LeftButton)

        assert mkdir_calls == []
        assert page.remote_dir_edit.text() == ""

    def test_cancelled_name_prompt_does_not_create_folder(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page.push_radio.setChecked(True)

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(lambda *a, **k: "/sdcard/Pictures"))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
        mkdir_calls = []
        monkeypatch.setattr(files_ops, "make_directory", lambda client, serial, path: mkdir_calls.append(path))

        qtbot.mouseClick(page.remote_dir_new_folder_button, Qt.MouseButton.LeftButton)

        assert mkdir_calls == []
        assert page.remote_dir_edit.text() == ""

    def test_blank_name_does_not_create_folder(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page.push_radio.setChecked(True)

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(lambda *a, **k: "/sdcard/Pictures"))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("   ", True)))
        mkdir_calls = []
        monkeypatch.setattr(files_ops, "make_directory", lambda client, serial, path: mkdir_calls.append(path))

        qtbot.mouseClick(page.remote_dir_new_folder_button, Qt.MouseButton.LeftButton)

        assert mkdir_calls == []
        assert page.remote_dir_edit.text() == ""

    def test_name_with_slash_is_rejected(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page.push_radio.setChecked(True)

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(lambda *a, **k: "/sdcard/Pictures"))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Sub/Folder", True)))
        mkdir_calls = []
        monkeypatch.setattr(files_ops, "make_directory", lambda client, serial, path: mkdir_calls.append(path))
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a))

        qtbot.mouseClick(page.remote_dir_new_folder_button, Qt.MouseButton.LeftButton)

        assert mkdir_calls == []
        assert len(warnings) == 1
        assert page.remote_dir_edit.text() == ""

    def test_mkdir_error_shows_warning_and_leaves_field_unchanged(self, qtbot, monkeypatch):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        page.push_radio.setChecked(True)

        monkeypatch.setattr(RemoteBrowseDialog, "get_remote_path", staticmethod(lambda *a, **k: "/sdcard/Pictures"))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Vacation2026", True)))

        def failing_mkdir(client, serial, path):
            raise AdbCommandError(["adb", "shell", "mkdir"], 1, "", "Permission denied")

        monkeypatch.setattr(files_ops, "make_directory", failing_mkdir)
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a))

        qtbot.mouseClick(page.remote_dir_new_folder_button, Qt.MouseButton.LeftButton)

        assert len(warnings) == 1
        assert page.remote_dir_edit.text() == ""


class TestRetrySpinbox:
    def _make_page(self, qtbot):
        from droidbridge.gui.pages.transfer import TransferPage
        from droidbridge.gui.viewmodels.transfer import TransferViewModel
        from droidbridge.gui.device_context import DeviceContext
        from unittest.mock import MagicMock
        context = DeviceContext()
        context.set_connected(MagicMock(), "S", "Pixel")
        vm = TransferViewModel(context, worker_factory=lambda fn, **kw: MagicMock())
        page = TransferPage(vm)
        qtbot.addWidget(page)
        return page, vm

    def test_retry_spin_present_with_default_3(self, qtbot):
        page, _ = self._make_page(qtbot)
        assert hasattr(page, "retry_spin")
        assert page.retry_spin.value() == 3
        assert page.retry_spin.minimum() == 0
        assert page.retry_spin.maximum() == 10

    def test_pull_passes_retry_count_from_spin(self, qtbot, monkeypatch):
        page, vm = self._make_page(qtbot)
        calls = []
        monkeypatch.setattr(vm, "start_pull", lambda *a, **k: calls.append(k))
        page.retry_spin.setValue(7)
        page._on_start_clicked()
        assert calls[0].get("retry_count") == 7


class TestMirrorCheckboxes:
    def _make_page(self, qtbot):
        from droidbridge.gui.pages.transfer import TransferPage
        from droidbridge.gui.viewmodels.transfer import TransferViewModel
        from droidbridge.gui.device_context import DeviceContext
        from unittest.mock import MagicMock
        context = DeviceContext()
        context.set_connected(MagicMock(), "S", "Pixel")
        vm = TransferViewModel(context, worker_factory=lambda fn, **kw: MagicMock())
        page = TransferPage(vm)
        qtbot.addWidget(page)
        return page, vm

    def test_mirror_checkbox_present(self, qtbot):
        page, _ = self._make_page(qtbot)
        assert hasattr(page, "mirror_checkbox")

    def test_delete_extras_checkbox_present(self, qtbot):
        page, _ = self._make_page(qtbot)
        assert hasattr(page, "delete_extras_checkbox")

    def test_mirror_pull_calls_start_mirror_pull(self, qtbot, monkeypatch):
        page, vm = self._make_page(qtbot)
        calls = []
        monkeypatch.setattr(vm, "start_mirror_pull", lambda *a, **k: calls.append(k))
        page.mirror_checkbox.setChecked(True)
        page.pull_radio.setChecked(True)
        page._on_start_clicked()
        assert len(calls) == 1
        assert "delete_extras" in calls[0]
        assert "retry_count" in calls[0]

    def test_mirror_push_calls_start_mirror_push(self, qtbot, monkeypatch):
        page, vm = self._make_page(qtbot)
        calls = []
        monkeypatch.setattr(vm, "start_mirror_push", lambda *a, **k: calls.append(k))
        page.mirror_checkbox.setChecked(True)
        page.push_radio.setChecked(True)
        page._on_start_clicked()
        assert len(calls) == 1


class TestMirrorPlanReadySlot:
    def _make_page_with_vm(self, qtbot):
        from droidbridge.gui.pages.transfer import TransferPage
        from droidbridge.gui.viewmodels.transfer import TransferViewModel
        from droidbridge.gui.device_context import DeviceContext
        from unittest.mock import MagicMock
        context = DeviceContext()
        context.set_connected(MagicMock(), "S", "Pixel")
        vm = TransferViewModel(context, worker_factory=lambda fn, **kw: MagicMock())
        page = TransferPage(vm)
        qtbot.addWidget(page)
        return page, vm

    def test_no_dialog_when_no_extras_or_delete_not_requested(self, qtbot, monkeypatch):
        page, vm = self._make_page_with_vm(qtbot)
        confirmed = []
        monkeypatch.setattr(vm, "confirm_mirror", lambda dc: confirmed.append(dc))

        page._on_mirror_plan_ready({"extra_files": 0, "extra_bytes": 0, "extra_paths": [],
                                    "delete_extras_requested": True})

        assert confirmed == [False]

    def test_dialog_shown_when_extras_and_delete_requested(self, qtbot, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox, QInputDialog
        page, vm = self._make_page_with_vm(qtbot)
        confirmed = []
        monkeypatch.setattr(vm, "confirm_mirror", lambda dc: confirmed.append(dc))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(QInputDialog, "getText",
                            staticmethod(lambda *a, **k: ("YES DELETE", True)))

        page._on_mirror_plan_ready({
            "extra_files": 1, "extra_bytes": 100,
            "extra_paths": ["/tmp/extra.jpg"],
            "delete_extras_requested": True,
        })

        assert confirmed == [True]

    def test_dialog_declined_passes_false(self, qtbot, monkeypatch):
        from PyQt6.QtWidgets import QMessageBox, QInputDialog
        page, vm = self._make_page_with_vm(qtbot)
        confirmed = []
        monkeypatch.setattr(vm, "confirm_mirror", lambda dc: confirmed.append(dc))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
        monkeypatch.setattr(QInputDialog, "getText",
                            staticmethod(lambda *a, **k: ("NOPE", True)))

        page._on_mirror_plan_ready({
            "extra_files": 1, "extra_bytes": 100,
            "extra_paths": ["/tmp/extra.jpg"],
            "delete_extras_requested": True,
        })

        assert confirmed == [False]


class TestTransferPageTooltips:
    def test_pull_radio_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.pull_radio.toolTip() != ""

    def test_push_radio_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.push_radio.toolTip() != ""

    def test_remote_path_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.remote_path_edit.toolTip() != ""

    def test_remote_path_browse_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.remote_path_browse_button.toolTip() != ""

    def test_local_dir_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.local_dir_edit.toolTip() != ""

    def test_local_dir_browse_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.local_dir_browse_button.toolTip() != ""

    def test_local_path_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.local_path_edit.toolTip() != ""

    def test_local_file_browse_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.local_file_browse_button.toolTip() != ""

    def test_local_folder_browse_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.local_folder_browse_button.toolTip() != ""

    def test_remote_dir_edit_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.remote_dir_edit.toolTip() != ""

    def test_remote_dir_browse_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.remote_dir_browse_button.toolTip() != ""

    def test_remote_dir_new_folder_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.remote_dir_new_folder_button.toolTip() != ""

    def test_verify_checkbox_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.verify_checkbox.toolTip() != ""

    def test_mirror_checkbox_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.mirror_checkbox.toolTip() != ""

    def test_delete_extras_checkbox_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.delete_extras_checkbox.toolTip() != ""

    def test_start_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.start_button.toolTip() != ""

    def test_cancel_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.cancel_button.toolTip() != ""

    def test_clear_history_button_has_tooltip(self, qtbot):
        page, _vm, _ctx = _make_page()
        qtbot.addWidget(page)
        assert page.clear_history_button.toolTip() != ""


class TestTransferPageShortcuts:
    def test_ctrl_return_starts_transfer(self, qtbot, monkeypatch):
        page, vm, _ctx = _make_page()
        qtbot.addWidget(page)
        page.show()

        page.remote_path_edit.setText("/sdcard/DCIM")
        page.local_dir_edit.setText("/tmp")

        calls = []
        monkeypatch.setattr(vm, "start_pull", lambda *a, **k: calls.append(1))

        qtbot.keyClick(page, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

        assert calls


class TestHistoryFailedColumnInPage:
    def _make_page(self, qtbot):
        from droidbridge.gui.pages.transfer import TransferPage, _HISTORY_COLUMNS
        from droidbridge.gui.viewmodels.transfer import TransferViewModel
        from droidbridge.gui.device_context import DeviceContext
        from unittest.mock import MagicMock
        context = DeviceContext()
        context.set_connected(MagicMock(), "S", "Pixel")
        vm = TransferViewModel(context, worker_factory=lambda fn, **kw: MagicMock())
        page = TransferPage(vm)
        qtbot.addWidget(page)
        return page, vm

    def test_five_columns_in_history_table(self, qtbot):
        page, _ = self._make_page(qtbot)
        from droidbridge.gui.pages.transfer import _HISTORY_COLUMNS
        assert page.history_table.columnCount() == 5
        assert "Failed" in _HISTORY_COLUMNS

    def test_failed_column_shows_count(self, qtbot):
        page, vm = self._make_page(qtbot)
        vm.historyEntryAdded.emit({
            "direction": "pull", "total_files": 2, "total_bytes": 2000,
            "verification_ok": True, "failed": 1, "deleted_files": 0,
        })
        assert page.history_table.item(0, 4).text() == "1"
