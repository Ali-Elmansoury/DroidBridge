# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
# tests/test_gui_whatsapp_organize.py
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from droidbridge.gui.viewmodels.whatsapp.organize import OrganizeViewModel
from droidbridge.gui.pages.whatsapp.organize import OrganizePanel


class TestOrganizeViewModel:
    def test_organize_emits_status_on_complete(self, qtbot, monkeypatch, tmp_path):
        vm = OrganizeViewModel()
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.organize.whatsapp_ops.run_organize",
                            lambda src, type_name: {"organized": 10, "fixed": 2, "dest": "/dest"})
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.organize(str(tmp_path), "images")
        assert any("10" in s for s in statuses)
        assert any("/dest" in s for s in statuses)

    def test_organize_error_emits_status(self, qtbot, monkeypatch, tmp_path):
        vm = OrganizeViewModel()
        monkeypatch.setattr("droidbridge.gui.viewmodels.whatsapp.organize.whatsapp_ops.run_organize",
                            lambda src, type_name: (_ for _ in ()).throw(RuntimeError("bad dir")))
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.organize(str(tmp_path), "images")
        assert any("bad dir" in s for s in statuses)


class TestOrganizePanel:
    def test_type_combo_has_seven_items(self, qtbot):
        panel = OrganizePanel(lambda: "whatsapp")
        qtbot.addWidget(panel)
        assert panel.type_combo.count() == 7

    def test_organize_button_triggers_viewmodel(self, qtbot, monkeypatch, tmp_path):
        panel = OrganizePanel(lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.src_edit.setText(str(tmp_path))
        calls = []
        monkeypatch.setattr(panel.viewmodel, "organize", lambda src, type_name: calls.append((src, type_name)))
        qtbot.mouseClick(panel.organize_button, Qt.MouseButton.LeftButton)
        assert calls[0] == (str(tmp_path), "voice_notes")

    def test_status_changed_updates_status_label(self, qtbot):
        panel = OrganizePanel(lambda: "whatsapp")
        qtbot.addWidget(panel)
        panel.viewmodel.statusChanged.emit("Done!")
        assert panel.status_label.text() == "Done!"
