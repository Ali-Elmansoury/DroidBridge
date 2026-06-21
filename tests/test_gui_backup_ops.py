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


from unittest.mock import MagicMock, patch

from droidbridge.modules.backup_manager import BackupRecord
from droidbridge.modules.transfer import TransferPlan, TransferProgress, TransferItem, ACTION_COPY, VerificationResult


class TestRunBackup:
    def test_raises_when_profile_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        try:
            backup_ops.run_backup(MagicMock(), "SERIAL", "missing", False)
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "missing" in str(exc)

    def test_runs_plan_and_logs_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_HISTORY_PATH", tmp_path / "history.json")
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], str(tmp_path / "dest"), "skip", [])

        item = TransferItem(source="/sdcard/DCIM/a.jpg", dest=str(tmp_path / "dest/a.jpg"), size=100, action=ACTION_COPY)
        plan = TransferPlan(direction="pull", items=[item])
        progress = TransferProgress(total_files=1, total_bytes=100)
        progress.done_files = 1

        with patch("droidbridge.gui.backup_ops.backup_module.plan_backup", return_value=plan), \
             patch("droidbridge.gui.backup_ops.transfer_module.execute_plan", return_value=progress) as mock_execute, \
             patch("droidbridge.gui.backup_ops.transfer_module.verify_pull", return_value=VerificationResult(1, 100, 1, 100)):
            result = backup_ops.run_backup(MagicMock(), "SERIAL", "nightly", False)

        assert result == {"done": 1, "total": 1, "failed": 0, "verified": True}
        mock_execute.assert_called_once()

        history = backup_ops.backup_module.load_history(backup_ops.backup_module.DEFAULT_HISTORY_PATH)
        assert len(history) == 1
        assert history[0].profile == "nightly"
        assert history[0].verified is True

    def test_nothing_to_transfer_skips_execute_and_still_logs_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_HISTORY_PATH", tmp_path / "history.json")
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], str(tmp_path / "dest"), "skip", [])

        plan = TransferPlan(direction="pull", items=[])

        with patch("droidbridge.gui.backup_ops.backup_module.plan_backup", return_value=plan), \
             patch("droidbridge.gui.backup_ops.transfer_module.execute_plan") as mock_execute, \
             patch("droidbridge.gui.backup_ops.transfer_module.verify_pull", return_value=VerificationResult(0, 0, 0, 0)):
            result = backup_ops.run_backup(MagicMock(), "SERIAL", "nightly", False)

        mock_execute.assert_not_called()
        assert result == {"done": 0, "total": 0, "failed": 0, "verified": True}
