# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from droidbridge.gui import apps_ops
from droidbridge.gui.widgets import uninstall_flow
from droidbridge.gui.widgets.uninstall_flow import _UNINSTALL_CHOICE_BACKUP, _UNINSTALL_CHOICE_NO_BACKUP
from tests.test_gui_viewmodels_device import FakeWorker

_APP = {
    "package": "com.example.app", "version_name": "1.2.3", "version_code": 7,
    "total_size_str": "35 B",
}


def _clicked_button_by_text(text):
    def clicked_button(self):
        for button in self.buttons():
            if button.text() == text:
                return button
        return None
    return clicked_button


class TestRunUninstallFlow:
    def test_cancel_returns_false(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text("Cancel"))

        result = uninstall_flow.run_uninstall_flow(parent, object(), "SERIAL", _APP, worker_factory=FakeWorker)

        assert result is False

    def test_uninstall_without_backup_confirmed(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        calls = []
        monkeypatch.setattr(
            apps_ops, "uninstall_app",
            lambda c, s, p, keep_data=False: calls.append((p, keep_data)) or True,
        )
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_UNINSTALL_CHOICE_NO_BACKUP))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("YES DELETE", True)))

        result = uninstall_flow.run_uninstall_flow(
            parent, object(), "SERIAL", _APP, keep_data=True, worker_factory=FakeWorker,
        )

        assert result is True
        assert calls == [("com.example.app", True)]

    def test_wrong_confirmation_returns_false(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        calls = []
        monkeypatch.setattr(apps_ops, "uninstall_app", lambda c, s, p, keep_data=False: calls.append(p))
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_UNINSTALL_CHOICE_NO_BACKUP))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("nope", True)))

        result = uninstall_flow.run_uninstall_flow(parent, object(), "SERIAL", _APP, worker_factory=FakeWorker)

        assert result is False
        assert calls == []

    def test_backup_dialog_cancelled_returns_false(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_UNINSTALL_CHOICE_BACKUP))
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))

        result = uninstall_flow.run_uninstall_flow(parent, object(), "SERIAL", _APP, worker_factory=FakeWorker)

        assert result is False

    def test_backup_verification_failure_aborts_uninstall(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        warn_calls = []
        uninstall_calls = []
        monkeypatch.setattr(apps_ops, "backup_apk", lambda *a, **k: "/tmp/bundle")
        monkeypatch.setattr(apps_ops, "verify_apk_backup", lambda bundle_dir: False)
        monkeypatch.setattr(apps_ops, "uninstall_app", lambda c, s, p, keep_data=False: uninstall_calls.append(p))
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_UNINSTALL_CHOICE_BACKUP))
        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a: warn_calls.append(a[1:])))
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/backup"))

        result = uninstall_flow.run_uninstall_flow(parent, object(), "SERIAL", _APP, worker_factory=FakeWorker)

        assert result is False
        assert warn_calls
        assert uninstall_calls == []

    def test_backup_verified_then_uninstall_confirmed(self, qtbot, monkeypatch):
        parent = QWidget()
        qtbot.addWidget(parent)
        uninstall_calls = []
        monkeypatch.setattr(apps_ops, "backup_apk", lambda *a, **k: "/tmp/bundle")
        monkeypatch.setattr(apps_ops, "verify_apk_backup", lambda bundle_dir: True)
        monkeypatch.setattr(
            apps_ops, "uninstall_app",
            lambda c, s, p, keep_data=False: uninstall_calls.append(p) or True,
        )
        monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
        monkeypatch.setattr(QMessageBox, "clickedButton", _clicked_button_by_text(_UNINSTALL_CHOICE_BACKUP))
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/backup"))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("YES DELETE", True)))

        result = uninstall_flow.run_uninstall_flow(parent, object(), "SERIAL", _APP, worker_factory=FakeWorker)

        assert result is True
        assert uninstall_calls == ["com.example.app"]
