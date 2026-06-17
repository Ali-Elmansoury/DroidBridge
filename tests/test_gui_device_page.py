"""Tests for droidbridge.gui.pages.device.DevicePage (Phase 6.1)."""

from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence

from droidbridge.gui.device_context import DeviceContext
from droidbridge.gui.pages.device import DevicePage
from droidbridge.gui.viewmodels.device import DeviceViewModel
from tests.test_gui_viewmodels_device import FakeWorker


def _make_page():
    context = DeviceContext()
    vm = DeviceViewModel(context, worker_factory=FakeWorker)
    page = DevicePage(vm)
    return page, vm, context


class TestDevicePage:
    def test_refresh_disabled_until_connected(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.refresh_button.isEnabled() is False

    def test_no_duplicate_connect_button(self, qtbot):
        """The top bar (MainWindow) already has a global Connect button - DevicePage
        must not have its own, redundant one."""
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert not hasattr(page, "connect_button")

    def test_info_changed_populates_labels(self, qtbot):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        vm.infoChanged.emit(
            {
                "serial": "SERIAL123",
                "model": "Pixel 7",
                "manufacturer": "Google",
                "android": "14 (SDK 34)",
                "build": "UQ1A.240205.004",
                "battery": "85% (charging)",
                "storage_total": "1000.0 KB",
                "storage_used": "500.0 KB",
                "storage_free": "500.0 KB",
                "storage_used_percent": 50.0,
            }
        )

        assert page.serial_label.text() == "SERIAL123"
        assert page.model_label.text() == "Pixel 7"
        assert page.android_label.text() == "14 (SDK 34)"
        assert page.storage_bar.value() == 50

    def test_connection_changed_enables_refresh(self, qtbot):
        page, _vm, context = _make_page()
        qtbot.addWidget(page)

        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")

        assert page.refresh_button.isEnabled() is True


class TestAutoRefresh:
    def test_checkbox_checked_by_default(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)

        assert page.auto_refresh_checkbox.isChecked() is True

    def test_connecting_starts_timer(self, qtbot):
        page, _vm, context = _make_page()
        qtbot.addWidget(page)

        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")

        assert page._refresh_timer.isActive() is True
        assert page._refresh_timer.interval() == 15000

    def test_unchecking_checkbox_stops_timer(self, qtbot):
        page, _vm, context = _make_page()
        qtbot.addWidget(page)
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")

        page.auto_refresh_checkbox.setChecked(False)

        assert page._refresh_timer.isActive() is False

    def test_disconnecting_stops_timer(self, qtbot):
        page, _vm, context = _make_page()
        qtbot.addWidget(page)
        context.set_connected(MagicMock(), "SERIAL123", "Pixel 7")

        context.clear()

        assert page._refresh_timer.isActive() is False

    def test_refresh_timer_calls_poll_when_idle(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []
        monkeypatch.setattr(vm, "poll", lambda: calls.append(True))

        page._busy = False
        page._on_refresh_timer()

        assert calls == [True]

    def test_refresh_timer_skips_when_busy(self, qtbot, monkeypatch):
        page, vm, _context = _make_page()
        qtbot.addWidget(page)

        calls = []
        monkeypatch.setattr(vm, "poll", lambda: calls.append(True))

        page._busy = True
        page._on_refresh_timer()

        assert calls == []


class TestDevicePageTooltipsAndShortcuts:
    def test_refresh_button_has_tooltip(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        assert page.refresh_button.toolTip() != ""

    def test_auto_refresh_checkbox_has_tooltip(self, qtbot):
        page, _vm, _context = _make_page()
        qtbot.addWidget(page)
        assert page.auto_refresh_checkbox.toolTip() != ""

    def test_f5_triggers_refresh(self, qtbot, monkeypatch):
        page, vm, context = _make_page()
        context.set_connected(MagicMock(), "SERIAL", "Model")
        qtbot.addWidget(page)
        page.show()

        calls = []
        monkeypatch.setattr(vm, "refresh", lambda: calls.append(1))

        qtbot.keyClick(page, Qt.Key.Key_F5)

        assert calls == [1]
