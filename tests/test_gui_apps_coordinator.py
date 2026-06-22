from unittest.mock import MagicMock

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.apps import AppsPage

_TAB_LABELS = ["Listing", "Cache Management", "Uninstall", "APK Extraction", "Bloatware Manager", "Backup & Restore"]


def _connected_ctx():
    ctx = DeviceContext()
    ctx.set_connected(MagicMock(), "S1", "Pixel 7")
    return ctx


def _make_page(qtbot):
    page = AppsPage(_connected_ctx())
    qtbot.addWidget(page)
    return page


def _row(package="com.a", is_system=False, is_disabled=False):
    return {
        "package": package, "version_name": "1.0", "version_code": 1,
        "installed_str": "", "updated_str": "",
        "apk_size": 10, "apk_size_str": "10 B", "data_size": 20, "data_size_str": "20 B",
        "cache_size": 5, "cache_size_str": "5 B", "total_size_str": "35 B",
        "kind": "system" if is_system else "user", "is_system": is_system,
        "status": "Disabled" if is_disabled else "Enabled", "is_disabled": is_disabled,
    }


class TestAppsPage:
    def test_op_list_has_six_items_in_order(self, qtbot):
        page = _make_page(qtbot)
        assert page.op_list.count() == 6
        labels = [page.op_list.item(i).text() for i in range(6)]
        assert labels == _TAB_LABELS

    def test_selecting_row_switches_stack(self, qtbot):
        page = _make_page(qtbot)
        page.op_list.setCurrentRow(3)
        assert page.stack.currentIndex() == 3

    def test_default_selected_row_is_listing(self, qtbot):
        page = _make_page(qtbot)
        assert page.op_list.currentRow() == 0
        assert page.stack.currentIndex() == 0

    def test_viewmodels_returns_six_entries_in_order(self, qtbot):
        page = _make_page(qtbot)
        assert len(page.viewmodels) == 6
        assert page.viewmodels[0] is page.listing_panel.viewmodel
        assert page.viewmodels[5] is page.backup_restore_panel.viewmodel

    def test_app_selected_relays_to_all_other_panels(self, qtbot, monkeypatch):
        page = _make_page(qtbot)
        calls = {}
        for name, panel in [
            ("cache", page.cache_panel), ("uninstall", page.uninstall_panel),
            ("apk_extraction", page.apk_extraction_panel), ("bloatware", page.bloatware_panel),
            ("backup_restore", page.backup_restore_panel),
        ]:
            monkeypatch.setattr(panel, "set_current_app", lambda p, name=name: calls.setdefault(name, []).append(p))

        page.listing_panel.appSelected.emit("com.a")

        assert calls == {
            "cache": ["com.a"], "uninstall": ["com.a"], "apk_extraction": ["com.a"],
            "bloatware": ["com.a"], "backup_restore": ["com.a"],
        }

    def test_listing_results_relay_to_cache_set_all_apps(self, qtbot, monkeypatch):
        page = _make_page(qtbot)
        calls = []
        monkeypatch.setattr(page.cache_panel, "set_all_apps", lambda rows: calls.append(rows))
        rows = [_row("com.a"), _row("com.b")]

        page.listing_panel.viewmodel.resultsChanged.emit(rows)

        assert calls == [rows]

    def test_app_uninstalled_clears_selection_and_refreshes_listing(self, qtbot, monkeypatch):
        page = _make_page(qtbot)
        clear_calls = []
        refresh_calls = []
        monkeypatch.setattr(page.listing_panel, "clear_selection", lambda: clear_calls.append(True))
        monkeypatch.setattr(page.listing_panel, "refresh", lambda: refresh_calls.append(True))

        page.uninstall_panel.appUninstalled.emit()

        assert clear_calls == [True]
        assert refresh_calls == [True]

    def test_bloatware_status_change_relays_to_listing_update_row_status(self, qtbot, monkeypatch):
        page = _make_page(qtbot)
        calls = []
        monkeypatch.setattr(
            page.listing_panel, "update_row_status", lambda package, is_disabled: calls.append((package, is_disabled)),
        )

        page.bloatware_panel.appStatusChanged.emit("com.a", True)

        assert calls == [("com.a", True)]
