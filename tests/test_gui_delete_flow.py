# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Tests for droidbridge.gui.widgets.delete_flow (Phase 6.3)."""

from types import SimpleNamespace

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from droidbridge.core.adb import AdbError
from droidbridge.gui import delete_ops, transfer_ops
from droidbridge.gui.widgets import delete_flow
from droidbridge.gui.widgets.delete_flow import _DELETE_CHOICE_BACKUP, _DELETE_CHOICE_NO_BACKUP
from droidbridge.modules.files import DeletePlan, DeleteVerification
from tests.test_gui_viewmodels_device import FakeWorker


class TestRunWithProgress:
    def test_real_worker_returns_value(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)

        result = delete_flow._run_with_progress(parent, lambda: 42, title="Testing")

        assert result == 42

    def test_success_returns_value(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)

        result = delete_flow._run_with_progress(parent, lambda: 42, worker_factory=FakeWorker)

        assert result == 42

    def test_error_shows_warning_and_returns_none(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        warnings = []
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: warnings.append(a[1:])))

        def boom():
            raise RuntimeError("boom")

        result = delete_flow._run_with_progress(parent, boom, worker_factory=FakeWorker)

        assert result is None
        assert warnings[0][-1] == "boom"

    def test_progress_callback_invoked(self, qtbot):
        parent = QWidget()
        qtbot.addWidget(parent)

        def fn(progress_callback=None):
            progress_callback("step 1")
            progress_callback("step 2")
            return "done"

        result = delete_flow._run_with_progress(
            parent, fn, worker_factory=FakeWorker, report_progress=True,
        )

        assert result == "done"


class TestRunRenameFlow:
    def test_success_renames_and_returns_new_path(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        calls = []
        monkeypatch.setattr(delete_ops, "rename_path", lambda c, s, old, new: calls.append((old, new)))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("new.txt", True)))

        result = delete_flow.run_rename_flow(parent, object(), "SERIAL", "/sdcard/old.txt")

        assert result == "/sdcard/new.txt"
        assert calls == [("/sdcard/old.txt", "/sdcard/new.txt")]

    def test_cancel_returns_none(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))

        result = delete_flow.run_rename_flow(parent, object(), "SERIAL", "/sdcard/old.txt")

        assert result is None

    def test_unchanged_name_returns_none(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("old.txt", True)))

        result = delete_flow.run_rename_flow(parent, object(), "SERIAL", "/sdcard/old.txt")

        assert result is None

    def test_name_with_slash_shows_warning_and_returns_none(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        warnings = []
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("a/b", True)))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: warnings.append(a[1:])))

        result = delete_flow.run_rename_flow(parent, object(), "SERIAL", "/sdcard/old.txt")

        assert result is None
        assert warnings

    def test_adb_error_shows_warning_and_returns_none(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        warnings = []

        def raise_error(c, s, old, new):
            raise AdbError("target exists")

        monkeypatch.setattr(delete_ops, "rename_path", raise_error)
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("new.txt", True)))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: warnings.append(a[1:])))

        result = delete_flow.run_rename_flow(parent, object(), "SERIAL", "/sdcard/old.txt")

        assert result is None
        assert warnings


def _clicked_button_by_text(text):
    def clicked_button(self):
        for button in self.buttons():
            if button.text() == text:
                return button
        return None
    return clicked_button


