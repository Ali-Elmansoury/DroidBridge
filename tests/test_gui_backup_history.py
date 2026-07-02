# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from droidbridge.gui.viewmodels.backup.history import HistoryViewModel
from droidbridge.modules.backup_manager import BackupRecord
from PyQt6.QtCore import Qt

from droidbridge.gui.pages.backup.history import HistoryPanel


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


class TestHistoryPanel:
    def test_refresh_button_calls_viewmodel_with_selected_profile(self, qtbot, monkeypatch):
        panel = HistoryPanel(lambda: "nightly")
        qtbot.addWidget(panel)
        calls = []
        monkeypatch.setattr(panel.viewmodel, "refresh", lambda profile, max_age_days=7: calls.append(profile))
        qtbot.mouseClick(panel.refresh_button, Qt.MouseButton.LeftButton)
        assert calls == ["nightly"]

    def test_history_changed_populates_table(self, qtbot):
        panel = HistoryPanel(lambda: "nightly")
        qtbot.addWidget(panel)
        record = BackupRecord(profile="nightly", timestamp="2026-06-21T00:00:00+00:00",
                               file_count=2, total_bytes=200, duration_seconds=1.5,
                               destination="/d", verified=True)
        panel.viewmodel.historyChanged.emit({"records": [record], "outdated": False, "comparison": None})
        assert panel.table.rowCount() == 1
        assert panel.table.item(0, 0).text() == "nightly"
        assert panel.table.item(0, 2).text() == "2"

    def test_history_changed_shows_outdated_flag(self, qtbot):
        panel = HistoryPanel(lambda: "nightly")
        qtbot.addWidget(panel)
        panel.viewmodel.historyChanged.emit({"records": [], "outdated": True, "comparison": None})
        assert "outdated" in panel.outdated_label.text().lower()

    def test_history_changed_shows_comparison_delta(self, qtbot):
        panel = HistoryPanel(lambda: "nightly")
        qtbot.addWidget(panel)
        panel.viewmodel.historyChanged.emit(
            {"records": [], "outdated": False, "comparison": {"file_count_delta": 3, "total_bytes_delta": 1024, "previous": None, "latest": None}}
        )
        assert "3" in panel.comparison_label.text()
        assert "1024" in panel.comparison_label.text()
