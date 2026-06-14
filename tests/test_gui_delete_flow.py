"""Tests for droidbridge.gui.widgets.delete_flow (Phase 6.3)."""

from PyQt6.QtWidgets import QInputDialog, QMessageBox, QWidget

from droidbridge.core.adb import AdbError
from droidbridge.gui import delete_ops
from droidbridge.gui.widgets import delete_flow
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