class TestRunDeleteFlow:
    def test_nothing_to_delete_shows_info(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        info_calls = []
        monkeypatch.setattr(
            delete_ops, "build_delete_plan",
            lambda c, s, paths: DeletePlan(paths=[], file_count=0, total_size=0),
        )
        monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a: info_calls.append(a[1:])))

        result = delete_flow.run_delete_flow(parent, object(), "SERIAL", ["/sdcard/Empty"], worker_factory=FakeWorker)

        assert result == set()
        assert info_calls

    def test_cancel_returns_empty_set(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        monkeypatch.setattr(
            delete_ops, "build_delete_plan",
            lambda c, s, paths: DeletePlan(paths=["/sdcard/a.jpg"], file_count=1, total_size=100),
        )
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text("Cancel"))

        result = delete_flow.run_delete_flow(parent, object(), "SERIAL", ["/sdcard/a.jpg"], worker_factory=FakeWorker)

        assert result == set()

    def test_delete_without_backup_confirmed(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        calls = []
        monkeypatch.setattr(
            delete_ops, "build_delete_plan",
            lambda c, s, paths: DeletePlan(paths=["/sdcard/a.jpg"], file_count=1, total_size=100),
        )
        monkeypatch.setattr(delete_ops, "delete_paths", lambda c, s, paths: calls.append(paths))
        monkeypatch.setattr(
            delete_ops, "verify_deletion",
            lambda c, s, paths: DeleteVerification(deleted=["/sdcard/a.jpg"], remaining=[]),
        )
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_DELETE_CHOICE_NO_BACKUP))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("YES DELETE", True)))

        result = delete_flow.run_delete_flow(parent, object(), "SERIAL", ["/sdcard/a.jpg"], worker_factory=FakeWorker)

        assert result == {"/sdcard/a.jpg"}
        assert calls == [["/sdcard/a.jpg"]]

    def test_delete_without_backup_wrong_confirmation(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        calls = []
        monkeypatch.setattr(
            delete_ops, "build_delete_plan",
            lambda c, s, paths: DeletePlan(paths=["/sdcard/a.jpg"], file_count=1, total_size=100),
        )
        monkeypatch.setattr(delete_ops, "delete_paths", lambda c, s, paths: calls.append(paths))
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_DELETE_CHOICE_NO_BACKUP))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("nope", True)))

        result = delete_flow.run_delete_flow(parent, object(), "SERIAL", ["/sdcard/a.jpg"], worker_factory=FakeWorker)

        assert result == set()
        assert calls == []

    def test_backup_dialog_cancelled_returns_empty_set(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        monkeypatch.setattr(
            delete_ops, "build_delete_plan",
            lambda c, s, paths: DeletePlan(paths=["/sdcard/a.jpg"], file_count=1, total_size=100),
        )
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_DELETE_CHOICE_BACKUP))
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))

        result = delete_flow.run_delete_flow(parent, object(), "SERIAL", ["/sdcard/a.jpg"], worker_factory=FakeWorker)

        assert result == set()

    def test_backup_verification_failure_aborts_delete(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        warn_calls = []
        monkeypatch.setattr(
            delete_ops, "build_delete_plan",
            lambda c, s, paths: DeletePlan(paths=["/sdcard/a.jpg"], file_count=1, total_size=100),
        )
        monkeypatch.setattr(transfer_ops, "plan_pull_many", lambda c, s, paths, local_dir: ["plan1"])
        monkeypatch.setattr(
            transfer_ops, "execute_plans",
            lambda c, s, plans, progress_callback=None: progress_callback and progress_callback("step"),
        )
        monkeypatch.setattr(
            transfer_ops, "verify_plans",
            lambda c, s, plans, direction, local_dir=None: SimpleNamespace(ok=False),
        )
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_DELETE_CHOICE_BACKUP))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: warn_calls.append(a[1:])))
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/backup"))

        result = delete_flow.run_delete_flow(parent, object(), "SERIAL", ["/sdcard/a.jpg"], worker_factory=FakeWorker)

        assert result == set()
        assert warn_calls

    def test_backup_verified_then_delete_confirmed(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        calls = []
        monkeypatch.setattr(
            delete_ops, "build_delete_plan",
            lambda c, s, paths: DeletePlan(paths=["/sdcard/a.jpg"], file_count=1, total_size=100),
        )
        monkeypatch.setattr(delete_ops, "delete_paths", lambda c, s, paths: calls.append(paths))
        monkeypatch.setattr(
            delete_ops, "verify_deletion",
            lambda c, s, paths: DeleteVerification(deleted=["/sdcard/a.jpg"], remaining=[]),
        )
        monkeypatch.setattr(transfer_ops, "plan_pull_many", lambda c, s, paths, local_dir: ["plan1"])
        monkeypatch.setattr(
            transfer_ops, "execute_plans",
            lambda c, s, plans, progress_callback=None: progress_callback and progress_callback("step"),
        )
        monkeypatch.setattr(
            transfer_ops, "verify_plans",
            lambda c, s, plans, direction, local_dir=None: SimpleNamespace(ok=True),
        )
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_DELETE_CHOICE_BACKUP))
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/backup"))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("YES DELETE", True)))

        result = delete_flow.run_delete_flow(parent, object(), "SERIAL", ["/sdcard/a.jpg"], worker_factory=FakeWorker)

        assert result == {"/sdcard/a.jpg"}
        assert calls == [["/sdcard/a.jpg"]]

    def test_partial_deletion_warns_about_remaining(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        warn_calls = []
        monkeypatch.setattr(
            delete_ops, "build_delete_plan",
            lambda c, s, paths: DeletePlan(paths=["/sdcard/a.jpg", "/sdcard/b.jpg"], file_count=2, total_size=200),
        )
        monkeypatch.setattr(delete_ops, "delete_paths", lambda c, s, paths: None)
        monkeypatch.setattr(
            delete_ops, "verify_deletion",
            lambda c, s, paths: DeleteVerification(deleted=["/sdcard/a.jpg"], remaining=["/sdcard/b.jpg"]),
        )
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_DELETE_CHOICE_NO_BACKUP))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: warn_calls.append(a[1:])))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("YES DELETE", True)))

        result = delete_flow.run_delete_flow(
            parent, object(), "SERIAL", ["/sdcard/a.jpg", "/sdcard/b.jpg"], worker_factory=FakeWorker,
        )

        assert result == {"/sdcard/a.jpg"}
        assert warn_calls
