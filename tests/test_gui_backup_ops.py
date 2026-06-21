from droidbridge.gui import backup_ops
from droidbridge.modules.backup_manager import BackupProfile


class TestProfileCrud:
    def test_save_and_list_profile(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], "/home/user/backups", "skip", [])
        profiles = backup_ops.list_profiles()
        assert len(profiles) == 1
        assert profiles[0] == BackupProfile(name="nightly", sources=["/sdcard/DCIM"], dest="/home/user/backups", conflict="skip", excludes=[])

    def test_get_profile_returns_none_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        assert backup_ops.get_profile("missing") is None

    def test_remove_profile(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], "/home/user/backups", "skip", [])
        assert backup_ops.remove_profile("nightly") is True
        assert backup_ops.list_profiles() == []

    def test_remove_profile_returns_false_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        assert backup_ops.remove_profile("missing") is False
