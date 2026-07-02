# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import functools
from unittest.mock import MagicMock
from PyQt6.QtCore import Qt
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.whatsapp.save_status import SaveStatusViewModel
from droidbridge.gui.pages.whatsapp.save_status import SaveStatusPanel
from tests.test_gui_viewmodels_device import FakeWorker
from droidbridge.modules.transfer import TransferProgress

def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx

_ITEMS = [
    {"local_path": "/tmp/a.jpg", "remote_path": "/r/a.jpg", "extension": "jpg", "filename": "a.jpg"},
    {"local_path": "/tmp/b.mp4", "remote_path": "/r/b.mp4", "extension": "mp4", "filename": "b.mp4"},
]


class TestSaveStatusViewModel:
    def test_load_statuses_emits_results_changed(self, qtbot, monkeypatch):
        vm = SaveStatusViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.whatsapp.save_status.whatsapp_ops.pull_statuses_to_temp",
            lambda *a, **kw: ("/tmp/statuses", _ITEMS),
        )
        results = []
        vm.resultsChanged.connect(results.append)
        vm.load_statuses("whatsapp")
        assert results == [_ITEMS]

    def test_load_statuses_emits_busy(self, qtbot, monkeypatch):
        vm = SaveStatusViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.whatsapp.save_status.whatsapp_ops.pull_statuses_to_temp",
            lambda *a, **kw: ("/tmp", []),
        )
        busy = []
        vm.busyChanged.connect(busy.append)
        vm.load_statuses("whatsapp")
        assert busy == [True, False]

    def test_save_selected_emits_status(self, qtbot, monkeypatch):
        vm = SaveStatusViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.whatsapp.save_status.whatsapp_ops.save_statuses",
            lambda *a, **kw: {"done": 1, "total": 1, "failed": 0, "verified": None},
        )
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.save_selected("whatsapp", "/dest", ["/r/a.jpg"], "skip", False)
        assert any("1" in s for s in statuses)


class TestSaveStatusPanel:
    def test_save_button_disabled_initially(self, qtbot):
        panel = SaveStatusPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert not panel.save_button.isEnabled()

    def test_load_button_triggers_viewmodel_load(self, qtbot, monkeypatch):
        panel = SaveStatusPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "load_statuses", lambda app: calls.append(app))
        qtbot.mouseClick(panel.load_button, Qt.MouseButton.LeftButton)
        assert calls == ["whatsapp"]

    def test_results_changed_populates_thumbnail_grid(self, qtbot, monkeypatch, tmp_path):
        panel = SaveStatusPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        jpg = tmp_path / "a.jpg"
        jpg.write_bytes(b"")
        items = [{"local_path": str(jpg), "remote_path": "/r/a.jpg", "extension": "jpg", "filename": "a.jpg"}]
        panel.viewmodel.resultsChanged.emit(items)
        assert panel._grid_layout.count() > 0

    def test_save_button_enabled_after_checkbox_checked(self, qtbot, monkeypatch, tmp_path):
        panel = SaveStatusPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        jpg = tmp_path / "a.jpg"
        jpg.write_bytes(b"")
        items = [{"local_path": str(jpg), "remote_path": "/r/a.jpg", "extension": "jpg", "filename": "a.jpg"}]
        panel.viewmodel.resultsChanged.emit(items)
        cb = panel._checkboxes[0]
        cb.setChecked(True)
        assert panel.save_button.isEnabled()

    def test_only_checked_remote_paths_passed_to_save(self, qtbot, monkeypatch, tmp_path):
        panel = SaveStatusPanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.dest_edit.setText(str(tmp_path))
        jpg1 = tmp_path / "a.jpg"
        jpg2 = tmp_path / "b.jpg"
        jpg1.write_bytes(b"")
        jpg2.write_bytes(b"")
        items = [
            {"local_path": str(jpg1), "remote_path": "/r/a.jpg", "extension": "jpg", "filename": "a.jpg"},
            {"local_path": str(jpg2), "remote_path": "/r/b.jpg", "extension": "jpg", "filename": "b.jpg"},
        ]
        panel.viewmodel.resultsChanged.emit(items)
        panel._checkboxes[0].setChecked(True)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "save_selected",
                            lambda app, dest, remote_paths, conflict, verify: calls.append(remote_paths))
        qtbot.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)
        assert calls == [["/r/a.jpg"]]
