# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from droidbridge.gui.viewmodels.backup.profiles import ProfilesViewModel
from droidbridge.modules.backup_manager import BackupProfile


class TestProfilesViewModel:
    def test_refresh_emits_profiles(self, qtbot, tmp_path, monkeypatch):
        vm = ProfilesViewModel()
        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.profiles.backup_ops.list_profiles",
                            lambda: [BackupProfile(name="nightly", sources=["/sdcard/DCIM"], dest="/d", conflict="skip", excludes=[])])
        emitted = []
        vm.profilesChanged.connect(emitted.append)
        vm.refresh()
        assert len(emitted) == 1
        assert emitted[0][0].name == "nightly"

    def test_save_emits_status_and_refreshes(self, qtbot, monkeypatch):
        vm = ProfilesViewModel()
        calls = []
        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.profiles.backup_ops.save_profile",
                            lambda *a: calls.append(a))
        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.profiles.backup_ops.list_profiles", lambda: [])
        statuses = []
        vm.statusChanged.connect(statuses.append)
        vm.save("nightly", ["/sdcard/DCIM"], "/d", "skip", [])
        assert calls == [("nightly", ["/sdcard/DCIM"], "/d", "skip", [])]
        assert "nightly" in statuses[0]

    def test_remove_reports_not_found(self, qtbot, monkeypatch):
        vm = ProfilesViewModel()
        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.profiles.backup_ops.remove_profile", lambda name: False)
        monkeypatch.setattr("droidbridge.gui.viewmodels.backup.profiles.backup_ops.list_profiles", lambda: [])
        logs = []
        vm.logMessage.connect(lambda msg, level: logs.append(level))
        vm.remove("missing")
        assert logs == ["ERROR"]


from unittest.mock import MagicMock

from PyQt6.QtCore import Qt

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.backup.profiles import ProfilesPanel


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


class TestProfilesPanel:
    def test_save_button_collects_form_fields(self, qtbot, monkeypatch):
        panel = ProfilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        panel.name_edit.setText("nightly")
        panel.sources_list.addItem("/sdcard/DCIM")
        panel.dest_edit.setText("/home/user/backups")
        panel.excludes_list.addItem("/sdcard/DCIM/.thumbnails")

        calls = []
        monkeypatch.setattr(panel.viewmodel, "save", lambda *a: calls.append(a))
        qtbot.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)
        assert calls == [("nightly", ["/sdcard/DCIM"], "/home/user/backups", "skip", ["/sdcard/DCIM/.thumbnails"])]

    def test_selecting_a_profile_populates_the_form(self, qtbot, monkeypatch):
        from droidbridge.modules.backup_manager import BackupProfile
        panel = ProfilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        profile = BackupProfile(name="nightly", sources=["/sdcard/DCIM"], dest="/d", conflict="overwrite", excludes=["/x"])
        monkeypatch.setattr(panel.viewmodel, "get", lambda name: profile)
        panel.profile_list.addItem("nightly")
        panel.profile_list.setCurrentRow(0)
        assert panel.name_edit.text() == "nightly"
        assert panel.dest_edit.text() == "/d"
        assert panel.conflict_combo.currentText() == "overwrite"
        assert [panel.sources_list.item(i).text() for i in range(panel.sources_list.count())] == ["/sdcard/DCIM"]

    def test_profiles_changed_repopulates_profile_list(self, qtbot):
        from droidbridge.modules.backup_manager import BackupProfile
        seen = []
        panel = ProfilesPanel(_connected_ctx(), on_profiles_changed=seen.append)
        qtbot.addWidget(panel)
        panel.viewmodel.profilesChanged.emit([BackupProfile(name="a", sources=[], dest="/d", conflict="skip", excludes=[])])
        assert panel.profile_list.count() == 1
        assert panel.profile_list.item(0).text() == "a"
        assert seen == [["a"]]

    def test_add_source_button_appends_picked_device_path(self, qtbot, monkeypatch):
        panel = ProfilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        monkeypatch.setattr(
            "droidbridge.gui.pages.backup.profiles.RemoteBrowseDialog.get_remote_path",
            lambda *a, **kw: "/sdcard/DCIM",
        )
        qtbot.mouseClick(panel.add_source_button, Qt.MouseButton.LeftButton)
        assert [panel.sources_list.item(i).text() for i in range(panel.sources_list.count())] == ["/sdcard/DCIM"]

    def test_add_exclude_button_appends_picked_device_path(self, qtbot, monkeypatch):
        panel = ProfilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        monkeypatch.setattr(
            "droidbridge.gui.pages.backup.profiles.RemoteBrowseDialog.get_remote_path",
            lambda *a, **kw: "/sdcard/DCIM/.thumbnails",
        )
        qtbot.mouseClick(panel.add_exclude_button, Qt.MouseButton.LeftButton)
        assert [panel.excludes_list.item(i).text() for i in range(panel.excludes_list.count())] == ["/sdcard/DCIM/.thumbnails"]

    def test_add_source_button_cancelled_dialog_adds_nothing(self, qtbot, monkeypatch):
        panel = ProfilesPanel(_connected_ctx())
        qtbot.addWidget(panel)
        monkeypatch.setattr(
            "droidbridge.gui.pages.backup.profiles.RemoteBrowseDialog.get_remote_path",
            lambda *a, **kw: None,
        )
        qtbot.mouseClick(panel.add_source_button, Qt.MouseButton.LeftButton)
        assert panel.sources_list.count() == 0
