from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.apps.uninstall import UninstallViewModel
from droidbridge.gui.pages.apps.uninstall import UninstallPanel
from droidbridge.gui.widgets import uninstall_flow
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _app_row(package="com.a", is_system=False):
    return {
        "package": package, "version_name": "1.0", "version_code": 1,
        "installed_str": "", "updated_str": "",
        "apk_size": 10, "apk_size_str": "10 B", "data_size": 20, "data_size_str": "20 B",
        "cache_size": 5, "cache_size_str": "5 B", "total_size_str": "35 B",
        "kind": "system" if is_system else "user", "is_system": is_system,
        "status": "Enabled", "is_disabled": False,
    }


class TestUninstallViewModel:
    def test_set_current_app_with_none_emits_app_info_none(self, qtbot):
        vm = UninstallViewModel(_connected_ctx(), worker_factory=FakeWorker)
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.set_current_app(None)

        assert infos == [None]

    def test_set_current_app_with_package_loads_app_info(self, qtbot, monkeypatch):
        vm = UninstallViewModel(_connected_ctx(), worker_factory=FakeWorker)
        row = _app_row()
        monkeypatch.setattr("droidbridge.gui.viewmodels.apps.uninstall.apps_ops.get_app_info", lambda *a: row)
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.set_current_app("com.a")

        assert infos == [row]


class TestUninstallPanel:
    def test_no_selection_disables_uninstall_button(self, qtbot):
        panel = UninstallPanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.appInfoChanged.emit(None)

        assert not panel.uninstall_button.isEnabled()

    def test_user_app_selection_enables_uninstall_button(self, qtbot):
        panel = UninstallPanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.appInfoChanged.emit(_app_row(is_system=False))

        assert panel.uninstall_button.isEnabled()

    def test_system_app_selection_keeps_uninstall_disabled(self, qtbot):
        panel = UninstallPanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.appInfoChanged.emit(_app_row(is_system=True))

        assert not panel.uninstall_button.isEnabled()

    def test_uninstall_click_calls_flow_with_keep_data_checkbox(self, qtbot, monkeypatch):
        panel = UninstallPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row())
        panel.keep_data_checkbox.setChecked(True)
        calls = []
        monkeypatch.setattr(
            uninstall_flow, "run_uninstall_flow",
            lambda parent, c, s, app, keep_data=False, worker_factory=None: calls.append((app["package"], keep_data)) or True,
        )

        panel.uninstall_button.click()

        assert calls == [("com.a", True)]

    def test_successful_uninstall_emits_app_uninstalled(self, qtbot, monkeypatch):
        panel = UninstallPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row())
        monkeypatch.setattr(uninstall_flow, "run_uninstall_flow", lambda *a, **k: True)
        signals = []
        panel.appUninstalled.connect(lambda: signals.append(True))

        panel.uninstall_button.click()

        assert signals == [True]

    def test_cancelled_uninstall_does_not_emit_app_uninstalled(self, qtbot, monkeypatch):
        panel = UninstallPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row())
        monkeypatch.setattr(uninstall_flow, "run_uninstall_flow", lambda *a, **k: False)
        signals = []
        panel.appUninstalled.connect(lambda: signals.append(True))

        panel.uninstall_button.click()

        assert signals == []
