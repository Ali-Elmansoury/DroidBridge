from unittest.mock import MagicMock

from PyQt6.QtWidgets import QMessageBox

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.apps.bloatware import BloatwareViewModel
from droidbridge.gui.pages.apps.bloatware import BloatwarePanel, _SYSTEM_APP_WARNING
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _app_row(package="com.a", is_system=False, is_disabled=False):
    return {
        "package": package, "version_name": "1.0", "version_code": 1,
        "installed_str": "", "updated_str": "",
        "apk_size": 10, "apk_size_str": "10 B", "data_size": 20, "data_size_str": "20 B",
        "cache_size": 5, "cache_size_str": "5 B", "total_size_str": "35 B",
        "kind": "system" if is_system else "user", "is_system": is_system,
        "status": "Disabled" if is_disabled else "Enabled", "is_disabled": is_disabled,
    }


class TestBloatwareViewModel:
    def test_set_current_app_with_none_emits_app_info_none(self, qtbot):
        vm = BloatwareViewModel(_connected_ctx(), worker_factory=FakeWorker)
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.set_current_app(None)

        assert infos == [None]

    def test_set_current_app_with_package_loads_app_info(self, qtbot, monkeypatch):
        vm = BloatwareViewModel(_connected_ctx(), worker_factory=FakeWorker)
        row = _app_row()
        monkeypatch.setattr("droidbridge.gui.viewmodels.apps.bloatware.apps_ops.get_app_info", lambda *a: row)
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.set_current_app("com.a")

        assert infos == [row]

    def test_disable_app_calls_ops_then_reloads_info(self, qtbot, monkeypatch):
        vm = BloatwareViewModel(_connected_ctx(), worker_factory=FakeWorker)
        calls = []
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.bloatware.apps_ops.disable_app",
            lambda c, s, p: calls.append(("disable", p)),
        )
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.bloatware.apps_ops.get_app_info",
            lambda c, s, p: _app_row(p, is_disabled=True),
        )
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.disable_app("com.a")

        assert calls == [("disable", "com.a")]
        assert infos == [_app_row("com.a", is_disabled=True)]

    def test_enable_app_calls_ops_then_reloads_info(self, qtbot, monkeypatch):
        vm = BloatwareViewModel(_connected_ctx(), worker_factory=FakeWorker)
        calls = []
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.bloatware.apps_ops.enable_app",
            lambda c, s, p: calls.append(("enable", p)),
        )
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.bloatware.apps_ops.get_app_info",
            lambda c, s, p: _app_row(p, is_disabled=False),
        )
        infos = []
        vm.appInfoChanged.connect(infos.append)

        vm.enable_app("com.a")

        assert calls == [("enable", "com.a")]
        assert infos == [_app_row("com.a", is_disabled=False)]


class TestBloatwarePanel:
    def test_no_selection_hides_both_buttons(self, qtbot):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()

        panel.viewmodel.appInfoChanged.emit(None)

        assert not panel.disable_button.isVisible()
        assert not panel.enable_button.isVisible()

    def test_enabled_app_shows_disable_button_only(self, qtbot):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()

        panel.viewmodel.appInfoChanged.emit(_app_row(is_disabled=False))

        assert panel.disable_button.isVisible()
        assert not panel.enable_button.isVisible()

    def test_disabled_app_shows_enable_button_only(self, qtbot):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.show()

        panel.viewmodel.appInfoChanged.emit(_app_row(is_disabled=True))

        assert panel.enable_button.isVisible()
        assert not panel.disable_button.isVisible()

    def test_disable_system_app_confirmed_includes_warning_and_calls_viewmodel(self, qtbot, monkeypatch):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row(is_system=True, is_disabled=False))
        captured = {}

        def fake_question(parent, title, text, buttons):
            captured["text"] = text
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "disable_app", lambda p: calls.append(p))

        panel.disable_button.click()

        assert _SYSTEM_APP_WARNING in captured["text"]
        assert calls == ["com.a"]

    def test_disable_system_app_cancelled_does_not_call_viewmodel(self, qtbot, monkeypatch):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row(is_system=True, is_disabled=False))
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a: QMessageBox.StandardButton.No))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "disable_app", lambda p: calls.append(p))

        panel.disable_button.click()

        assert calls == []

    def test_disable_user_app_confirmed_without_warning(self, qtbot, monkeypatch):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row(is_system=False, is_disabled=False))
        captured = {}

        def fake_question(parent, title, text, buttons):
            captured["text"] = text
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "disable_app", lambda p: calls.append(p))

        panel.disable_button.click()

        assert _SYSTEM_APP_WARNING not in captured["text"]
        assert calls == ["com.a"]

    def test_enable_calls_viewmodel_without_confirmation(self, qtbot, monkeypatch):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row(is_disabled=True))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "enable_app", lambda p: calls.append(p))

        panel.enable_button.click()

        assert calls == ["com.a"]

    def test_status_change_emits_app_status_changed(self, qtbot, monkeypatch):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.viewmodel.appInfoChanged.emit(_app_row(is_disabled=False))
        monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a: QMessageBox.StandardButton.Yes))
        monkeypatch.setattr(panel.viewmodel, "disable_app", lambda p: panel._on_app_info(_app_row(p, is_disabled=True)))
        emitted = []
        panel.appStatusChanged.connect(lambda p, d: emitted.append((p, d)))

        panel.disable_button.click()

        assert emitted == [("com.a", True)]

    def test_selecting_an_app_does_not_emit_app_status_changed(self, qtbot):
        panel = BloatwarePanel(_connected_ctx())
        qtbot.addWidget(panel)
        emitted = []
        panel.appStatusChanged.connect(lambda p, d: emitted.append((p, d)))

        panel.viewmodel.appInfoChanged.emit(_app_row(is_disabled=False))

        assert emitted == []
