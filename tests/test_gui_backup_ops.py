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


class TestRunVerify:
    def test_raises_when_no_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_HISTORY_PATH", tmp_path / "history.json")
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], str(tmp_path / "dest"), "skip", [])
        try:
            backup_ops.run_verify("nightly")
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "nightly" in str(exc)

    def test_ok_when_destination_matches_history(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_HISTORY_PATH", tmp_path / "history.json")
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a.jpg").write_bytes(b"x" * 100)
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], str(dest), "skip", [])
        backup_ops.backup_module.append_history(
            backup_ops.backup_module.DEFAULT_HISTORY_PATH,
            BackupRecord(profile="nightly", timestamp="2026-06-21T00:00:00+00:00",
                         file_count=1, total_bytes=100, duration_seconds=1.0,
                         destination=str(dest), verified=True),
        )
        result = backup_ops.run_verify("nightly")
        assert result == {"ok": True, "expected_files": 1, "expected_bytes": 100, "actual_files": 1, "actual_bytes": 100}


class TestGetHistory:
    def test_returns_all_records_when_no_profile_given(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_HISTORY_PATH", tmp_path / "history.json")
        backup_ops.backup_module.append_history(
            backup_ops.backup_module.DEFAULT_HISTORY_PATH,
            BackupRecord(profile="a", timestamp="2026-06-20T00:00:00+00:00",
                         file_count=1, total_bytes=10, duration_seconds=1.0, destination="/d", verified=True),
        )
        result = backup_ops.get_history()
        assert len(result["records"]) == 1
        assert result["outdated"] is None
        assert result["comparison"] is None

    def test_filters_and_flags_outdated_for_one_profile(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_HISTORY_PATH", tmp_path / "history.json")
        old_record = BackupRecord(profile="nightly", timestamp="2020-01-01T00:00:00+00:00",
                                   file_count=1, total_bytes=10, duration_seconds=1.0, destination="/d", verified=True)
        backup_ops.backup_module.append_history(backup_ops.backup_module.DEFAULT_HISTORY_PATH, old_record)
        result = backup_ops.get_history("nightly", max_age_days=7)
        assert len(result["records"]) == 1
        assert result["outdated"] is True


from droidbridge.modules.backup_manager import RestoreTarget


class TestRunRestore:
    def test_raises_when_profile_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        try:
            backup_ops.run_restore(MagicMock(), "SERIAL", "missing", [], None, None, "skip", False)
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "missing" in str(exc)

    def test_restores_each_target_and_reports_per_source_results(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], str(tmp_path / "dest"), "skip", [])

        item = TransferItem(source=str(tmp_path / "dest/a.jpg"), dest="/sdcard/DCIM/a.jpg", size=50, action=ACTION_COPY)
        plan = TransferPlan(direction="push", items=[item])
        target = RestoreTarget(source="/sdcard/DCIM", local_path=str(tmp_path / "dest"), remote_dir="/sdcard", plan=plan)
        progress = TransferProgress(total_files=1, total_bytes=50)
        progress.done_files = 1

        with patch("droidbridge.gui.backup_ops.backup_module.plan_restore", return_value=[target]), \
             patch("droidbridge.gui.backup_ops.transfer_module.execute_plan", return_value=progress), \
             patch("droidbridge.gui.backup_ops.transfer_module.verify_push", return_value=VerificationResult(1, 50, 1, 50)):
            results = backup_ops.run_restore(MagicMock(), "SERIAL", "nightly", [], None, None, "skip", False)

        assert results == [{"source": "/sdcard/DCIM", "done": 1, "total": 1, "failed": 0, "verified": True}]

    def test_verify_scopes_to_target_source_not_its_broad_parent(self, tmp_path, monkeypatch):
        """target.remote_dir is the source's parent (often /sdcard itself); verifying
        against it would `find` the whole device storage tree. Must verify against
        target.source - the actual restored subtree - instead."""
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], str(tmp_path / "dest"), "skip", [])

        item = TransferItem(source=str(tmp_path / "dest/a.jpg"), dest="/sdcard/DCIM/a.jpg", size=50, action=ACTION_COPY)
        plan = TransferPlan(direction="push", items=[item])
        target = RestoreTarget(source="/sdcard/DCIM", local_path=str(tmp_path / "dest"), remote_dir="/sdcard", plan=plan)
        progress = TransferProgress(total_files=1, total_bytes=50)
        progress.done_files = 1

        with patch("droidbridge.gui.backup_ops.backup_module.plan_restore", return_value=[target]), \
             patch("droidbridge.gui.backup_ops.transfer_module.execute_plan", return_value=progress), \
             patch("droidbridge.gui.backup_ops.transfer_module.verify_push", return_value=VerificationResult(1, 50, 1, 50)) as mock_verify:
            backup_ops.run_restore(MagicMock(), "SERIAL", "nightly", [], None, None, "skip", False)

        assert mock_verify.call_args.args[3] == "/sdcard/DCIM"

    def test_nothing_to_transfer_for_a_target_reports_zeroes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_ops.backup_module, "DEFAULT_PROFILES_PATH", tmp_path / "profiles.json")
        backup_ops.save_profile("nightly", ["/sdcard/DCIM"], str(tmp_path / "dest"), "skip", [])

        plan = TransferPlan(direction="push", items=[])
        target = RestoreTarget(source="/sdcard/DCIM", local_path=str(tmp_path / "dest"), remote_dir="/sdcard", plan=plan)

        with patch("droidbridge.gui.backup_ops.backup_module.plan_restore", return_value=[target]), \
             patch("droidbridge.gui.backup_ops.transfer_module.execute_plan") as mock_execute:
            results = backup_ops.run_restore(MagicMock(), "SERIAL", "nightly", [], None, None, "skip", True)

        mock_execute.assert_not_called()
        assert results == [{"source": "/sdcard/DCIM", "done": 0, "total": 0, "failed": 0, "verified": None}]
