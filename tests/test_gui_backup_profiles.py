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
