import datetime
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.viewmodels.whatsapp.delete import DeleteViewModel
from droidbridge.gui.pages.whatsapp.delete import DeletePanel
from tests.test_gui_viewmodels_device import FakeWorker
from droidbridge.modules.whatsapp import BACKUP_TYPES

def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestDeleteViewModel:
    def test_preview_emits_results_and_status(self, qtbot, monkeypatch):
        vm = DeleteViewModel(_connected_ctx(), worker_factory=FakeWorker)
        rows = [{"path": "/f.jpg", "folder_type": "Images", "size_str": "1 KB"}]
        fake_plans = [{"install": MagicMock(), "plan": MagicMock(total_files=1)}]
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.delete.whatsapp_ops.build_delete_preview",
                            lambda *a, **kw: {"plans": fake_plans, "rows": rows, "error": None})
        results, statuses = [], []
        vm.resultsChanged.connect(results.append)
        vm.statusChanged.connect(statuses.append)
        vm.preview("whatsapp", datetime.date(2024, 1, 1), None, "")
        assert results == [rows]
        assert any("1" in s for s in statuses)

    def test_preview_error_emits_status_and_empty_results(self, qtbot, monkeypatch):
        vm = DeleteViewModel(_connected_ctx(), worker_factory=FakeWorker)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.delete.whatsapp_ops.build_delete_preview",
                            lambda *a, **kw: {"plans": [], "rows": [], "error": "backup missing"})
        results, statuses = [], []
        vm.resultsChanged.connect(results.append)
        vm.statusChanged.connect(statuses.append)
        vm.preview("whatsapp", datetime.date(2024, 1, 1), None, "/backup")
        assert results == [[]]
        assert any("backup missing" in s for s in statuses)

    def test_execute_emits_status_on_done(self, qtbot, monkeypatch):
        vm = DeleteViewModel(_connected_ctx(), worker_factory=FakeWorker)
        fake_plans = [{"install": MagicMock(), "plan": MagicMock(total_files=3)}]
        vm._plans = fake_plans
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.delete.whatsapp_ops.execute_delete",
                            lambda *a, **kw: {"deleted": 3})
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.execute()
        assert any("3" in s for s in statuses)


class TestDeletePanel:
    def test_delete_button_disabled_before_preview(self, qtbot):
        panel = DeletePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert not panel.delete_button.isEnabled()

    def test_delete_button_enabled_after_non_empty_preview(self, qtbot, monkeypatch):
        panel = DeletePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        rows = [{"path": "/f.jpg", "folder_type": "Images", "size_str": "1 KB"}]
        fake_plans = [{"install": MagicMock(), "plan": MagicMock(total_files=1)}]
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.delete.whatsapp_ops.build_delete_preview",
                            lambda *a, **kw: {"plans": fake_plans, "rows": rows, "error": None})
        with qtbot.waitSignal(panel.viewmodel.resultsChanged, timeout=1000):
            panel.viewmodel.preview("whatsapp", datetime.date(2024, 1, 1), None, "")
        assert panel.delete_button.isEnabled()

    def test_delete_button_stays_disabled_after_empty_preview(self, qtbot, monkeypatch):
        panel = DeletePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.delete.whatsapp_ops.build_delete_preview",
                            lambda *a, **kw: {"plans": [], "rows": [], "error": None})
        with qtbot.waitSignal(panel.viewmodel.resultsChanged, timeout=1000):
            panel.viewmodel.preview("whatsapp", datetime.date(2024, 1, 1), None, "")
        assert not panel.delete_button.isEnabled()

    def test_yes_delete_confirmation_triggers_execute(self, qtbot, monkeypatch):
        panel = DeletePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.viewmodel._plans = [{"install": MagicMock(), "plan": MagicMock(total_files=1)}]
        panel.delete_button.setEnabled(True)
        execute_calls = []
        monkeypatch.setattr(panel.viewmodel, "execute", lambda: execute_calls.append(True))
        monkeypatch.setattr(
            "droidbridge.gui.pages.whatsapp.delete.QInputDialog.getText",
            lambda *a, **kw: ("YES DELETE", True),
        )
        qtbot.mouseClick(panel.delete_button, Qt.MouseButton.LeftButton)
        assert execute_calls == [True]

    def test_wrong_confirmation_does_not_trigger_execute(self, qtbot, monkeypatch):
        panel = DeletePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.delete_button.setEnabled(True)
        execute_calls = []
        monkeypatch.setattr(panel.viewmodel, "execute", lambda: execute_calls.append(True))
        monkeypatch.setattr(
            "droidbridge.gui.pages.whatsapp.delete.QInputDialog.getText",
            lambda *a, **kw: ("nope", True),
        )
        qtbot.mouseClick(panel.delete_button, Qt.MouseButton.LeftButton)
        assert execute_calls == []

    def test_selected_keep_type_passes_folder_type_value_not_dict_key(self, qtbot, monkeypatch):
        # Regression: plan_delete() filters keep_types by `folder_type` (the
        # BACKUP_TYPES *value*, e.g. "Voice Notes"), not the snake_case CLI
        # key ("voice_notes"). Selecting "voice_notes" used to pass the raw
        # key straight through, so nothing was ever kept.
        panel = DeletePanel(_connected_ctx(), lambda: "whatsapp")
        qtbot.addWidget(panel)
        matches = [i for i in range(panel.keep_list.count())
                   if panel.keep_list.item(i).text() == BACKUP_TYPES["voice_notes"]]
        assert matches, "keep_list must display the folder_type value, not the dict key"
        panel.keep_list.item(matches[0]).setSelected(True)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "preview",
                             lambda app, before, keep_types, backup_dir: calls.append(keep_types))
        panel._on_preview()
        assert calls == [[BACKUP_TYPES["voice_notes"]]]
