from unittest.mock import MagicMock

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.apps.backup_restore import BackupRestoreViewModel
from droidbridge.gui.pages.apps.backup_restore import BackupRestorePanel
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _app_row(package="com.a"):
    return {
        "package": package, "version_name": "1.0", "version_code": 1,
        "installed_str": "", "updated_str": "",
        "apk_size": 10, "apk_size_str": "10 B", "data_size": 20, "data_size_str": "20 B",
        "cache_size": 5, "cache_size_str": "5 B", "total_size_str": "35 B",
        "kind": "user", "is_system": False, "status": "Enabled", "is_disabled": False,
    }


def _manifest(package="com.a"):
    return {
        "package": package, "version_name": "1.0", "version_code": 1,
        "apk_files": [{"filename": "base.apk", "size": 10}], "backed_up_at": "2026-06-22T00:00:00",
    }


class TestBackupRestoreViewModel:
    def test_set_current_app_with_none_emits_app_info_none(self, qtbot):
        vm = BackupRestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.set_current_app(None)

        assert infos == [None]

    def test_set_current_app_with_package_loads_app_info(self, qtbot, monkeypatch):
        vm = BackupRestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        row = _app_row()
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.backup_restore.apps_ops.get_app_info", lambda *a: row,
        )
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.set_current_app("com.a")

        assert infos == [row]

    def test_backup_calls_apps_ops_backup_apk_and_emits_finished(self, qtbot, monkeypatch):
        vm = BackupRestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        calls = []

        def fake_backup(c, s, package, version_name, version_code, dest_dir, progress_callback=None):
            calls.append((package, version_name, version_code, dest_dir))
            return "/tmp/dest/com.a_1"

        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.backup_restore.apps_ops.backup_apk", fake_backup,
        )
        finished = []
        vm.backupFinished.connect(finished.append)

        vm.backup("com.a", "1.0", 1, "/tmp/dest")

        assert calls == [("com.a", "1.0", 1, "/tmp/dest")]
        assert finished == ["/tmp/dest/com.a_1"]

    def test_load_manifest_calls_apps_ops_read_manifest_and_emits_changed(self, qtbot, monkeypatch):
        vm = BackupRestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        manifest = _manifest()
        calls = []
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.backup_restore.apps_ops.read_manifest",
            lambda bundle_dir: calls.append(bundle_dir) or manifest,
        )
        changed = []
        vm.manifestChanged.connect(changed.append)

        vm.load_manifest("/tmp/bundle")

        assert calls == ["/tmp/bundle"]
        assert changed == [manifest]

    def test_restore_calls_apps_ops_restore_apk_and_emits_finished(self, qtbot, monkeypatch):
        vm = BackupRestoreViewModel(_connected_ctx(), worker_factory=FakeWorker)
        calls = []
        manifest = _manifest()

        def fake_restore(c, s, bundle_dir, allow_downgrade=False):
            calls.append((bundle_dir, allow_downgrade))
            return manifest

        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.backup_restore.apps_ops.restore_apk", fake_restore,
        )
        finished = []
        vm.restoreFinished.connect(finished.append)

        vm.restore("/tmp/bundle", allow_downgrade=True)

        assert calls == [("/tmp/bundle", True)]
        assert finished == [manifest]


class TestBackupRestorePanel:
    def test_no_selection_disables_backup_button(self, qtbot):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.appInfoChanged.emit(None)

        assert not panel.backup_button.isEnabled()

    def test_selection_enables_backup_button(self, qtbot):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.appInfoChanged.emit(_app_row())

        assert panel.backup_button.isEnabled()

    def test_backup_click_opens_dialog_and_calls_viewmodel_backup(self, qtbot, monkeypatch):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row())
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/dest"))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "backup", lambda *a: calls.append(a))

        panel.backup_button.click()

        assert calls == [("com.a", "1.0", 1, "/tmp/dest")]

    def test_backup_cancelled_dialog_does_not_call_viewmodel(self, qtbot, monkeypatch):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row())
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "backup", lambda *a: calls.append(a))

        panel.backup_button.click()

        assert calls == []

    def test_restore_button_disabled_until_manifest_loaded(self, qtbot):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)

        assert not panel.restore_button.isEnabled()

    def test_browse_loads_manifest_and_enables_restore(self, qtbot, monkeypatch):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/bundle"))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "load_manifest", lambda bundle_dir: calls.append(bundle_dir))

        panel.browse_button.click()

        assert calls == ["/tmp/bundle"]

    def test_browse_cancelled_does_not_load_manifest(self, qtbot, monkeypatch):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "load_manifest", lambda bundle_dir: calls.append(bundle_dir))

        panel.browse_button.click()

        assert calls == []

    def test_manifest_loaded_shows_label_and_enables_restore(self, qtbot):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.manifestChanged.emit(_manifest())

        assert "com.a" in panel.manifest_label.text()
        assert "1.0" in panel.manifest_label.text()
        assert panel.restore_button.isEnabled()

    def test_restore_click_confirms_with_exact_text_and_calls_viewmodel(self, qtbot, monkeypatch):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/bundle"))
        monkeypatch.setattr(panel.viewmodel, "load_manifest", lambda bundle_dir: panel._on_manifest(_manifest()))
        panel.browse_button.click()
        panel.allow_downgrade_checkbox.setChecked(True)
        captured = {}

        def fake_question(parent, title, text, buttons):
            captured["text"] = text
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "restore", lambda bundle_dir, allow_downgrade=False: calls.append((bundle_dir, allow_downgrade)))

        panel.restore_button.click()

        assert captured["text"] == "Install/replace com.a v1.0 now?"
        assert calls == [("/tmp/bundle", True)]

    def test_restore_cancelled_does_not_call_viewmodel(self, qtbot, monkeypatch):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/tmp/bundle"))
        monkeypatch.setattr(panel.viewmodel, "load_manifest", lambda bundle_dir: panel._on_manifest(_manifest()))
        panel.browse_button.click()
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a: QMessageBox.StandardButton.No))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "restore", lambda bundle_dir, allow_downgrade=False: calls.append(bundle_dir))

        panel.restore_button.click()

        assert calls == []

    def test_busy_disables_action_buttons_and_busy_false_reenables(self, qtbot):
        panel = BackupRestorePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row())
        panel.viewmodel.manifestChanged.emit(_manifest())

        panel.viewmodel.busyChanged.emit(True)

        assert not panel.backup_button.isEnabled()
        assert not panel.restore_button.isEnabled()

        panel.viewmodel.busyChanged.emit(False)

        assert panel.backup_button.isEnabled()
        assert panel.restore_button.isEnabled()
