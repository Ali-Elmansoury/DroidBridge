from droidbridge.gui import backup_ops
from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.backup import BackupManagerPage
from droidbridge.modules.backup_manager import BackupProfile


def _isolated_page(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
    page = BackupManagerPage(DeviceContext())
    qtbot.addWidget(page)
    return page


class TestBackupManagerPage:
    def test_sidebar_has_six_ops_in_order(self, qtbot, tmp_path, monkeypatch):
        page = _isolated_page(qtbot, tmp_path, monkeypatch)
        items = [page.op_list.item(i).text() for i in range(page.op_list.count())]
        assert items == ["Profiles", "Run", "Verify", "History", "Restore", "Contacts/Call Log"]

    def test_selecting_an_op_switches_the_stack(self, qtbot, tmp_path, monkeypatch):
        page = _isolated_page(qtbot, tmp_path, monkeypatch)
        page.op_list.setCurrentRow(2)
        assert page.stack.currentWidget() is page._verify_panel

    def test_profiles_changed_repopulates_profile_combo(self, qtbot, tmp_path, monkeypatch):
        page = _isolated_page(qtbot, tmp_path, monkeypatch)
        profile = BackupProfile(name="nightly", sources=["/sdcard/DCIM"], dest="/d", conflict="skip", excludes=[])
        page._profiles_panel.viewmodel.profilesChanged.emit([profile])
        assert page.profile_combo.count() == 1
        assert page.profile_combo.currentText() == "nightly"

    def test_selecting_restore_row_refreshes_sources(self, qtbot, tmp_path, monkeypatch):
        page = _isolated_page(qtbot, tmp_path, monkeypatch)
        calls = []
        monkeypatch.setattr(page._restore_panel, "refresh_sources", lambda: calls.append(True))
        page.op_list.setCurrentRow(4)
        assert calls == [True]

    def test_selected_profile_returns_none_when_combo_empty(self, qtbot, tmp_path, monkeypatch):
        page = _isolated_page(qtbot, tmp_path, monkeypatch)
        assert page.selected_profile() is None

    def test_selected_profile_returns_combo_text_when_set(self, qtbot, tmp_path, monkeypatch):
        page = _isolated_page(qtbot, tmp_path, monkeypatch)
        profile = BackupProfile(name="nightly", sources=[], dest="/d", conflict="skip", excludes=[])
        page._profiles_panel.viewmodel.profilesChanged.emit([profile])
        assert page.selected_profile() == "nightly"

    def test_viewmodels_property_exposes_all_panel_viewmodels(self, qtbot, tmp_path, monkeypatch):
        page = _isolated_page(qtbot, tmp_path, monkeypatch)
        assert len(page.viewmodels) == 6
