# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.apps.apk_extraction import ApkExtractionViewModel
from droidbridge.gui.pages.apps.apk_extraction import ApkExtractionPanel
from tests.test_gui_viewmodels_device import FakeWorker


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _apk_info():
    return {
        "files": [{"path": "/data/app/com.a/base.apk", "size": 1000, "size_str": "1000 B"}],
        "total_size_str": "1000 B",
    }


class TestApkExtractionViewModel:
    def test_set_current_app_with_none_emits_apk_info_none(self, qtbot):
        vm = ApkExtractionViewModel(_connected_ctx(), worker_factory=FakeWorker)
        infos = []
        vm.apkInfoChanged.connect(infos.append)

        vm.set_current_app(None)

        assert infos == [None]

    def test_set_current_app_with_package_loads_apk_info(self, qtbot, monkeypatch):
        vm = ApkExtractionViewModel(_connected_ctx(), worker_factory=FakeWorker)
        info = _apk_info()
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.apk_extraction.apps_ops.get_apk_info",
            lambda c, s, p: info,
        )
        infos = []
        vm.apkInfoChanged.connect(infos.append)

        vm.set_current_app("com.a")

        assert infos == [info]

    def test_extract_calls_apps_ops_extract_apk_and_emits_finished(self, qtbot, monkeypatch):
        vm = ApkExtractionViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.apk_extraction.apps_ops.get_apk_info",
            lambda c, s, p: _apk_info(),
        )
        vm.set_current_app("com.a")
        calls = []

        def fake_extract(c, s, p, dest_dir, progress_callback=None):
            calls.append((p, dest_dir))
            return ["/tmp/dest/base.apk"]

        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.apps.apk_extraction.apps_ops.extract_apk", fake_extract,
        )
        finished = []
        vm.extractionFinished.connect(finished.append)

        vm.extract("/tmp/dest")

        assert calls == [("com.a", "/tmp/dest")]
        assert finished == [["/tmp/dest/base.apk"]]


class TestApkExtractionPanel:
    def test_no_selection_disables_extract_button(self, qtbot):
        panel = ApkExtractionPanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.apkInfoChanged.emit(None)

        assert not panel.extract_button.isEnabled()

    def test_apk_info_populates_list_and_enables_button(self, qtbot):
        panel = ApkExtractionPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel._current_package = "com.a"

        panel.viewmodel.apkInfoChanged.emit(_apk_info())

        assert panel.extract_button.isEnabled()
        assert panel.files_list.count() == 1
        assert "1000 B" in panel.files_list.item(0).text()

    def test_extract_click_opens_dialog_and_calls_viewmodel_extract(self, qtbot, monkeypatch):
        panel = ApkExtractionPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel._current_package = "com.a"
        panel.viewmodel.apkInfoChanged.emit(_apk_info())
        monkeypatch.setattr(
            "droidbridge.gui.pages.apps.apk_extraction.QFileDialog.getExistingDirectory",
            staticmethod(lambda *a, **k: "/tmp/dest"),
        )
        calls = []
        monkeypatch.setattr(panel.viewmodel, "extract", lambda dest_dir: calls.append(dest_dir))

        panel.extract_button.click()

        assert calls == ["/tmp/dest"]

    def test_extract_cancelled_dialog_does_not_call_viewmodel(self, qtbot, monkeypatch):
        panel = ApkExtractionPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel._current_package = "com.a"
        panel.viewmodel.apkInfoChanged.emit(_apk_info())
        monkeypatch.setattr(
            "droidbridge.gui.pages.apps.apk_extraction.QFileDialog.getExistingDirectory",
            staticmethod(lambda *a, **k: ""),
        )
        calls = []
        monkeypatch.setattr(panel.viewmodel, "extract", lambda dest_dir: calls.append(dest_dir))

        panel.extract_button.click()

        assert calls == []

    def test_extraction_finished_updates_status_label(self, qtbot):
        panel = ApkExtractionPanel(_connected_ctx())
        qtbot.addWidget(panel)

        panel.viewmodel.extractionFinished.emit(["/tmp/dest/base.apk", "/tmp/dest/split1.apk"])

        assert panel.status_label.text() == "Extracted 2 file(s)."
