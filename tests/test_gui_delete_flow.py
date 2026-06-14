"""Tests for droidbridge.gui.widgets.delete_flow (Phase 6.3)."""

from PyQt6.QtWidgets import QMessageBox, QWidget

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
