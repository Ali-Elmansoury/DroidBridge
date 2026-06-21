from droidbridge.gui.viewmodels.backup.history import HistoryViewModel
from droidbridge.modules.backup_manager import BackupRecord


class TestHistoryViewModel:
    def test_refresh_emits_history(self, qtbot, monkeypatch):
        vm = HistoryViewModel()
        record = BackupRecord(profile="nightly", timestamp="2026-06-21T00:00:00+00:00",
                               file_count=1, total_bytes=100, duration_seconds=1.0,
                               destination="/d", verified=True)
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.history.backup_ops.get_history",
            lambda profile_name=None, max_age_days=7: {"records": [record], "outdated": False, "comparison": None},
        )
        emitted = []
        vm.historyChanged.connect(emitted.append)
        vm.refresh("nightly")
        assert emitted == [{"records": [record], "outdated": False, "comparison": None}]

    def test_refresh_forwards_profile_and_max_age(self, qtbot, monkeypatch):
        vm = HistoryViewModel()
        calls = []
        monkeypatch.setattr(
            "droidbridge.gui.viewmodels.backup.history.backup_ops.get_history",
            lambda profile_name=None, max_age_days=7: calls.append((profile_name, max_age_days)) or {"records": [], "outdated": None, "comparison": None},
        )
        vm.refresh("nightly", max_age_days=3)
        assert calls == [("nightly", 3)]
