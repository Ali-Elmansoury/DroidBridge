from unittest.mock import MagicMock

from PyQt6.QtWidgets import QInputDialog

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.apps.cache import CacheViewModel
from droidbridge.gui.pages.apps.cache import CachePanel, _RESET_WARNING, _NO_SELECTION_TEXT
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _app_row(package="com.a", is_system=False, data_size_str="20 B", cache_size_str="5 B"):
    return {
        "package": package, "version_name": "1.0", "version_code": 1,
        "installed_str": "", "updated_str": "",
        "apk_size": 10, "apk_size_str": "10 B", "data_size": 20, "data_size_str": data_size_str,
        "cache_size": 5, "cache_size_str": cache_size_str, "total_size_str": "35 B",
        "kind": "system" if is_system else "user", "is_system": is_system,
        "status": "Enabled", "is_disabled": False,
    }


class TestCacheViewModel:
    def test_set_all_apps_emits_estimate_synchronously_with_no_worker(self, qtbot):
        vm = CacheViewModel(_connected_ctx(), worker_factory=FakeWorker)
        estimates = []
        vm.estimateChanged.connect(estimates.append)

        vm.set_all_apps([{"cache_size": 1000}, {"cache_size": 2000}])

        assert estimates == [{"estimate_bytes": 3000, "estimate_str": "2.9 KB"}]

    def test_set_current_app_with_none_emits_app_info_none(self, qtbot):
        vm = CacheViewModel(_connected_ctx(), worker_factory=FakeWorker)
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.set_current_app(None)

        assert infos == [None]

    def test_set_current_app_with_package_loads_app_info(self, qtbot, monkeypatch):
        vm = CacheViewModel(_connected_ctx(), worker_factory=FakeWorker)
        row = _app_row()
        monkeypatch.setattr("droidbridge.gui.viewmodels.apps.cache.apps_ops.get_app_info", lambda *a: row)
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.set_current_app("com.a")

        assert infos == [row]

    def test_trim_caches_calls_ops_and_emits_status(self, qtbot, monkeypatch):
        vm = CacheViewModel(_connected_ctx(), worker_factory=FakeWorker)
        calls = []
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.cache.apps_ops.trim_caches",
            lambda c, s, n: calls.append(n),
        )
        statuses = []
        vm.statusChanged.connect(statuses.append)

        vm.trim_caches(5000)

        assert calls == [5000]
        assert statuses == ["Caches trimmed."]

    def test_reset_app_data_calls_ops_and_reloads_app_info(self, qtbot, monkeypatch):
        vm = CacheViewModel(_connected_ctx(), worker_factory=FakeWorker)
        reset_calls = []
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.cache.apps_ops.reset_app_data",
            lambda c, s, p: reset_calls.append(p),
        )
        reloaded_row = _app_row(data_size_str="0 B", cache_size_str="0 B")
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.cache.apps_ops.get_app_info",
            lambda c, s, p: reloaded_row,
        )
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.reset_app_data("com.a")

        assert reset_calls == ["com.a"]
        assert infos == [reloaded_row]


class TestCachePanel:
    def test_set_all_apps_updates_estimate_label(self, qtbot):
        panel = CachePanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.set_all_apps([{"cache_size": 1000}])

        assert panel.estimate_label.text() == "Estimated reclaimable: 1000 B"

    def test_trim_button_calls_viewmodel_with_current_estimate(self, qtbot, monkeypatch):
        panel = CachePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.set_all_apps([{"cache_size": 1000}])
        calls = []
        monkeypatch.setattr(panel.viewmodel, "trim_caches", lambda n: calls.append(n))

        panel.trim_button.click()

        assert calls == [1000]

    def test_no_selection_shows_placeholder_and_disables_reset(self, qtbot):
        panel = CachePanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.appInfoChanged.emit(None)

        assert panel.acting_on_label.text() == _NO_SELECTION_TEXT
        assert not panel.reset_button.isEnabled()

    def test_user_app_selection_enables_reset_and_shows_warning(self, qtbot):
        panel = CachePanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.appInfoChanged.emit(_app_row(package="com.a", is_system=False))

        assert panel.reset_button.isEnabled()
        assert "com.a" in panel.acting_on_label.text()
        assert panel.warning_label.text() == _RESET_WARNING.format(package="com.a")

    def test_system_app_selection_keeps_reset_disabled(self, qtbot):
        panel = CachePanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.appInfoChanged.emit(_app_row(package="com.sys", is_system=True))

        assert not panel.reset_button.isEnabled()

    def test_reset_button_requires_typed_confirmation(self, qtbot, monkeypatch):
        panel = CachePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row(package="com.a", is_system=False))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("nope", True)))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "reset_app_data", lambda p: calls.append(p))

        panel.reset_button.click()

        assert calls == []

    def test_reset_button_with_correct_confirmation_calls_viewmodel(self, qtbot, monkeypatch):
        panel = CachePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row(package="com.a", is_system=False))
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("YES DELETE", True)))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "reset_app_data", lambda p: calls.append(p))

        panel.reset_button.click()

        assert calls == ["com.a"]

    def test_busy_disables_trim_and_reset_buttons(self, qtbot):
        panel = CachePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row(package="com.a", is_system=False))

        panel.viewmodel.busyChanged.emit(True)
        assert not panel.trim_button.isEnabled()
        assert not panel.reset_button.isEnabled()

        panel.viewmodel.busyChanged.emit(False)
        assert panel.trim_button.isEnabled()
        assert panel.reset_button.isEnabled()
